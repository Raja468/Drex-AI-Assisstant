"""Formats responses from tools and AI into natural language strings."""
from __future__ import annotations
import re
from loguru import logger
from runtime.tools.models import ToolResult
from runtime.planning.plan_models import Plan
from runtime.execution.execution_models import ExecutionResult, StepOutcome


class ResponseService:
    def __init__(self, voice_mode: bool = False):
        self._voice_mode = voice_mode

    def format_tool_result(self, result: ToolResult) -> str:
        if result.success:
            return self._format_success(result)
        return self._format_failure(result)

    def _format_success(self, result: ToolResult) -> str:
        o = result.output.strip()
        if o and o[-1] in (".", "!", "?"):
            return o
        tn = result.metadata.get("tool_name", "")
        m = {
            "browser": "Done.",
            "clipboard": "Clipboard operation complete.",
            "app_launcher": "Done.",
            "screenshot": "Screenshot captured.",
            "file": "File operation complete.",
            "system": "Done.",
        }
        return o or m.get(tn, "Done.")

    def _format_failure(self, result: ToolResult) -> str:
        e = result.error or "An unknown error occurred."
        if "not found" in e.lower() or "permission" in e.lower():
            return e
        return f"I couldn't do that. {e}"

    def format_ai_response(self, text: str) -> str:
        if not text:
            return ""
        if self._voice_mode:
            return self._strip_markdown(text)
        return text.strip()

    def _strip_markdown(self, text: str) -> str:
        text = re.sub(r"\*+", "", text)
        text = re.sub(r"#+\s*", "", text)
        text = re.sub(r"`+", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"---+\n?", "", text)
        return text.strip()

    def format_error(self, error: Exception) -> str:
        return "Sorry, I ran into an unexpected issue. Please try again."

    def set_voice_mode(self, enabled: bool) -> None:
        self._voice_mode = enabled

    # ── New Phase 5C extensions ────────────────────────────────────────
    def format_plan_summary(self, plan: Plan) -> str:
        """Format a human‑readable plan summary for user confirmation.

        Example output:
            "Here is my plan for <title> (3 steps):\n"
            "1. Step one\n"
            "2. Step two\n"
            "3. Step three\n\n"
            "Shall I proceed? (say yes or no)"
        """
        lines = [
            f"Here is my plan for {plan.title} ({len(plan.steps)} steps):"
        ]
        for i, step in enumerate(plan.steps, 1):
            lines.append(f"{i}. {step.title}")
        lines.append("\nShall I proceed? (say yes or no)")
        return "\n".join(lines)

    def format_execution_result(self, result: ExecutionResult) -> str:
        """Format the final execution result for user consumption.

        Success: "Done. Completed all N steps successfully."
        Failure: "I completed X of N steps but failed on <step title>."
        Cancelled: "Task cancelled after X steps."
        """
        if result.cancelled:
            return f"Task cancelled after {result.completed_steps} steps."
        if result.success:
            return f"Done. Completed all {result.total_steps} steps successfully."
        # Failure case
        failed = result.failed_step or "unknown step"
        return (
            f"I completed {result.completed_steps} of {result.total_steps} steps "
            f"but failed on {failed}."
        )

    def format_step_progress(self, outcome: StepOutcome) -> str:
        """Format a progress update for a single step.

        Example: "Step completed: Install Dependencies"
        """
        return f"Step completed: {outcome.step_title}"


__all__ = ["ResponseService"]