from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class LockInfo(BaseModel):
    """Represents an active file lock."""

    file_path: str
    agent_id: str
    description: str
    locked_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at
