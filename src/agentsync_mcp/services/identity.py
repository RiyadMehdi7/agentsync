from __future__ import annotations

import os
import socket
import uuid


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
