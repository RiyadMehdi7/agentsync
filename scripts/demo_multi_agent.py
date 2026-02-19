#!/usr/bin/env python3
"""Demo: Two agents coordinating through AgentSync's shared SQLite DB.

This simulates what happens when two Claude Code sessions (each with their
own stdio MCP server process) try to work on the same files.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path so we can import without installing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.lock_manager import LockManager
from agentsync_mcp.services.work_queue import WorkQueue

DB_PATH = Path(__file__).parent.parent / "data" / "agentsync.db"


async def simulate_agent(name: str, files: list[str], description: str, db: Database):
    """Simulate one agent's workflow."""
    lm = LockManager(db, cleanup_interval=3600)
    wq = WorkQueue(db)
    await lm.start()

    print(f"\n[{name}] Trying to lock: {files}")
    print(f"[{name}] Reason: {description}")

    locked = []
    blocked = []
    for f in files:
        result = await lm.acquire_lock(f, name, description, ttl_seconds=300)
        if result["success"]:
            locked.append(f)
        else:
            blocked.append(result)

    if locked:
        print(f"[{name}] ✅ Locked: {locked}")
        await wq.create_work_item(name, description, locked)
    if blocked:
        for b in blocked:
            print(f"[{name}] ❌ BLOCKED — '{b.get('locked_by')}' is working on: {b.get('description')}")

    await lm.stop()
    return locked, blocked


async def main():
    # Ensure DB exists
    db = Database(DB_PATH)
    await db.initialize()

    print("=" * 60)
    print("AgentSync Multi-Agent Demo")
    print("=" * 60)

    # --- Agent Alice locks auth files ---
    alice_locked, _ = await simulate_agent(
        "claude-alice",
        ["src/auth.py", "src/login.py"],
        "Fixing authentication bug in login flow",
        db,
    )

    # --- Agent Bob tries the SAME files ---
    _, bob_blocked = await simulate_agent(
        "claude-bob",
        ["src/auth.py", "src/api/users.py"],
        "Adding OAuth2 support",
        db,
    )

    # --- Bob checks what's happening ---
    lm = LockManager(db, cleanup_interval=3600)
    await lm.start()
    wq = WorkQueue(db)

    print(f"\n[claude-bob] Checking all active work...")
    active = await wq.get_active_work()
    for item in active:
        print(f"  → {item['agent_id']}: {item['description']} on {item['files']}")

    # --- Alice finishes and releases ---
    print(f"\n[claude-alice] Done! Releasing locks...")
    for f in alice_locked:
        await lm.release_lock(f, "claude-alice")
    await wq.complete_work("claude-alice", commit_hash="abc123f")
    print(f"[claude-alice] ✅ Released: {alice_locked}")

    # --- Bob retries ---
    bob_locked, _ = await simulate_agent(
        "claude-bob",
        ["src/auth.py", "src/api/users.py"],
        "Adding OAuth2 support",
        db,
    )

    await lm.stop()

    print("\n" + "=" * 60)
    if bob_locked:
        print("✅ SUCCESS — Bob got the lock after Alice released!")
    else:
        print("❌ FAIL — Something went wrong")
    print("=" * 60)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
