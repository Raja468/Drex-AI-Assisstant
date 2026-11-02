"""
runtime/awareness/awareness_models.py — Data models for environment awareness.

WindowInfo, ScreenContext, and SystemSnapshot dataclasses that
represent the current state of the desktop environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WindowInfo:
    """Information about a single desktop window."""

    title: str = ""
    process_name: str = ""
    pid: int = 0
    is_active: bool = False
    captured_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "process_name": self.process_name,
            "pid": self.pid,
            "is_active": self.is_active,
            "captured_at": self.captured_at.isoformat(),
        }


@dataclass
class ScreenContext:
    """Screen analysis result from ScreenAnalyzer."""

    window: WindowInfo | None = None
    description: str = ""
    visible_text: str = ""
    ui_elements: list[dict] = field(default_factory=list)
    captured_at: datetime = field(default_factory=datetime.now)
    analysis_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window.to_dict() if self.window else None,
            "description": self.description,
            "visible_text": self.visible_text,
            "ui_elements": list(self.ui_elements),
            "captured_at": self.captured_at.isoformat(),
            "analysis_duration_ms": self.analysis_duration_ms,
        }

    def summary(self) -> str:
        """One-line human readable summary of screen context."""
        if self.description:
            return self.description[:120]
        if self.window:
            return f"Active window: {self.window.title}"
        return "No screen context available."

    def is_stale(self, max_age_seconds: int = 30) -> bool:
        """Return True if this context is older than max_age_seconds."""
        elapsed = (datetime.now() - self.captured_at).total_seconds()
        return elapsed > max_age_seconds


@dataclass
class SystemSnapshot:
    """Complete snapshot of system awareness state."""

    active_window: WindowInfo | None = None
    screen_context: ScreenContext | None = None
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    captured_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_window": self.active_window.to_dict() if self.active_window else None,
            "screen_context": self.screen_context.to_dict() if self.screen_context else None,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "captured_at": self.captured_at.isoformat(),
        }

    def describe(self) -> str:
        """Natural language description of system state."""
        parts = []
        if self.active_window and self.active_window.title:
            parts.append(f"You have {self.active_window.process_name} open with '{self.active_window.title}'")
        elif self.active_window:
            parts.append(f"You have {self.active_window.process_name} open")
        if self.cpu_percent > 0 or self.memory_percent > 0:
            parts.append(f"CPU: {self.cpu_percent:.0f}%, RAM: {self.memory_percent:.0f}%")
        if self.screen_context and self.screen_context.description:
            desc = self.screen_context.description[:80]
            parts.append(f"Screen: {desc}")
        return ". ".join(parts) if parts else "System is idle."


__all__ = ["WindowInfo", "ScreenContext", "SystemSnapshot"]