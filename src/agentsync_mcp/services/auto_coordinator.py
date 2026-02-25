from __future__ import annotations

import asyncio
import os
import shlex
import signal
import socket
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.identity import detect_agent_session_identity
from agentsync_mcp.services.lock_manager import LockManager


def _git_status_dirty_files(repo_root: Path) -> set[str]:
    """Return dirty/untracked files from git status porcelain output."""
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return set()

    files: set[str] = set()
    for raw_line in proc.stdout.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if len(line) < 4:
            continue
        path_part = line[3:]
        if " -> " in path_part:
            _, new_path = path_part.split(" -> ", 1)
            path_part = new_path
        files.add(path_part)
    return files


@dataclass
class AutoCoordinationOptions:
    client: str
    command: list[str]
    db_path: str = "data/agentsync.db"
    poll_interval: float = 1.0
    ttl_seconds: int = 1800
    description: str | None = None
    heartbeat_interval: float = 10.0


class AutoCoordinator:
    """Launch an agent command and auto-coordinate file locks from repo changes."""

    def __init__(self, options: AutoCoordinationOptions):
        self.options = options
        self.repo_root = self._resolve_repo_root()
        self.baseline_dirty_files = _git_status_dirty_files(self.repo_root)
        self.auto_locked_files: set[str] = set()
        self._last_renewal: float = 0.0

    def _resolve_repo_root(self) -> Path:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return Path.cwd()
        return Path(proc.stdout.strip())

    async def run(self) -> int:
        child_env = self._build_child_env()
        session_meta = self._session_record_for_env(child_env)

        db = Database(self.options.db_path)
        await db.initialize()
        lock_manager = LockManager(db, cleanup_interval=max(30, int(self.options.poll_interval * 10)))
        await lock_manager.start()

        agent_id = session_meta["agent_id"]
        agent_type = session_meta["agent_type"]
        await db.register_agent(agent_id, agent_type, session=session_meta)

        proc = await asyncio.create_subprocess_exec(
            *self.options.command,
            env=child_env,
            cwd=str(self.repo_root),
        )

        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def _handle_signal() -> None:
            stop_event.set()
            if proc.returncode is None:
                try:
                    proc.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass

        try:
            try:
                loop.add_signal_handler(signal.SIGINT, _handle_signal)
            except NotImplementedError:
                pass
            try:
                loop.add_signal_handler(signal.SIGTERM, _handle_signal)
            except NotImplementedError:
                pass

            await self._event_loop(proc, db, lock_manager, stop_event, agent_id)
            code = await proc.wait()
        finally:
            await self._release_all_auto_locks(lock_manager, db, agent_id)
            await db.set_agent_status(agent_id, "inactive")
            await lock_manager.stop()
            await db.close()

            # best effort: remove custom signal handlers
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.remove_signal_handler(sig)
                except Exception:
                    pass

        return code

    async def _event_loop(
        self,
        proc: asyncio.subprocess.Process,
        db: Database,
        lock_manager: LockManager,
        stop_event: asyncio.Event,
        agent_id: str,
    ) -> None:
        renew_every = max(3.0, min(self.options.ttl_seconds / 2, 60.0))
        heartbeat_every = max(2.0, self.options.heartbeat_interval)
        last_heartbeat = 0.0

        while proc.returncode is None:
            now = asyncio.get_running_loop().time()

            dirty_files = _git_status_dirty_files(self.repo_root)
            dirty_files = {
                p for p in dirty_files if p and not p.startswith(".git/")
            }
            session_dirty_files = dirty_files - self.baseline_dirty_files

            new_dirty = [p for p in sorted(session_dirty_files - self.auto_locked_files)]
            for file_path in new_dirty:
                await self._acquire_auto_lock(lock_manager, db, agent_id, file_path)

            cleaned = [p for p in sorted(self.auto_locked_files - session_dirty_files)]
            for file_path in cleaned:
                released = await lock_manager.release_lock(file_path, agent_id)
                if released:
                    self.auto_locked_files.discard(file_path)
                    await db.log_event("auto_lock_released_clean", agent_id, {"file": file_path})

            if self.auto_locked_files and (now - self._last_renewal) >= renew_every:
                for file_path in sorted(self.auto_locked_files):
                    await lock_manager.acquire_lock(
                        file_path=file_path,
                        agent_id=agent_id,
                        description=self._lock_description(),
                        ttl_seconds=self.options.ttl_seconds,
                    )
                self._last_renewal = now

            if (now - last_heartbeat) >= heartbeat_every:
                await db.touch_agent(agent_id)
                await db.mark_stale_agents_inactive()
                last_heartbeat = now

            try:
                await asyncio.wait_for(proc.wait(), timeout=self.options.poll_interval)
            except asyncio.TimeoutError:
                pass

            if stop_event.is_set() and proc.returncode is not None:
                break

    async def _acquire_auto_lock(
        self,
        lock_manager: LockManager,
        db: Database,
        agent_id: str,
        file_path: str,
    ) -> None:
        result = await lock_manager.acquire_lock(
            file_path=file_path,
            agent_id=agent_id,
            description=self._lock_description(),
            ttl_seconds=self.options.ttl_seconds,
        )
        if result.get("success"):
            self.auto_locked_files.add(file_path)
            await db.log_event("auto_lock_acquired", agent_id, {"file": file_path})
            return

        blocked_by = result.get("locked_by", "unknown")
        msg = (
            f"[agentsync] lock conflict on {file_path} "
            f"(held by {blocked_by})"
        )
        print(msg, flush=True)
        await db.log_event(
            "auto_lock_conflict",
            agent_id,
            {
                "file": file_path,
                "locked_by": blocked_by,
                "description": result.get("description"),
            },
        )

    async def _release_all_auto_locks(
        self, lock_manager: LockManager, db: Database, agent_id: str
    ) -> None:
        for file_path in sorted(self.auto_locked_files):
            await lock_manager.release_lock(file_path, agent_id)
            await db.log_event("auto_lock_released_exit", agent_id, {"file": file_path})
        self.auto_locked_files.clear()

    def _lock_description(self) -> str:
        if self.options.description:
            return self.options.description
        rendered_cmd = " ".join(shlex.quote(part) for part in self.options.command)
        return f"Auto-coordination ({self.options.client}) for `{rendered_cmd}`"

    def _build_child_env(self) -> dict[str, str]:
        env = os.environ.copy()
        client = self.options.client.lower()

        if client == "auto":
            if any(key.startswith("CODEX_") for key in env):
                client = "codex"
            elif any(key.startswith("CLAUDE_") for key in env):
                client = "claude"
            else:
                client = "unknown"

        agent_id = env.get("AGENTSYNC_AGENT_ID")
        if not agent_id:
            host = socket.gethostname().split(".")[0].lower()
            agent_id = f"{client}-{host}-{os.getpid()}-{uuid.uuid4().hex[:6]}"

        session_label = env.get("AGENTSYNC_SESSION_LABEL")
        if not session_label:
            session_label = f"{client}-{self.repo_root.name}-{os.getpid()}"

        env["AGENTSYNC_AGENT_ID"] = agent_id
        env["AGENTSYNC_AGENT_TYPE"] = client
        env["AGENTSYNC_CLIENT_NAME"] = client.title() if client != "unknown" else "Unknown Agent"
        env["AGENTSYNC_SESSION_LABEL"] = session_label
        env["AGENTSYNC_AUTO_COORDINATION"] = "1"
        return env

    def _session_record_for_env(self, child_env: dict[str, str]) -> dict:
        ident = detect_agent_session_identity(child_env)
        record = ident.to_agent_record()
        meta = dict(record.get("metadata") or {})
        meta["auto_wrapper"] = True
        meta["wrapped_command"] = self.options.command
        record["metadata"] = meta
        return record
