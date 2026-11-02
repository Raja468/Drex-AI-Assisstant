# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/echo_canceller.py  —  Echo Cancellation
#
#  Prevents DREX from hearing its own TTS output.
#
#  Problem:
#  When DREX speaks via TTS, the microphone picks up the
#  speaker output, causing DREX to "hear itself" and
#  potentially trigger false speech detection.
#
#  Solution:
#  1. Track when TTS is playing (speaking state)
#  2. Suppress speech detection during TTS playback
#  3. Use audio ducking to reduce mic sensitivity
#  4. Implement post-TTS cooldown period
#
#  This creates a clean voice interaction loop where
#  DREX only listens when it's not speaking.
# ============================================================

import threading
import time
from typing import Callable, Optional
from loguru import logger

from assistant.state_engine import StateEngine, AssistantState


class EchoCanceller:
    """
    Echo cancellation for voice interaction.
    
    Prevents DREX from hearing its own TTS output by:
    - Tracking TTS playback state
    - Suppressing speech detection during playback
    - Implementing post-TTS cooldown
    - Optional audio ducking
    
    Usage:
        canceller = EchoCanceller(state_engine)
        canceller.set_speaker(speaker)
        
        # In speech detection callback:
        if canceller.should_listen():
            process_speech(text)
    """
    
    def __init__(self, state_engine: StateEngine):
        self.state_engine = state_engine
        self._lock = threading.RLock()
        
        # Speaker reference
        self._speaker = None
        
        # Echo cancellation state
        self._is_speaking = False
        self._speaking_start_time = 0.0
        self._speaking_end_time = 0.0
        
        # Configuration
        self._enabled = True
        self._cooldown_seconds = 0.5  # Wait after TTS ends
        self._pre_speech_buffer = 0.1  # Buffer before TTS starts
        self._ducking_enabled = False  # Reduce mic sensitivity
        
        # Statistics
        self._echo_prevented_count = 0
        
        # Register state callback
        self.state_engine.register_state_callback(self._on_state_change)
        
        logger.debug("EchoCanceller initialized | cooldown={}s", self._cooldown_seconds)
    
    # ── Speaker Integration ───────────────────────────────────
    
    def set_speaker(self, speaker):
        """
        Set the TTS speaker component.
        
        The speaker should have is_playing() or similar method.
        """
        with self._lock:
            self._speaker = speaker
            logger.debug("Speaker set for echo cancellation")
    
    # ── Core Logic ────────────────────────────────────────────
    
    def should_listen(self) -> bool:
        """
        Check if we should listen for speech.
        
        Returns False if:
        - Echo cancellation is disabled
        - TTS is currently playing
        - We're in cooldown period after TTS
        - State doesn't allow listening
        
        This is the main method to call in speech detection.
        """
        with self._lock:
            # Check if enabled
            if not self._enabled:
                return True
            
            # Check state engine
            if not self.state_engine.can_listen():
                return False
            
            # Check if currently speaking
            if self._is_speaking:
                self._echo_prevented_count += 1
                logger.debug("Echo prevented: speaking")
                return False
            
            # Check cooldown period
            if self._speaking_end_time > 0:
                elapsed = time.time() - self._speaking_end_time
                if elapsed < self._cooldown_seconds:
                    logger.debug("Echo prevented: cooldown ({:.2f}s)", elapsed)
                    return False
            
            # Check speaker directly (backup)
            if self._speaker and self._is_speaker_playing():
                self._echo_prevented_count += 1
                logger.debug("Echo prevented: speaker playing")
                return False
            
            return True
    
    def _is_speaker_playing(self) -> bool:
        """Check if speaker is currently playing audio."""
        if not self._speaker:
            return False
        
        # Try various methods to check playback state
        try:
            if hasattr(self._speaker, 'is_playing'):
                return self._speaker.is_playing()
            if hasattr(self._speaker, '_is_playing'):
                return self._speaker._is_playing
            if hasattr(self._speaker, 'playing'):
                return self._speaker.playing
        except Exception:
            pass
        
        return False
    
    # ── Speaking State Management ─────────────────────────────
    
    def start_speaking(self):
        """
        Mark that TTS playback has started.
        
        Call this when TTS begins playing.
        """
        with self._lock:
            self._is_speaking = True
            self._speaking_start_time = time.time()
            self._speaking_end_time = 0.0
            logger.debug("Echo canceller: speaking started")
    
    def stop_speaking(self):
        """
        Mark that TTS playback has ended.
        
        Call this when TTS finishes or is interrupted.
        """
        with self._lock:
            self._is_speaking = False
            self._speaking_end_time = time.time()
            logger.debug("Echo canceller: speaking stopped")
    
    def is_speaking(self) -> bool:
        """Check if TTS is currently playing."""
        with self._lock:
            return self._is_speaking
    
    # ── State Change Handler ──────────────────────────────────
    
    def _on_state_change(self, old_state: AssistantState, new_state: AssistantState):
        """Handle state changes to track speaking state."""
        if new_state == AssistantState.SPEAKING:
            self.start_speaking()
        elif old_state == AssistantState.SPEAKING:
            self.stop_speaking()
    
    # ── Configuration ─────────────────────────────────────────
    
    def enable(self):
        """Enable echo cancellation."""
        with self._lock:
            self._enabled = True
            logger.info("Echo cancellation enabled")
    
    def disable(self):
        """Disable echo cancellation."""
        with self._lock:
            self._enabled = False
            logger.info("Echo cancellation disabled")
    
    def is_enabled(self) -> bool:
        """Check if echo cancellation is enabled."""
        with self._lock:
            return self._enabled
    
    def set_cooldown(self, seconds: float):
        """
        Set post-TTS cooldown period.
        
        During cooldown, speech detection is suppressed to
        allow TTS audio to fully dissipate.
        """
        with self._lock:
            self._cooldown_seconds = max(0.0, seconds)
            logger.debug("Echo cooldown: {}s", self._cooldown_seconds)
    
    def get_cooldown(self) -> float:
        """Get current cooldown period."""
        return self._cooldown_seconds
    
    def set_ducking(self, enabled: bool):
        """
        Enable/disable audio ducking.
        
        When enabled, microphone sensitivity is reduced
        during TTS playback for better echo cancellation.
        """
        with self._lock:
            self._ducking_enabled = enabled
            logger.debug("Audio ducking: {}", enabled)
    
    # ── Statistics ────────────────────────────────────────────
    
    def get_echo_prevented_count(self) -> int:
        """Get count of prevented echo detections."""
        with self._lock:
            return self._echo_prevented_count
    
    def reset_stats(self):
        """Reset statistics."""
        with self._lock:
            self._echo_prevented_count = 0
    
    def get_stats(self) -> dict:
        """Get echo canceller statistics."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "is_speaking": self._is_speaking,
                "cooldown_seconds": self._cooldown_seconds,
                "ducking_enabled": self._ducking_enabled,
                "echo_prevented_count": self._echo_prevented_count,
                "time_since_speaking": (
                    time.time() - self._speaking_end_time 
                    if self._speaking_end_time > 0 else None
                ),
            }
    
    # ── Utilities ─────────────────────────────────────────────
    
    def reset(self):
        """Reset echo canceller state."""
        with self._lock:
            self._is_speaking = False
            self._speaking_start_time = 0.0
            self._speaking_end_time = 0.0
            self._echo_prevented_count = 0
            logger.debug("EchoCanceller reset")
    
    def destroy(self):
        """Clean up and destroy the echo canceller."""
        self.state_engine.unregister_state_callback(self._on_state_change)
        logger.debug("EchoCanceller destroyed")
    
    def __repr__(self) -> str:
        return (
            f"EchoCanceller(enabled={self._enabled}, "
            f"speaking={self._is_speaking}, "
            f"prevented={self._echo_prevented_count})"
        )