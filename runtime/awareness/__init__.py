"""
runtime/awareness/ -- Environment awareness subsystem for DREX.

Provides passive window tracking, on-demand screen analysis, and
system snapshot capabilities. Awareness data is READ-ONLY from
the orchestrator perspective — it queries, never writes.
"""

from runtime.awareness.awareness_engine import AwarenessEngine
from runtime.awareness.awareness_events import (
    AppClosed,
    AppOpened,
    ContextUpdated,
    ScreenAnalyzed,
    WindowChanged,
)
from runtime.awareness.awareness_models import ScreenContext, SystemSnapshot, WindowInfo
from runtime.awareness.screen_analyzer import ScreenAnalyzer
from runtime.awareness.window_tracker import WindowTracker

__all__ = [
    "AppClosed",
    "AppOpened",
    "AwarenessEngine",
    "ContextUpdated",
    "ScreenAnalyzed",
    "ScreenAnalyzer",
    "ScreenContext",
    "SystemSnapshot",
    "WindowChanged",
    "WindowInfo",
    "WindowTracker",
]