"""ScreenAnalyzer — on-demand screen analysis using existing assistant modules."""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

from loguru import logger

from runtime.awareness.awareness_events import ScreenAnalyzed
from runtime.awareness.awareness_models import ScreenContext, WindowInfo
from runtime.event_bus import EventBus


class ScreenAnalyzer:
    """
    On-demand screen analysis using existing ScreenCapture
    and VisionAnalyzer from assistant/.
    Does NOT run continuously — only analyzes when asked.
    Caches last result for 30 seconds to avoid redundant API calls.
    """

    CACHE_TTL = 30  # seconds

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._last_context: Optional[ScreenContext] = None
        self._lock = threading.RLock()
        self.available = False
        self._capture = None
        self._analyzer = None

        # Lazy-load existing assistant modules
        try:
            from assistant.screen_capture import ScreenCapture
            from assistant.vision_analyzer import VisionAnalyzer
            self._capture = ScreenCapture()
            self._analyzer = VisionAnalyzer()
            self.available = True
        except Exception as e:
            logger.warning("ScreenAnalyzer unavailable: {}", e)

        logger.debug("ScreenAnalyzer initialized | available={}", self.available)

    def analyze(
        self, window: Optional[WindowInfo] = None, force: bool = False
    ) -> Optional[ScreenContext]:
        """
        Capture and analyze the current screen.
        If cached result is fresh (< 30s) and force=False -> return cache.
        Otherwise:
          1. capture_full() via ScreenCapture
          2. analyze_screenshot() via VisionAnalyzer
          3. Build ScreenContext from results
          4. Publish awareness.screen_analyzed event
          5. Cache and return result
        Returns None if unavailable.
        """
        if not self.available or self._capture is None or self._analyzer is None:
            return None

        # Check cache freshness
        if not force:
            with self._lock:
                if self._last_context is not None and not self._last_context.is_stale(self.CACHE_TTL):
                    return self._last_context

        start = time.perf_counter()
        try:
            image = self._capture.capture_full()
            if image is None:
                return None

            result = self._analyzer.analyze_screenshot(image)
            elapsed_ms = (time.perf_counter() - start) * 1000

            ctx = ScreenContext(
                window=window,
                description=result.get("description", ""),
                visible_text=result.get("visible_text", ""),
                ui_elements=result.get("ui_elements", []),
                captured_at=datetime.now(),
                analysis_duration_ms=elapsed_ms,
            )

            with self._lock:
                self._last_context = ctx

            self._publish(ScreenAnalyzed, {"context": ctx.to_dict()})
            logger.debug("Screen analyzed | duration={:.0f}ms", elapsed_ms)
            return ctx

        except Exception as exc:
            logger.error("Screen analysis failed: {}", exc)
            return None

    def get_cached(self) -> Optional[ScreenContext]:
        """Return cached context without triggering new analysis."""
        with self._lock:
            return self._last_context

    def describe_current(self) -> str:
        """
        Returns natural language description of current screen.
        Triggers analysis if cache is stale.
        Falls back to active window name if vision unavailable.
        """
        if not self.available:
            return "Screen analysis is not available."

        # Check if cache is fresh
        with self._lock:
            if self._last_context is not None and not self._last_context.is_stale(self.CACHE_TTL):
                ctx = self._last_context
                if ctx.description:
                    return ctx.description
                if ctx.window and ctx.window.title:
                    return f"You have {ctx.window.process_name} open with '{ctx.window.title}'"

        # Trigger new analysis
        ctx = self.analyze(force=True)
        if ctx is not None and ctx.description:
            return ctx.description
        if ctx is not None and ctx.window and ctx.window.title:
            return f"You have {ctx.window.process_name} open with '{ctx.window.title}'"

        return "I cannot see any screen content right now."

    def _publish(self, event_class, payload: dict):
        """Publish awareness event through the EventBus."""
        try:
            event = event_class(source="screen_analyzer", payload=payload)
            self._event_bus.publish(event)
        except Exception as e:
            logger.error("Failed to publish {}: {}", event_class.__name__, e)


__all__ = ["ScreenAnalyzer"]