from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WorkItem(BaseModel):
    """Represents a tracked unit of work being performed by an agent."""

    id: int | None = None
    agent_id: str
    description: str
    files: list[str] = Field(default_factory=list)
    status: str = "in_progress"  # pending, in_progress, completed, failed
    priority: int = 0
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    commit_hash: Optional[str] = None
