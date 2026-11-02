"""Execution lifecycle events published through the EventBus."""
from runtime.events import RuntimeEvent


class ExecutionStarted(RuntimeEvent):
    EVENT_TYPE = "execution.started"


class ExecutionStepStarted(RuntimeEvent):
    EVENT_TYPE = "execution.step_started"


class ExecutionStepCompleted(RuntimeEvent):
    EVENT_TYPE = "execution.step_completed"


class ExecutionStepFailed(RuntimeEvent):
    EVENT_TYPE = "execution.step_failed"


class ExecutionCompleted(RuntimeEvent):
    EVENT_TYPE = "execution.completed"


class ExecutionFailed(RuntimeEvent):
    EVENT_TYPE = "execution.failed"


class ExecutionCancelled(RuntimeEvent):
    EVENT_TYPE = "execution.cancelled"


__all__ = [
    "ExecutionCancelled", "ExecutionCompleted", "ExecutionFailed",
    "ExecutionStarted", "ExecutionStepCompleted", "ExecutionStepFailed",
    "ExecutionStepStarted",
]