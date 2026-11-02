"""
voice/voice_engine.py — Runtime-owned Voice Subsystem for DREX.

The VoiceEngine becomes the single owner of all voice-related modules,
replacing the ad-hoc lazy-initialisation and state management that was
previously spread across the Orchestrator and GUI.

It wraps (does NOT rewrite) the existing Speaker, Listener,
WakeWordDetector, and InterruptionHandler.  Every existing API on the
Orchestrator and GUI continues to work by delegating through this engine.

Responsibilities:
  - Own the unified voice state model (IDLE → LISTENING → PROCESSING → SPEAKING → ...)
  - Own the lifecycle of Speaker, Listener, WakeWordDetector, InterruptionHandler
  - Publish voice events on the runtime EventBus
  - Provide health() and status() for the runtime diagnostics dashboard
  - Support backward-compatible APIs for the Orchestrator and GUI
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Callable, Optional

from loguru import logger

from voice.listener import Listener
from voice.speaker import Speaker
from voice.interruption_handler import InterruptionHandler


# ─────────────────────────────────────────────────────────────────
#  UNIFIED VOICE STATE
# ─────────────────────────────────────────────────────────────────

class VoiceState(Enum):
    """Single source of truth for voice subsystem state."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


# ─────────────────────────────────────────────────────────────────
#  VOICE ENGINE
# ─────────────────────────────────────────────────────────────────

