from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Central configuration loaded from environment variables."""

    # Database
    db_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("AGENTSYNC_DB_PATH", "data/agentsync.db")
        )
    )

    # Server
    host: str = field(default_factory=lambda: os.environ.get("AGENTSYNC_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.environ.get("AGENTSYNC_PORT", "8080")))

    # Lock defaults
    default_ttl_seconds: int = field(
        default_factory=lambda: int(os.environ.get("AGENTSYNC_DEFAULT_TTL", "1800"))
    )
    lock_cleanup_interval: int = field(
        default_factory=lambda: int(os.environ.get("AGENTSYNC_CLEANUP_INTERVAL", "60"))
    )

    # Session presence / autodetection
    session_heartbeat_interval: int = field(
        default_factory=lambda: int(
            os.environ.get("AGENTSYNC_SESSION_HEARTBEAT_INTERVAL", "15")
        )
    )
    session_stale_after_seconds: int = field(
        default_factory=lambda: int(
            os.environ.get("AGENTSYNC_SESSION_STALE_AFTER_SECONDS", "90")
        )
    )

    # LLM (for conflict analysis)
    anthropic_api_key: str | None = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY")
    )
    conflict_model: str = field(
        default_factory=lambda: os.environ.get("AGENTSYNC_CONFLICT_MODEL", "claude-sonnet-4-20250514")
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.environ.get("AGENTSYNC_LOG_LEVEL", "INFO")
    )


def get_config() -> Config:
    """Return a Config instance (singleton-friendly via module caching)."""
    return Config()
