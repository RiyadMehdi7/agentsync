from __future__ import annotations

import json
import logging
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any

import aiosqlite

from agentsync_mcp.models.lock import LockInfo

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/agentsync.db")


class Database:
    """Async SQLite database layer for AgentSync persistence.

    Holds a single persistent connection with WAL mode for concurrent reads.
    All writes are serialised through that connection.
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create the database file, apply the schema, and open the persistent connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        schema_sql = (
            resources.files("agentsync_mcp.db").joinpath("schema.sql").read_text()
        )

        # Open the persistent connection
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(schema_sql)
        await self._conn.commit()

        logger.info("Database initialized at %s", self.db_path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database not initialized — call initialize() first"
        return self._conn

    # ------------------------------------------------------------------
    # Agent operations
    # ------------------------------------------------------------------

    async def register_agent(self, agent_id: str, agent_type: str = "unknown") -> None:
        await self.conn.execute(
            """
            INSERT INTO agents (agent_id, agent_type)
            VALUES (?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                last_active = CURRENT_TIMESTAMP,
                status = 'active'
            """,
            (agent_id, agent_type),
        )
        await self.conn.commit()

    async def get_all_active_agents(self) -> list[str]:
        cursor = await self.conn.execute(
            "SELECT DISTINCT agent_id FROM agents WHERE status = 'active'"
        )
        rows = await cursor.fetchall()
        return [row["agent_id"] for row in rows]

    # ------------------------------------------------------------------
    # Lock operations
    # ------------------------------------------------------------------

    async def create_lock(self, lock: LockInfo) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO file_locks (file_path, agent_id, description, locked_at, expires_at, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (
                lock.file_path,
                lock.agent_id,
                lock.description,
                lock.locked_at.isoformat(),
                lock.expires_at.isoformat(),
            ),
        )
        await self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def release_lock(self, file_path: str, agent_id: str) -> None:
        await self.conn.execute(
            """
            UPDATE file_locks
            SET status = 'released', released_at = ?
            WHERE file_path = ? AND agent_id = ? AND status = 'active'
            """,
            (datetime.now().isoformat(), file_path, agent_id),
        )
        await self.conn.commit()

    async def update_lock_expiry(self, file_path: str, new_expires_at: datetime) -> None:
        await self.conn.execute(
            """
            UPDATE file_locks SET expires_at = ?
            WHERE file_path = ? AND status = 'active'
            """,
            (new_expires_at.isoformat(), file_path),
        )
        await self.conn.commit()

    async def get_active_locks(self) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT file_path, agent_id, description, locked_at, expires_at
            FROM file_locks WHERE status = 'active'
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def cleanup_expired_locks(self) -> int:
        cursor = await self.conn.execute(
            """
            UPDATE file_locks SET status = 'expired'
            WHERE status = 'active' AND expires_at < ?
            """,
            (datetime.now().isoformat(),),
        )
        await self.conn.commit()
        return cursor.rowcount

    # ------------------------------------------------------------------
    # Work item operations
    # ------------------------------------------------------------------

    async def create_work_item(
        self, agent_id: str, description: str, files: list[str]
    ) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO work_items (agent_id, description, files, status)
            VALUES (?, ?, ?, 'in_progress')
            """,
            (agent_id, description, json.dumps(files)),
        )
        await self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def complete_work_item(
        self, agent_id: str, commit_hash: str | None = None
    ) -> bool:
        cursor = await self.conn.execute(
            """
            SELECT id FROM work_items
            WHERE agent_id = ? AND status = 'in_progress'
            ORDER BY started_at DESC LIMIT 1
            """,
            (agent_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return False

        await self.conn.execute(
            """
            UPDATE work_items
            SET status = 'completed', completed_at = ?, commit_hash = ?
            WHERE id = ?
            """,
            (datetime.now().isoformat(), commit_hash, row["id"]),
        )
        await self.conn.commit()
        return True

    async def get_active_work_items(
        self, agent_id: str | None = None
    ) -> list[dict[str, Any]]:
        if agent_id:
            cursor = await self.conn.execute(
                """
                SELECT id, agent_id, description, files, started_at, status
                FROM work_items WHERE agent_id = ? AND status = 'in_progress'
                ORDER BY started_at DESC
                """,
                (agent_id,),
            )
        else:
            cursor = await self.conn.execute(
                """
                SELECT id, agent_id, description, files, started_at, status
                FROM work_items WHERE status = 'in_progress'
                ORDER BY started_at DESC
                """
            )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["files"] = json.loads(d["files"]) if d["files"] else []
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Action operations
    # ------------------------------------------------------------------

    async def register_action(
        self,
        agent_id: str,
        action_type: str,
        files: list[str],
        intent: str,
    ) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO agent_actions (agent_id, action_type, files, intent)
            VALUES (?, ?, ?, ?)
            """,
            (agent_id, action_type, json.dumps(files), intent),
        )
        await self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    async def get_recent_actions(
        self,
        file_path: str | None = None,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT id, agent_id, action_type, files, intent, created_at
            FROM agent_actions
            WHERE created_at > datetime('now', ?)
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (f"-{hours} hours",),
        )
        rows = await cursor.fetchall()

        actions = []
        for row in rows:
            d = dict(row)
            d["files"] = json.loads(d["files"]) if d["files"] else []
            if file_path is None or file_path in d["files"]:
                actions.append(d)
        return actions

    # ------------------------------------------------------------------
    # Conflict operations
    # ------------------------------------------------------------------

    async def create_conflict(
        self,
        file_path: str,
        agent1_id: str,
        agent2_id: str,
        conflict_type: str,
        severity: str,
        description: str,
    ) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO conflicts
                (file_path, agent1_id, agent2_id, conflict_type, severity, description)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_path, agent1_id, agent2_id, conflict_type, severity, description),
        )
        await self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    async def log_event(
        self, event_type: str, agent_id: str | None, details: dict[str, Any] | None = None
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO event_log (event_type, agent_id, details)
            VALUES (?, ?, ?)
            """,
            (event_type, agent_id, json.dumps(details) if details else None),
        )
        await self.conn.commit()
