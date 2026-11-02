"""AwarenessEngine — central coordinator for all awareness subsystems."""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

from loguru import logger
import psutil

from runtime.awareness.awareness_events import ContextUpdated
from runtime.awareness.awareness_models import ScreenContext, SystemSnapshot, WindowInfo
from runtime.awareness.screen_analyzer import ScreenAnalyzer
from runtime.awareness.window_tracker import WindowTracker
from runtime.event_bus import EventBus


class AwarenessEngine:
    """
    Central coordinator for all awareness subsystems.
    Owns WindowTracker and ScreenAnalyzer.
    Maintains current SystemSnapshot.
    Refreshes snapshot every 5 seconds passively.
    Provides context injection for AI prompts.
    """

    SNAPSHOT_INTERVAL = 10.0  # seconds (increased from 5s to reduce CPU)

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._window_tracker = WindowTracker(event_bus)
        self._screen_analyzer = ScreenAnalyzer(event_bus)
        self._snapshot: Optional[SystemSnapshot] = None
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        logger.debug("AwarenessEngine initialized")

    @property
    def window_tracker(self) -> WindowTracker:
        return self._window_tracker

    @property
    def screen_analyzer(self) -> ScreenAnalyzer:
        return self._screen_analyzer

    def get_snapshot(self) -> Optional[SystemSnapshot]:
        """Return current SystemSnapshot (may be up to 5s old)."""
        with self._lock:
            return self._snapshot

    def get_context_for_prompt(self) -> str:
        """
        Returns a brief context string for injection into AI prompts.
        Example:
          "Current context: VS Code is open with a Python file.
           CPU: 23%, RAM: 61%."
        Returns empty string if no context available.
        Maximum 150 characters — keep it brief for token efficiency.
        """
        snapshot = self.get_snapshot()
        if snapshot is None:
            return ""
        text = snapshot.describe()
        if len(text) > 150:
            text = text[:147] + "..."
        return text

    def analyze_screen_now(self) -> Optional[ScreenContext]:
        """Force immediate screen analysis (bypasses cache)."""
        window = self._window_tracker.get_current()
        return self._screen_analyzer.analyze(window=window, force=True)

    def describe_screen(self) -> str:
        """
        Returns natural language description of what is on screen.
        Used when user asks 'what am I looking at?'
        """
        # Trigger fresh analysis
        ctx = self.analyze_screen_now()
        if ctx is not None and ctx.description:
            return ctx.description
        if ctx is not None and ctx.window and ctx.window.title:
            return f"You have {ctx.window.process_name} open with '{ctx.window.title}'"

        # Fallback to window tracker
        window = self._window_tracker.get_current()
        if window and window.title:
            return f"You are using {window.process_name} — '{window.title}'"

        return "I cannot determine what you're looking at right now."

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Start WindowTracker, ScreenAnalyzer, snapshot loop."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()

        # Start window tracker background polling
        self._window_tracker.start()

        # Start snapshot refresh loop
        self._thread = threading.Thread(
            target=self._snapshot_loop,
            daemon=True,
            name="drex-awareness-engine",
        )
        self._thread.start()
        logger.info("AwarenessEngine started | snapshot_interval={}s", self.SNAPSHOT_INTERVAL)

    def stop(self) -> None:
        """Stop all subsystems cleanly."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        self._stop_event.set()
        self._window_tracker.stop()

        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("AwarenessEngine stopped")

    # ── Internal ──────────────────────────────────────────────

    def _refresh_snapshot(self) -> None:
        """
        Build new SystemSnapshot from:
          - WindowTracker.get_current()
          - ScreenAnalyzer.get_cached() (no new analysis)
          - psutil.cpu_percent() and psutil.virtual_memory()
        Publish awareness.context_updated event.
        """
        try:
            window = self._window_tracker.get_current()
            screen_ctx = self._screen_analyzer.get_cached()
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent

            snapshot = SystemSnapshot(
                active_window=window,
                screen_context=screen_ctx,
                cpu_percent=cpu,
                memory_percent=mem,
                captured_at=datetime.now(),
            )

            with self._lock:
                self._snapshot = snapshot

            self._publish(ContextUpdated, {"snapshot": snapshot.to_dict()})
        except Exception as exc:
            logger.debug("Snapshot refresh failed: {}", exc)

    def _snapshot_loop(self) -> None:
        """Background thread — calls _refresh_snapshot() every 5s."""
        # Give subsystems a moment to collect initial data
        self._stop_event.wait(1.0)

        while self._running and not self._stop_event.is_set():
            self._refresh_snapshot()
            self._stop_event.wait(self.SNAPSHOT_INTERVAL)

    def _publish(self, event_class, payload: dict):
        """Publish awareness event through the EventBus."""
        try:
            event = event_class(source="awareness_engine", payload=payload)
            self._event_bus.publish(event)
        except Exception as e:
            logger.error("Failed to publish {}: {}", event_class.__name__, e)


__all__ = ["AwarenessEngine"]