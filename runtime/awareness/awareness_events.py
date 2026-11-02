"""Awareness lifecycle events published through the EventBus."""
from runtime.events import RuntimeEvent


class WindowChanged(RuntimeEvent):
    EVENT_TYPE = "awareness.window_changed"


class ScreenAnalyzed(RuntimeEvent):
    EVENT_TYPE = "awareness.screen_analyzed"


class ContextUpdated(RuntimeEvent):
    EVENT_TYPE = "awareness.context_updated"


class AppOpened(RuntimeEvent):
    EVENT_TYPE = "awareness.app_opened"


class AppClosed(RuntimeEvent):
    EVENT_TYPE = "awareness.app_closed"


__all__ = [
    "AppClosed",
    "AppOpened",
    "ContextUpdated",
    "ScreenAnalyzed",
    "WindowChanged",
]