from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Agent(BaseModel):
    """Represents a connected AI coding agent."""

    agent_id: str
    agent_type: str = "unknown"  # cursor, claude_code, aider, manual
    user_id: Optional[str] = None
    first_seen: datetime = Field(default_factory=datetime.now)
    last_active: datetime = Field(default_factory=datetime.now)
    status: str = "active"  # active, inactive