class VoiceEngine:
    """
    Runtime-owned voice subsystem.

    Wraps the existing ``Speaker``, ``Listener``, ``WakeWordDetector``
    and ``InterruptionHandler``.  The Orchestrator and GUI continue to
    work exactly as before — they gain runtime lifecycle, health checks
    and event publishing for free.
    """

    def __init__(
        self,
        event_bus=None,               # optional runtime EventBus
        on_state_change: Callable[[VoiceState], None] = None,
    ):
        # ── Wrapped modules (lazy-created, *not* replaced) ──
        self._speaker: Optional[Speaker] = None
        self._listener: Optional[Listener] = None
        self._wake_word = None           # WakeWordDetector (lazy)
        self._interruption: Optional[InterruptionHandler] = None

        # ── Event bus (optional — may be None in tests) ────
        self._event_bus = event_bus
        self._on_state_change = on_state_change

        # ── State ──────────────────────────────────────────
        self._state = VoiceState.IDLE
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        # ── Health tracking ────────────────────────────────
        self._health = {
            "mic_available": False,
            "speaker_available": False,
            "wake_word_available": False,
            "state": "idle",
            "last_error": "",
            "errors_since_start": 0,
            "uptime": 0.0,
        }
        self._started_at: Optional[float] = None

        # ── Public callbacks (backward compatibility) ──────
        self.on_state_change: Optional[Callable[[VoiceState], None]] = None

        logger.debug("VoiceEngine created (event_bus={})", event_bus is not None)

    # ──────────────────────────────────────────────────────────
    #  PROPERTIES — expose wrapped modules for backward compat
    # ──────────────────────────────────────────────────────────

    @property
    def speaker(self) -> Optional[Speaker]:
        if self._speaker is None:
            try:
                self._speaker = Speaker()
            except Exception as e:
                logger.error("VoiceEngine: Speaker init failed: {}", e)
                self._health["speaker_available"] = False
        return self._speaker

    @property
    def listener(self) -> Optional[Listener]:
        if self._listener is None:
            try:
                self._listener = Listener()
            except Exception as e:
                logger.error("VoiceEngine: Listener init failed: {}", e)
                self._health["mic_available"] = False
        return self._listener

    @property
    def wake_word(self):
        """Lazy-load WakeWordDetector (pvporcupine or fallback)."""
        if self._wake_word is None:
            try:
                from voice.wake_word import WakeWordDetector
                self._wake_word = WakeWordDetector()
            except Exception as e1:
                logger.debug("VoiceEngine: WakeWordDetector failed, trying SimpleWakeWord: {}", e1)
                try:
                    from voice.wake_word_simple import SimpleWakeWord
                    self._wake_word = SimpleWakeWord()
                except Exception as e2:
                    logger.error("VoiceEngine: All wake word engines failed: {}", e2)
                    self._health["wake_word_available"] = False
        return self._wake_word

    @property
    def interruption(self) -> Optional[InterruptionHandler]:
        if self._interruption is None:
            try:
                self._interruption = InterruptionHandler(
                    speaker=self._speaker or Speaker(),
                    listener=self._listener or Listener(),
                )
            except Exception as e:
                logger.debug("VoiceEngine: InterruptionHandler init failed: {}", e)
        return self._interruption

    @property
    def state(self) -> VoiceState:
        with self._lock:
            return self._state

    @state.setter
    def state(self, new_state: VoiceState):
        with self._lock:
            old = self._state
            self._state = new_state
            self._health["state"] = new_state.value
        if old != new_state:
            logger.info("VoiceEngine: {} -> {}", old.value, new_state.value)
            self._publish_event("voice.state_changed", {"from": old.value, "to": new_state.value})
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception as e:
                    logger.error("State change callback error: {}", e)
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    logger.error("Public state change callback error: {}", e)

    # ──────────────────────────────────────────────────────────
    #  LIFECYCLE — called by RuntimeSupervisor
    # ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the voice engine (idempotent, thread-safe)."""
        with self._lock:
            if self._running:
                logger.debug("VoiceEngine already running")
                return
            self._stop_event.clear()
            self._running = True
            self._started_at = time.time()

        logger.info("VoiceEngine starting")

        # Probe availability for health tracking
        spk = self.speaker
        self._health["speaker_available"] = spk is not None and spk.is_available

        mic = self.listener
        self._health["mic_available"] = mic is not None and mic.is_available

        ww = self.wake_word
        self._health["wake_word_available"] = ww is not None and ww.is_available

        # Start interruption monitor if available
        try:
            ih = self.interruption
            if ih and ih.is_available:
                ih.calibrate_ambient(duration=1.0)
                ih.start_monitoring()
        except Exception as e:
            logger.debug("VoiceEngine: interruption monitor start skipped: {}", e)

        self.state = VoiceState.IDLE
        self._publish_event("voice.started", {})
        logger.info("VoiceEngine started")

    def stop(self) -> None:
        """Stop the voice engine cleanly (idempotent, thread-safe)."""
        with self._lock:
            if not self._running:
                logger.debug("VoiceEngine already stopped")
                return
            self._running = False
            self._stop_event.set()

        logger.info("VoiceEngine stopping")

        # Stop interruption monitor
        if self._interruption is not None:
            try:
                self._interruption.stop_monitoring()
            except Exception as e:
                logger.debug("VoiceEngine: interruption stop error: {}", e)

        # Stop wake word
        if self._wake_word is not None:
            try:
                self._wake_word.stop()
            except Exception as e:
                logger.debug("VoiceEngine: wake word stop error: {}", e)

        # Stop listener
        if self._listener is not None:
            try:
                self._listener.stop_continuous()
            except Exception as e:
                logger.debug("VoiceEngine: listener stop error: {}", e)

        # Stop speaker
        if self._speaker is not None:
            try:
                self._speaker.stop()
            except Exception as e:
                logger.debug("VoiceEngine: speaker stop error: {}", e)

        self.state = VoiceState.IDLE
        self._publish_event("voice.stopped", {})
        logger.info("VoiceEngine stopped")

    def shutdown(self) -> None:
        """Full shutdown — release all resources (called by RuntimeSupervisor)."""
        logger.info("VoiceEngine shutting down")

        # First stop everything
        self.stop()

        # Shutdown wrapped modules
        if self._speaker is not None:
            try:
                self._speaker.shutdown()
            except Exception as e:
                logger.debug("VoiceEngine: speaker shutdown error: {}", e)

        if self._listener is not None:
            try:
                self._listener.shutdown()
            except Exception as e:
                logger.debug("VoiceEngine: listener shutdown error: {}", e)

        if self._wake_word is not None:
            try:
                self._wake_word.shutdown()
            except Exception as e:
                logger.debug("VoiceEngine: wake word shutdown error: {}", e)

        if self._interruption is not None:
            try:
                self._interruption.shutdown()
            except Exception as e:
                logger.debug("VoiceEngine: interruption shutdown error: {}", e)

        self._health["state"] = "shutdown"
        self._health["uptime"] = (time.time() - self._started_at) if self._started_at else 0.0
        logger.info("VoiceEngine shutdown complete")

    # ──────────────────────────────────────────────────────────
    #  VOICE OPERATIONS — used by Orchestrator and GUI
    # ──────────────────────────────────────────────────────────

    def start_listening(self) -> None:
        """
        Start voice listening (wake word or continuous mode).

        Delegates to the Orchestrator's existing voice flow
        but owns the state transitions and event publishing.
        """
        self.state = VoiceState.LISTENING
        self._publish_event("voice.listening_started", {})

    def stop_listening(self) -> None:
        """Stop voice listening."""
        self.state = VoiceState.IDLE
        self._publish_event("voice.listening_stopped", {})

    def interrupt(self) -> None:
        """
        Interrupt current speech playback immediately.
        Called by InterruptionHandler or GUI.
        """
        if self._speaker is not None:
            try:
                self._speaker.stop()
            except Exception as e:
                logger.error("VoiceEngine: interrupt speaker stop error: {}", e)
        self.state = VoiceState.INTERRUPTED
        self._publish_event("voice.interrupted", {})
        logger.info("VoiceEngine: interrupted")

    def speak(self, text: str, priority: bool = False) -> None:
        """Queue text for TTS. Delegates to Speaker.speak()."""
        self.state = VoiceState.SPEAKING
        self._publish_event("voice.speech_started", {"text_length": len(text)})
        if self._speaker is not None:
            self._speaker.speak(text, priority=priority)

    def on_speech_finished(self) -> None:
        """Called when TTS playback completes (transition back to idle)."""
        self.state = VoiceState.IDLE
        self._publish_event("voice.speech_finished", {})

    def on_transcript(self, text: str) -> None:
        """Called when a voice transcript is received."""
        self._publish_event("voice.transcript", {"text": text})
        self.state = VoiceState.PROCESSING

    def on_response_complete(self) -> None:
        """Called when orchestrator finishes processing."""
        self.state = VoiceState.IDLE

    # ──────────────────────────────────────────────────────────
    #  WAKE WORD
    # ──────────────────────────────────────────────────────────

    def start_wake_word(self, callback: Callable[[], None] = None) -> None:
        """Start wake word detection."""
        ww = self.wake_word
        if ww is None or not ww.is_available:
            logger.warning("VoiceEngine: wake word not available")
            return

        def _on_wake():
            logger.info("🔊 Wake word detected (via VoiceEngine)")
            self._publish_event("voice.wake_word_detected", {})
            if callback:
                callback()

        ww.start(callback=_on_wake)

    def stop_wake_word(self) -> None:
        """Stop wake word detection."""
        if self._wake_word is not None:
            try:
                self._wake_word.stop()
            except Exception as e:
                logger.debug("VoiceEngine: wake word stop error: {}", e)

    @property
    def wake_word_available(self) -> bool:
        ww = self._wake_word or self.wake_word
        return ww is not None and ww.is_available

    # ──────────────────────────────────────────────────────────
    #  HEALTH & DIAGNOSTICS
    # ──────────────────────────────────────────────────────────

    def health(self) -> dict:
        """
        Return a JSON-safe health snapshot for the runtime dashboard.

        Returns:
            Dict with availability flags, current state, and error info.
        """
        with self._lock:
            speaker_avail = self._speaker is not None and self._speaker.is_available
            mic_avail = self._listener is not None and self._listener.is_available
            ww_avail = self._health["wake_word_available"]

            return {
                "microphone_available": mic_avail,
                "speaker_available": speaker_avail,
                "wake_word_available": ww_avail,
                "state": self._state.value,
                "is_running": self._running,
                "is_speaking": self._speaker.is_speaking if self._speaker else False,
                "is_listening": self._listener.is_listening if self._listener else False,
                "last_error": self._health["last_error"],
                "errors_since_start": self._health["errors_since_start"],
                "uptime_seconds": (time.time() - self._started_at) if self._started_at else 0.0,
            }

    def status(self) -> dict:
        """Alias for health(), used by runtime diagnostics."""
        return self.health()

    # ──────────────────────────────────────────────────────────
    #  EVENT PUBLISHING
    # ──────────────────────────────────────────────────────────

    def _publish_event(self, event_type: str, payload: dict = None) -> None:
        """Publish a voice event to the runtime EventBus if available."""
        if self._event_bus is None:
            return
        try:
            from runtime.events import Event
            self._event_bus.publish(
                Event(
                    type=event_type,
                    source="voice_engine",
                    payload=payload or {},
                )
            )
        except Exception as e:
            logger.debug("VoiceEngine: event publish error: {}", e)


__all__ = [
    "VoiceEngine",
    "VoiceState",
]