"""WindowTracker — polls active window every 2 seconds, detects changes."""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

from loguru import logger

from runtime.awareness.awareness_events import WindowChanged
from runtime.awareness.awareness_models import WindowInfo
from runtime.event_bus import EventBus


class WindowTracker:
    """
    Polls the active window every 2 seconds using pygetwindow.
    Detects when the active window changes.
    Publishes awareness.window_changed event on change.
    Runs in background thread — never blocks main thread.
    """

    POLL_INTERVAL = 2.0

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._current_window: Optional[WindowInfo] = None
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        logger.debug("WindowTracker initialized")

    def get_active_window(self) -> Optional[WindowInfo]:
        """
        Get current active window info using pygetwindow.
        Returns WindowInfo or None if unavailable.
        Uses psutil to get process_name from pid.
        Never raise — return None on any error.
        """
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active is None:
                return None

            title = active.title or ""
            pid = 0
            process_name = ""

            try:
                import psutil
                # pygetwindow does not expose pid directly on Windows;
                # we can try GetWindowThreadProcessId via ctypes
                import ctypes
                from ctypes import wintypes
                try:
                    user32 = ctypes.windll.user32
                    hwnd = active._hWnd if hasattr(active, '_hWnd') else 0
                    if hwnd:
                        pid_c = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
                        pid = pid_c.value
                        if pid:
                            proc = psutil.Process(pid)
                            process_name = proc.name() or ""
                except Exception:
                    pass
            except Exception:
                pass

            return WindowInfo(
                title=title,
                process_name=process_name,
                pid=pid,
                is_active=True,
                captured_at=datetime.now(),
            )
        except Exception as exc:
            logger.debug("get_active_window failed: {}", exc)
            return None

    def get_current(self) -> Optional[WindowInfo]:
        """Return last known active window (no poll)."""
        with self._lock:
            return self._current_window

    def start(self) -> None:
        """Start background polling thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="drex-window-tracker",
        )
        self._thread.start()
        logger.info("WindowTracker started | poll_interval={}s", self.POLL_INTERVAL)

    def stop(self) -> None:
        """Stop polling thread cleanly."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("WindowTracker stopped")

    def _publish(self, event_class, payload: dict):
        """Publish awareness event through the EventBus."""
        try:
            event = event_class(source="window_tracker", payload=payload)
            self._event_bus.publish(event)
        except Exception as e:
            logger.error("Failed to publish {}: {}", event_class.__name__, e)

    def _poll_loop(self) -> None:
        """
        Loop every POLL_INTERVAL seconds.
        Call get_active_window().
        If window title changed -> update self._current_window
        -> publish awareness.window_changed event.
        """
        while self._running and not self._stop_event.is_set():
            try:
                window = self.get_active_window()
                if window is not None:
                    with self._lock:
                        prev = self._current_window
                        title_changed = (
                            prev is None
                            or prev.title != window.title
                            or prev.process_name != window.process_name
                        )

                        if title_changed:
                            prev_pid = prev.pid if prev else 0
                            self._current_window = window
                            self._publish(
                                WindowChanged,
                                {
                                    "window": window.to_dict(),
                                    "previous_title": prev.title if prev else "",
                                },
                            )
                            if prev_pid and prev_pid != window.pid:
                                self._publish_window_event(window, prev)
            except Exception as exc:
                logger.debug("WindowTracker poll error: {}", exc)

            self._stop_event.wait(self.POLL_INTERVAL)

    def _publish_window_event(self, window: WindowInfo, prev: WindowInfo) -> None:
        """Publish app_opened / app_closed events when pid changes."""
        try:
            self._publish(
                self._import_event("AppOpened"),
                {"window": window.to_dict()},
            )
            self._publish(
                self._import_event("AppClosed"),
                {"window": prev.to_dict()},
            )
        except Exception:
            pass

    @staticmethod
    def _import_event(name: str):
        """Lazy import to avoid circular dependency."""
        from runtime.awareness.awareness_events import AppClosed, AppOpened
        return {"AppOpened": AppOpened, "AppClosed": AppClosed}[name]


__all__ = ["WindowTracker"]