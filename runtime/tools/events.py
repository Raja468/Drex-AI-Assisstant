from runtime.events import RuntimeEvent

class ToolStarted(RuntimeEvent):
    EVENT_TYPE = "tool.started"

class ToolCompleted(RuntimeEvent):
    EVENT_TYPE = "tool.completed"

class ToolFailed(RuntimeEvent):
    EVENT_TYPE = "tool.failed"

class ToolPermissionRequired(RuntimeEvent):
    EVENT_TYPE = "tool.permission_required"

__all__ = ["ToolCompleted", "ToolFailed", "ToolPermissionRequired", "ToolStarted"]
