"""
runtime/execution/ -- Execution engine foundation for DREX.

Connects Planner → TaskManager → ToolRouter → ResponseService.
Sequential execution only. No autonomous execution.
"""

from runtime.execution.execution_engine import ExecutionEngine
from runtime.execution.execution_events import (
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
    ExecutionStepCompleted,
    ExecutionStepFailed,
    ExecutionStepStarted,
)
from runtime.execution.execution_models import (
    ExecutionResult,
    ExecutionState,
    StepOutcome,
)

__all__ = [
    "ExecutionCancelled",
    "ExecutionCompleted",
    "ExecutionEngine",
    "ExecutionFailed",
    "ExecutionStarted",
    "ExecutionState",
    "ExecutionStepCompleted",
    "ExecutionStepFailed",
    "ExecutionStepStarted",
    "ExecutionResult",
    "StepOutcome",
]