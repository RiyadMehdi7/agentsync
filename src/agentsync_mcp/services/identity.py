from __future__ import annotations

import os
import re
import socket
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


def generate_agent_id() -> str:
    """Generate a unique agent ID for this server process.

    Format: ``{hostname}-{pid}-{short_uuid}``

    Each MCP stdio server process gets its own ID automatically.
    Users never need to think about this.
    """
    host = socket.gethostname().split(".")[0][:12]
    pid = os.getpid()
    short_id = uuid.uuid4().hex[:6]
    return f"{host}-{pid}-{short_id}"


@dataclass(frozen=True)
class AgentSessionIdentity:
    """Runtime identity for the connected MCP client session."""

    agent_id: str
    agent_type: str
    client_name: str
    session_label: str
    host: str
    pid: int
    cwd: str
    repo_root: str | None
    repo_name: str | None
    git_branch: str | None
    transport: str = "stdio"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_agent_record(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "client_name": self.client_name,
            "session_label": self.session_label,
            "host": self.host,
            "pid": self.pid,
            "cwd": self.cwd,
            "repo_root": self.repo_root,
            "repo_name": self.repo_name,
            "git_branch": self.git_branch,
            "transport": self.transport,
            "metadata": self.metadata,
        }

    def to_public_dict(self) -> dict[str, Any]:
        return self.to_agent_record()


def detect_agent_session_identity(env: Mapping[str, str] | None = None) -> AgentSessionIdentity:
    """Best-effort zero-config detection of the connected agent session."""
    env = env or os.environ
    host = _safe_slug(socket.gethostname().split(".")[0][:24]) or "host"
    pid = os.getpid()
    ppid = os.getppid()

    cwd_path = Path.cwd()
    repo_root = _git("rev-parse", "--show-toplevel")
    git_branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    repo_name = Path(repo_root).name if repo_root else cwd_path.name

    env_type = env.get("AGENTSYNC_AGENT_TYPE")
    env_client_name = env.get("AGENTSYNC_CLIENT_NAME")
    process_markers = _get_process_markers(ppid)
    detected_type, detected_name, detected_from = _detect_client(env, process_markers)

    agent_type = _normalize_agent_type(env_type or detected_type)
    client_name = env_client_name or detected_name or _display_name_for(agent_type)

    session_hint = (
        env.get("AGENTSYNC_SESSION_LABEL")
        or env.get("AGENTSYNC_SESSION_ID")
        or env.get("CLAUDE_SESSION_ID")
        or env.get("CODEX_SESSION_ID")
        or env.get("CURSOR_SESSION_ID")
    )
    branch_hint = None if git_branch in (None, "HEAD") else git_branch
    default_label = "-".join(
        part
        for part in [client_name, repo_name, branch_hint, str(pid)]
        if part
    )
    session_label = session_hint or default_label

    agent_id = env.get("AGENTSYNC_AGENT_ID")
    if not agent_id:
        short_id = uuid.uuid4().hex[:6]
        agent_id = f"{agent_type}-{host}-{pid}-{short_id}"

    metadata = {
        "ppid": ppid,
        "detected_from": detected_from,
        "process_markers": process_markers,
        "env_markers": _interesting_env_markers(env),
        "repo_root_source": "git" if repo_root else "cwd",
    }

    return AgentSessionIdentity(
        agent_id=agent_id,
        agent_type=agent_type,
        client_name=client_name,
        session_label=session_label,
        host=host,
        pid=pid,
        cwd=str(cwd_path),
        repo_root=repo_root,
        repo_name=repo_name,
        git_branch=git_branch,
        metadata=metadata,
    )


def _git(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=0.75,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _get_process_markers(ppid: int) -> list[str]:
    markers: list[str] = []
    current = ppid
    for _ in range(4):
        if current <= 1:
            break
        command = _ps_value(current, "command")
        if command:
            markers.append(command)
        parent = _ps_value(current, "ppid")
        if not parent:
            break
        try:
            next_pid = int(parent)
        except ValueError:
            break
        if next_pid == current:
            break
        current = next_pid
    return markers


def _ps_value(pid: int, field: str) -> str | None:
    try:
        proc = subprocess.run(
            ["ps", "-o", f"{field}=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _detect_client(env: Mapping[str, str], process_markers: list[str]) -> tuple[str, str, str]:
    checks = [
        ("codex", "Codex", _matches_codex(env, process_markers)),
        ("claude", "Claude", _matches_claude(env, process_markers)),
        ("cursor", "Cursor", _matches_keyword(env, process_markers, "cursor")),
        ("aider", "Aider", _matches_keyword(env, process_markers, "aider")),
    ]
    for agent_type, display, detected_from in checks:
        if detected_from:
            return agent_type, display, detected_from
    return "unknown", "Unknown Agent", "fallback"


def _matches_codex(env: Mapping[str, str], process_markers: list[str]) -> str | None:
    if any(key.startswith("CODEX_") for key in env):
        return "env:CODEX_*"
    if any("codex" in marker.lower() for marker in process_markers):
        return "process:codex"
    return None


def _matches_claude(env: Mapping[str, str], process_markers: list[str]) -> str | None:
    if any(key.startswith("CLAUDE_") for key in env):
        return "env:CLAUDE_*"
    if any("claude" in marker.lower() for marker in process_markers):
        return "process:claude"
    return None


def _matches_keyword(
    env: Mapping[str, str], process_markers: list[str], keyword: str
) -> str | None:
    if any(keyword in key.lower() for key in env):
        return f"env:*{keyword}*"
    if any(keyword in marker.lower() for marker in process_markers):
        return f"process:{keyword}"
    return None


def _interesting_env_markers(env: Mapping[str, str]) -> list[str]:
    markers: list[str] = []
    for key in sorted(env):
        upper = key.upper()
        if upper.startswith(("CLAUDE_", "CODEX_", "CURSOR_", "AIDER_", "AGENTSYNC_")):
            markers.append(key)
    return markers[:20]


def _normalize_agent_type(value: str | None) -> str:
    if not value:
        return "unknown"
    slug = _safe_slug(value)
    return slug or "unknown"


def _display_name_for(agent_type: str) -> str:
    names = {
        "claude": "Claude",
        "codex": "Codex",
        "cursor": "Cursor",
        "aider": "Aider",
        "unknown": "Unknown Agent",
    }
    return names.get(agent_type, agent_type.title())


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return slug[:48]
