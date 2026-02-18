from __future__ import annotations

import pytest

from agentsync_mcp.services.conflict_analyzer import ConflictAnalyzer


@pytest.mark.asyncio
class TestConflictAnalyzer:
    async def test_no_conflicts_without_api_key(
        self, conflict_analyzer: ConflictAnalyzer
    ) -> None:
        """Without ANTHROPIC_API_KEY the analyzer gracefully returns no conflicts."""
        conflicts = await conflict_analyzer.detect_semantic_conflicts(
            agent_id="agent-1",
            files=["src/auth.py"],
            intent="Fix login bug",
        )
        assert conflicts == []

    async def test_merge_suggestion_without_api_key(
        self, conflict_analyzer: ConflictAnalyzer
    ) -> None:
        suggestion = await conflict_analyzer.generate_merge_suggestion(
            "src/auth.py", "branch-a", "branch-b"
        )
        assert suggestion["strategy"] == "manual"
        assert suggestion["confidence"] == 0.0
