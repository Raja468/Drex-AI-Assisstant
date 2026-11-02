"""Execution data models for task execution tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ExecutionState(Enum):
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class StepOutcome:
    step_id: str
    step_title: str
    success: bool
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_title": self.step_title,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ExecutionResult:
    task_id: str
    plan_id: str
    success: bool
    total_steps: int
    completed_steps: int
    failed_step: Optional[str] = None
    outcomes: list[StepOutcome] = field(default_factory=list)
    duration_ms: float = 0.0
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "plan_id": self.plan_id,
            "success": self.success,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_step": self.failed_step,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "duration_ms": self.duration_ms,
            "cancelled": self.cancelled,
        }

    def summary(self) -> str:
        if self.cancelled:
            return f"Task cancelled after {self.completed_steps} steps."
        if self.success:
            return f"Done. Completed all {self.total_steps} steps successfully."
        return (f"I completed {self.completed_steps} of {self.total_steps} steps "
                f"but failed on {self.failed_step}.")


__all__ = ["ExecutionResult", "ExecutionState", "StepOutcome"]