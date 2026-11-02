"""
core/voice_agent.py — Always-on Voice Agent Loop for DREX

The always-on voice processing loop.
Runs as a background thread/task, coordinating listener, speaker,
interruption handler, and orchestrator.

States:
- IDLE: waiting for wake word or direct activation
- LISTENING: actively capturing user speech
- PROCESSING: sending to AI/FastRouter
- SPEAKING: playing TTS response
- INTERRUPTED: user spoke during response

Flow:
IDLE -> (wake word detected) -> LISTENING
LISTENING -> (speech detected) -> PROCESSING
PROCESSING -> (response ready) -> SPEAKING
SPEAKING -> (done or interrupted) -> IDLE
INTERRUPTED -> LISTENING (capture new input)
"""

import threading
import time
from enum import Enum
from typing import Callable, Optional
from loguru import logger


class VoiceState(Enum):
    """Voice agent states for the HUD and state machine."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


class VoiceAgent:
    """
    The always-on voice processing loop.
    Runs as a background thread, coordinating all voice modules.

    Wraps the EXISTING orchestrator voice flow — does NOT rewrite it.
    """

    def __init__(self, orchestrator, listener, speaker,
                 interruption_handler=None):
        """
        Args:
            orchestrator: The main Orchestrator instance (with process()).
            listener: The Listener instance.
            speaker: The Speaker instance.
            interruption_handler: Optional InterruptionHandler.
        """
        self._orchestrator = orchestrator
        self._listener = listener
        self._speaker = speaker
        self._interruption = interruption_handler

        # State
        self._state = VoiceState.IDLE
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._wake_word_enabled = False
        self._wake_word_detector = None

        # Public callback for UI state changes
        self.on_state_change: Optional[Callable[[VoiceState], None]] = None

        logger.info("VoiceAgent initialized")

    @property
    def state(self) -> VoiceState:
        with self._lock:
            return self._state

    @state.setter
    def state(self, new_state: VoiceState):
        with self._lock:
            old = self._state
            self._state = new_state
            if old != new_state:
                logger.info("VoiceAgent: {} -> {}", old.value, new_state.value)
                if self.on_state_change:
                    try:
                        self.on_state_change(new_state)
                    except Exception as e:
                        logger.error("State change callback error: {}", e)

    def set_wake_word(self, detector):
        """Set a wake word detector instance."""
        self._wake_word_detector = detector
        self._wake_word_enabled = detector is not None

    def start(self):
        """Start the voice agent background loop."""
        if self._running:
            logger.debug("VoiceAgent already running")
            return

        self._stop_event.clear()
        self._running = True

        # Start interruption monitoring if available
        if self._interruption and self._interruption.is_available:
            self._interruption.calibrate_ambient(duration=1.0)
            self._interruption.start_monitoring()
            # Wire interrupt callback
            self._interruption.on_interrupt = self._on_interrupt

        # Start background loop thread
        self._thread = threading.Thread(
            target=self._agent_loop,
            daemon=True,
            name="drex-voice-agent",
        )
        self._thread.start()
        logger.info("VoiceAgent started")

    def stop(self):
        """Stop cleanly, finish current response first."""
        self._running = False
        self._stop_event.set()
        if self._interruption:
            self._interruption.stop_monitoring()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        self.state = VoiceState.IDLE
        logger.info("VoiceAgent stopped")

    def force_stop(self):
        """Stop immediately, interrupt current response."""
        if self._speaker:
            self._speaker.stop()
        self.stop()

    def activate(self):
        """
        Manually activate listening (e.g. button press or wake word).
        Transitions to LISTENING state immediately.
        """
        logger.info("VoiceAgent activated")
        self.state = VoiceState.LISTENING
        # The agent loop will pick this up

    def _on_interrupt(self):
        """Called by InterruptionHandler when user speaks during TTS."""
        self.state = VoiceState.INTERRUPTED
        # Brief pause, then go back to listening
        threading.Timer(0.3, self._transition_to_listening).start()

    def _transition_to_listening(self):
        if self._running:
            self.state = VoiceState.LISTENING

    def _agent_loop(self):
        """
        Main background loop coordinating the voice pipeline.
        Delegates to the orchestrator's existing voice methods.
        """
        while self._running and not self._stop_event.is_set():
            current_state = self.state

            if current_state == VoiceState.IDLE:
                # Check if wake word is active
                if self._wake_word_enabled and self._wake_word_detector:
                    # Wake word detector fires on_detected -> activate()
                    time.sleep(0.1)
                else:
                    # No wake word — stay responsive but don't listen continuously
                    time.sleep(0.1)

            elif current_state == VoiceState.LISTENING:
                # Use listener.listen_once() for single utterance
                self.state = VoiceState.PROCESSING
                try:
                    if self._listener and self._listener.is_available:
                        text = self._listener.listen_once(timeout=5, phrase_limit=10)
                        if text:
                            # Process through orchestrator
                            self._orchestrator.process(text, voice_response=True)
                        # After processing, go back to IDLE
                except Exception as e:
                    logger.error("VoiceAgent listen error: {}", e)
                finally:
                    if self._running:
                        self.state = VoiceState.IDLE

            elif current_state == VoiceState.PROCESSING:
                # Orchestrator is processing — wait for completion
                time.sleep(0.1)

            elif current_state == VoiceState.SPEAKING:
                # Speaker is active — wait for completion
                time.sleep(0.1)

            elif current_state == VoiceState.INTERRUPTED:
                # Interruption in progress — brief pause
                time.sleep(0.1)

            else:
                time.sleep(0.1)

        logger.info("VoiceAgent loop exiting")