"""Rule-based goal decomposer — no LLM, no AI calls, no tool execution."""
from __future__ import annotations

from typing import Any
from loguru import logger


class GoalDecomposer:
    """
    Converts common high-level goals into ordered step lists.
    Rule-based only — no LLM, no AI calls, no tool execution.
    Uses keyword matching against a template library.
    """

    TEMPLATES: dict[str, list[str]] = {
        "website": [
            "Define requirements",
            "Create project structure",
            "Build UI components",
            "Test website",
            "Deploy website",
        ],
        "react": [
            "Define requirements",
            "Create React project",
            "Install dependencies",
            "Build UI components",
            "Test application",
            "Deploy application",
        ],
        "python": [
            "Define requirements",
            "Create project structure",
            "Implement features",
            "Write tests",
            "Package application",
        ],
        "api": [
            "Define API requirements",
            "Design endpoints",
            "Implement API",
            "Write tests",
            "Deploy API",
        ],
        "documentation": [
            "Gather information",
            "Create outline",
            "Write documentation",
            "Review content",
            "Publish documentation",
        ],
        "database": [
            "Define schema",
            "Create database",
            "Implement migrations",
            "Seed data",
            "Verify setup",
        ],
        "default": [
            "Analyze requirements",
            "Create plan",
            "Execute steps",
            "Verify results",
            "Complete task",
        ],
    }

    def __init__(self):
        self._templates: dict[str, list[str]] = dict(self.TEMPLATES)
        logger.debug("GoalDecomposer initialized with {} templates", len(self._templates))

    def decompose(self, goal: str) -> list[str]:
        """
        Match goal text against TEMPLATES keys (case-insensitive).
        Uses longest-key-first matching to avoid short-key false matches.
        Fall back to "default" if no match found.
        """
        if not goal or not goal.strip():
            logger.debug("Empty goal — returning default steps")
            return list(self._templates["default"])

        goal_lower = goal.lower().strip()
        goal_words = set(goal_lower.split())

        # First pass: exact word match — sort by length descending so more specific
        # keys (e.g. "documentation") match before generic ones (e.g. "api" or "website")
        non_default_keys = sorted(
            [k for k in self._templates if k != "default"],
            key=lambda k: len(k),
            reverse=True,
        )
        for key in non_default_keys:
            if key in goal_words:
                logger.debug("Goal decomposed (word match) using template '{}': '{}'", key, goal)
                return list(self._templates[key])

        # Second pass: substring matching (same descending length order)
        for key in non_default_keys:
            if key in goal_lower:
                logger.debug("Goal decomposed (substring) using template '{}': '{}'", key, goal)
                return list(self._templates[key])

        logger.debug("No template matched — returning default steps for: '{}'", goal)
        return list(self._templates["default"])

    def decompose_or_none(self, goal: str) -> list[str] | None:
        """
        Like decompose() but returns None when only the 'default' template matches.

        This prevents false-positive planning for normal chat messages
        that happen to be long enough to trigger the default 5-step template.
        Only goals matching a SPECIFIC domain template (website, react,
        python, api, documentation, database) return steps.
        """
        if not goal or not goal.strip():
            return None

        goal_lower = goal.lower().strip()
        goal_words = set(goal_lower.split())

        non_default = sorted(
            [k for k in self._templates if k != "default"],
            key=lambda k: len(k),
            reverse=True,
        )
        for key in non_default:
            if key in goal_words or key in goal_lower:
                logger.debug("Goal matched specific template '{}': '{}'", key, goal)
                return list(self._templates[key])
        return None

    def get_template_names(self) -> list[str]:
        """Return list of available template keys."""
        return [k for k in self._templates if k != "default"]

    def add_template(self, key: str, steps: list[str]) -> None:
        """Allow runtime addition of new templates."""
        if not key or not key.strip():
            raise ValueError("Template key must be non-empty")
        if not steps:
            raise ValueError("Template steps must be non-empty")
        self._templates[key.strip().lower()] = list(steps)
        logger.info("GoalDecomposer template added: '{}' ({} steps)", key, len(steps))


__all__ = ["GoalDecomposer"]