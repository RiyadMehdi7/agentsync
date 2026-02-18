from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Conflict(BaseModel):
    """Represents a detected conflict between two agents' work."""

    id: int | None = None
    file_path: str
    agent1_id: str
    agent2_id: str
    conflict_type: str  # textual, semantic
    severity: str = "medium"  # low, medium, high
    description: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolution_strategy: Optional[str] = None
    status: str = "open"  # open, resolved, ignored
