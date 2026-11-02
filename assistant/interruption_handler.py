# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/interruption_handler.py  —  Speech Interruption
#
#  Handles speech interruption (barge-in) scenarios.
#
#  When the user speaks while DREX is speaking:
#  1. Immediately stop TTS playback
#  2. Cancel pending AI generation
#  3. Process new user input
#  4. Resume normal flow
#
#  This creates a natural conversational experience where
#  the user can interrupt DREX just like interrupting a
#  real person.
# ============================================================

import threading
import time
from typing import Callable, Optional
from loguru import logger

from assistant.state_engine import StateEngine, AssistantState


class InterruptionHandler:
    """
    Handles speech interruption (barge-in) scenarios.
    
    Coordinates between:
    - Voice listener (detects user speech)
    - Voice speaker (stops TTS)
    - Orchestrator (cancels generation)
    - State engine (tracks state)
    
    Usage:
        handler = InterruptionHandler(state_engine)
        handler.set_speaker(speaker)
        handler.set_cancel_callback(orchestrator.cancel_pending_generation)
        
        # When speech is detected during TTS:
        handler.on_speech_detected("user text")
    """
    
    def __init__(self, state_engine: StateEngine):
        self.state_engine = state_engine
        self._lock = threading.RLock()
        
        # Component references (set via setters)
        self._speaker = None
        self._listener = None
        
        # Callbacks
        self._on_interrupt: Optional[Callable[[str], None]] = None
        self._cancel_generation: Optional[Callable] = None
        
        # Interruption state
        self._is_speaking = False
        self._interruption_count = 0
        self._last_interrupt_time = 0.0
        self._min_interrupt_interval = 0.5  # Prevent rapid interrupts
        
        # Configuration
        self._enabled = True
        self._auto_cancel = True  # Auto-cancel generation on interrupt
        
        logger.debug("InterruptionHandler initialized | enabled={}", self._enabled)
    
    # ── Component Setters ─────────────────────────────────────
    
    def set_speaker(self, speaker):
        """
        Set the speaker component for TTS control.
        
        The speaker must have a stop() method.
        """
        with self._lock:
            self._speaker = speaker
            logger.debug("Speaker set for interruption handling")
    
    def set_listener(self, listener):
        """
        Set the listener component for speech detection.
        
        Used to check if listener is active during interruption.
        """
        with self._lock:
            self._listener = listener
            logger.debug("Listener set for interruption handling")
    
    # ── Callback Setters ──────────────────────────────────────
    
    def set_interrupt_callback(self, callback: Callable[[str], None]):
        """
        Set callback for when interruption occurs.
        
        Callback signature: callback(interrupted_text)
        Called with the text that was being spoken when interrupted.
        """
        with self._lock:
            self._on_interrupt = callback
    
    def set_cancel_callback(self, callback: Callable):
        """
        Set callback to cancel pending AI generation.
        
        This is typically orchestrator.cancel_pending_generation()
        """
        with self._lock:
            self._cancel_generation = callback
    
    # ── Interruption Handling ─────────────────────────────────
    
    def on_speech_detected(self, user_text: str) -> bool:
        """
        Handle speech detection during TTS playback.
        
        This is the main entry point for interruption handling.
        Called by the voice listener when speech is detected.
        
        Args:
            user_text: The transcribed user speech
            
        Returns:
            True if this was an interruption, False otherwise
        """
        with self._lock:
            # Check if interruption is enabled
            if not self._enabled:
                logger.debug("Interruption disabled, ignoring speech")
                return False
            
            # Check if we're actually speaking
            if not self._is_speaking:
                logger.debug("Not speaking, not an interruption")
                return False
            
            # Check state engine
            if not self.state_engine.can_interrupt():
                logger.debug("State doesn't allow interruption")
                return False
            
            # Check minimum interval
            now = time.time()
            if now - self._last_interrupt_time < self._min_interrupt_interval:
                logger.debug("Too soon after last interrupt")
                return False
            
            # This is a valid interruption!
            logger.info("🔊 Interruption detected: '{}'", user_text[:50])
            
            # Perform interruption
            self._perform_interruption(user_text)
            
            return True
    
    def _perform_interruption(self, user_text: str):
        """Execute the interruption sequence."""
        with self._lock:
            self._interruption_count += 1
            self._last_interrupt_time = time.time()
            
            # Step 1: Stop TTS immediately
            self._stop_speech()
            
            # Step 2: Cancel pending generation
            if self._auto_cancel:
                self._cancel_generation_pending()
            
            # Step 3: Update state
            self.state_engine.state = AssistantState.LISTENING
            
            # Step 4: Notify callback
            if self._on_interrupt:
                try:
                    self._on_interrupt(user_text)
                except Exception as e:
                    logger.error("Interrupt callback error: {}", e)
    
    def _stop_speech(self):
        """Stop TTS playback immediately."""
        if self._speaker:
            try:
                self._speaker.stop()
                logger.debug("TTS stopped due to interruption")
            except Exception as e:
                logger.error("Failed to stop TTS: {}", e)
        
        self._is_speaking = False
    
    def _cancel_generation_pending(self):
        """Cancel any pending AI generation."""
        if self._cancel_generation:
            try:
                self._cancel_generation()
                logger.debug("Generation cancelled due to interruption")
            except Exception as e:
                logger.error("Failed to cancel generation: {}", e)
    
    # ── Speaking State Management ─────────────────────────────
    
    def start_speaking(self):
        """
        Mark that DREX has started speaking.
        
        Call this when TTS playback begins.
        """
        with self._lock:
            self._is_speaking = True
            logger.debug("Interruption handler: speaking started")
    
    def stop_speaking(self):
        """
        Mark that DREX has stopped speaking.
        
        Call this when TTS playback ends (naturally or interrupted).
        """
        with self._lock:
            self._is_speaking = False
            logger.debug("Interruption handler: speaking stopped")
    
    def is_speaking(self) -> bool:
        """Check if DREX is currently speaking."""
        with self._lock:
            return self._is_speaking
    
    # ── Configuration ─────────────────────────────────────────
    
    def enable(self):
        """Enable interruption handling."""
        with self._lock:
            self._enabled = True
            logger.info("Interruption handling enabled")
    
    def disable(self):
        """Disable interruption handling."""
        with self._lock:
            self._enabled = False
            logger.info("Interruption handling disabled")
    
    def is_enabled(self) -> bool:
        """Check if interruption handling is enabled."""
        with self._lock:
            return self._enabled
    
    def set_auto_cancel(self, enabled: bool):
        """
        Enable/disable automatic generation cancellation.
        
        When enabled, pending AI generation is cancelled on interrupt.
        When disabled, only TTS is stopped.
        """
        with self._lock:
            self._auto_cancel = enabled
            logger.debug("Auto-cancel on interrupt: {}", enabled)
    
    def set_min_interval(self, seconds: float):
        """
        Set minimum interval between interruptions.
        
        Prevents rapid successive interruptions.
        """
        with self._lock:
            self._min_interrupt_interval = max(0.1, seconds)
            logger.debug("Min interrupt interval: {}s", self._min_interrupt_interval)
    
    # ── Statistics ────────────────────────────────────────────
    
    def get_interruption_count(self) -> int:
        """Get total number of interruptions handled."""
        with self._lock:
            return self._interruption_count
    
    def reset_count(self):
        """Reset interruption counter."""
        with self._lock:
            self._interruption_count = 0
    
    def get_stats(self) -> dict:
        """Get interruption handler statistics."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "is_speaking": self._is_speaking,
                "interruption_count": self._interruption_count,
                "auto_cancel": self._auto_cancel,
                "min_interval": self._min_interrupt_interval,
                "last_interrupt": self._last_interrupt_time,
            }
    
    # ── Utilities ─────────────────────────────────────────────
    
    def reset(self):
        """Reset interruption handler state."""
        with self._lock:
            self._is_speaking = False
            self._interruption_count = 0
            self._last_interrupt_time = 0.0
            logger.debug("Interruption handler reset")
    
    def __repr__(self) -> str:
        return (
            f"InterruptionHandler(enabled={self._enabled}, "
            f"speaking={self._is_speaking}, "
            f"count={self._interruption_count})"
        )