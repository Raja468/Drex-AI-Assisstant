"""Task lifecycle events published through the EventBus."""
from runtime.events import RuntimeEvent


class TaskCreated(RuntimeEvent):
    EVENT_TYPE = "task.created"


class TaskUpdated(RuntimeEvent):
    EVENT_TYPE = "task.updated"


class TaskStarted(RuntimeEvent):
    EVENT_TYPE = "task.started"


class TaskPaused(RuntimeEvent):
    EVENT_TYPE = "task.paused"


class TaskResumed(RuntimeEvent):
    EVENT_TYPE = "task.resumed"


class TaskCompleted(RuntimeEvent):
    EVENT_TYPE = "task.completed"


class TaskFailed(RuntimeEvent):
    EVENT_TYPE = "task.failed"


class TaskCancelled(RuntimeEvent):
    EVENT_TYPE = "task.cancelled"


__all__ = [
    "TaskCancelled", "TaskCompleted", "TaskCreated",
    "TaskFailed", "TaskPaused", "TaskResumed",
    "TaskStarted", "TaskUpdated",
]