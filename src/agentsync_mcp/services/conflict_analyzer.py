from __future__ import annotations

import json
import logging
from typing import Any

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.work_queue import WorkQueue
from agentsync_mcp.utils.config import Config

logger = logging.getLogger(__name__)


class ConflictAnalyzer:
    """LLM-powered semantic conflict detection and merge suggestions."""

    def __init__(self, db: Database, work_queue: WorkQueue, config: Config):
        self.db = db
        self.work_queue = work_queue
        self._model = config.conflict_model
        self._client: Any | None = None

        if config.anthropic_api_key:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            except Exception:
                logger.warning("Failed to initialize Anthropic client")
        else:
            logger.warning("ANTHROPIC_API_KEY not set - conflict analysis disabled")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def detect_semantic_conflicts(
        self,
        agent_id: str,
        files: list[str],
        intent: str,
    ) -> list[dict[str, Any]]:
        """Check for semantic conflicts with other agents' recent work."""
        if not self._client:
            return []

        conflicts: list[dict[str, Any]] = []

        for file_path in files:
            recent = await self.work_queue.get_recent_actions(file_path, hours=24)
            other_actions = [a for a in recent if a["agent_id"] != agent_id]

            for action in other_actions[:3]:
                conflict = await self._check_action_conflict(
                    file_path, intent, action["intent"], action["agent_id"]
                )
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    async def generate_merge_suggestion(
        self,
        file_path: str,
        branch1: str,
        branch2: str,
    ) -> dict[str, Any]:
        """Generate an AI-powered merge strategy for conflicting changes."""
        if not self._client:
            return {
                "strategy": "manual",
                "reasoning": "LLM not available - ANTHROPIC_API_KEY not set",
                "confidence": 0.0,
                "warnings": [],
            }

        prompt = (
            f"Analyze a potential merge conflict in {file_path} between "
            f"branch '{branch1}' and branch '{branch2}'.\n\n"
            "Suggest a merge strategy. Respond with JSON only:\n"
            "{\n"
            '  "strategy": "accept_both" | "accept_branch1" | "accept_branch2" | "manual" | "custom",\n'
            '  "reasoning": "explanation",\n'
            '  "merged_content": "full merged file content if strategy is accept_both or custom, otherwise null",\n'
            '  "confidence": 0.0-1.0,\n'
            '  "warnings": ["list of things to watch for"]\n'
            "}"
        )

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            suggestion = json.loads(response.content[0].text)
            logger.info(
                "Merge suggestion for %s: %s (confidence=%.2f)",
                file_path,
                suggestion["strategy"],
                suggestion.get("confidence", 0),
            )
            return suggestion
        except Exception as exc:
            logger.error("Error generating merge suggestion: %s", exc)
            return {
                "strategy": "manual",
                "reasoning": f"Error: {exc}",
                "confidence": 0.0,
                "warnings": [],
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _check_action_conflict(
        self,
        file_path: str,
        intent1: str,
        intent2: str,
        other_agent_id: str,
    ) -> dict[str, Any] | None:
        prompt = (
            f"Analyze if these two code changes to {file_path} conflict semantically.\n\n"
            f"Change 1 Intent: {intent1}\n\n"
            f"Change 2 Intent: {intent2}\n\n"
            "Do these changes conflict? Consider:\n"
            "- Are they modifying the same functionality?\n"
            "- Could they introduce logical contradictions?\n"
            "- Would both changes be compatible?\n\n"
            "Respond with JSON only:\n"
            "{\n"
            '  "conflicts": boolean,\n'
            '  "severity": "low" | "medium" | "high",\n'
            '  "reason": "brief explanation"\n'
            "}"
        )

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            result = json.loads(response.content[0].text)

            if result.get("conflicts"):
                await self.db.create_conflict(
                    file_path=file_path,
                    agent1_id="current",
                    agent2_id=other_agent_id,
                    conflict_type="semantic",
                    severity=result["severity"],
                    description=result["reason"],
                )
                return {
                    "type": "semantic",
                    "severity": result["severity"],
                    "file": file_path,
                    "conflicting_with": other_agent_id,
                    "reason": result["reason"],
                }
        except Exception as exc:
            logger.error("Error checking conflict: %s", exc)

        return None
