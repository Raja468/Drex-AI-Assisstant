# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/silence_detector.py  —  Advanced Silence Detection
#
#  Improved silence detection for speech endpoint detection.
#
#  Problem:
#  Traditional VAD (Voice Activity Detection) can be too
#  aggressive, cutting off speech during natural pauses.
#  Or too lenient, waiting too long before processing.
#
#  Solution:
#  - Adaptive silence threshold based on ambient noise
#  - Configurable silence duration before endpoint
#  - Pause detection vs. speech end detection
#  - Debounce to prevent false triggers
#
#  This creates more natural conversation flow where
#  DREX waits appropriately for the user to finish.
# ============================================================

import threading
import time
import collections
from typing import Callable, Optional
from loguru import logger

from assistant.state_engine import StateEngine, AssistantState


class SilenceDetector:
    """
    Advanced silence detection for speech endpoint detection.
    
    Features:
    - Adaptive noise floor tracking
    - Configurable silence duration
    - Pause vs. end-of-speech detection
    - Debounce protection
    
    Usage:
        detector = SilenceDetector(state_engine)
        detector.set_speech_callback(on_speech_detected)
        detector.set_silence_callback(on_silence_detected)
        
        # In audio processing loop:
        detector.process_audio_level(level)
    """
    
    def __init__(self, state_engine: StateEngine):
        self.state_engine = state_engine
        self._lock = threading.RLock()
        
        # Callbacks
        self._on_speech_start: Optional[Callable] = None
        self._on_speech_end: Optional[Callable] = None
        self._on_pause: Optional[Callable] = None
        
        # Audio state
        self._is_speaking = False
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0
        self._silence_start_time = 0.0
        
        # Noise floor tracking
        self._noise_floor = 0.01  # Default low threshold
        self._noise_samples: collections.deque = collections.deque(maxlen=100)
        self._adaptive_threshold = True
        
        # Configuration
        self._enabled = True
        self._silence_threshold = 0.02  # Audio level below this = silence
        self._silence_duration = 0.8  # Seconds of silence before endpoint
        self._pause_duration = 0.3  # Short pause (not end of speech)
        self._min_speech_duration = 0.2  # Minimum speech to count
        self._debounce_time = 0.1  # Prevent rapid state changes
        
        # Statistics
        self._speech_count = 0
        self._false_trigger_count = 0
        
        logger.debug("SilenceDetector initialized | silence_duration={}s", 
                    self._silence_duration)
    
    # ── Callback Registration ─────────────────────────────────
    
    def set_speech_callback(self, on_start: Callable = None, on_end: Callable = None):
        """
        Set speech detection callbacks.
        
        on_start: Called when speech begins
        on_end: Called when speech ends (silence detected)
        """
        with self._lock:
            if on_start:
                self._on_speech_start = on_start
            if on_end:
                self._on_speech_end = on_end
    
    def set_pause_callback(self, on_pause: Callable):
        """Set callback for pause detection (short silence)."""
        with self._lock:
            self._on_pause = on_pause
    
    # ── Audio Processing ──────────────────────────────────────
    
    def process_audio_level(self, level: float):
        """
        Process an audio level sample.
        
        Call this regularly with the current audio level
        (normalized 0.0 to 1.0).
        
        Args:
            level: Audio level (0.0 = silence, 1.0 = max volume)
        """
        with self._lock:
            if not self._enabled:
                return
            
            now = time.time()
            
            # Update noise floor
            if self._adaptive_threshold:
                self._update_noise_floor(level)
            
            # Determine if this is speech or silence
            threshold = self._get_effective_threshold()
            is_speech = level > threshold
            
            if is_speech:
                self._handle_speech(now, level)
            else:
                self._handle_silence(now)
    
    def _update_noise_floor(self, level: float):
        """Update adaptive noise floor estimate."""
        # Only update during "quiet" periods
        if not self._is_speaking:
            self._noise_samples.append(level)
            
            # Calculate noise floor as median of quiet samples
            if len(self._noise_samples) >= 10:
                sorted_samples = sorted(self._noise_samples)
                median_idx = len(sorted_samples) // 2
                self._noise_floor = sorted_samples[median_idx]
    
    def _get_effective_threshold(self) -> float:
        """Get effective silence threshold."""
        if self._adaptive_threshold:
            # Use noise floor + margin
            return max(self._silence_threshold, self._noise_floor * 2.0)
        return self._silence_threshold
    
    def _handle_speech(self, now: float, level: float):
        """Handle speech detection."""
        if not self._is_speaking:
            # Speech just started
            # Check debounce
            if now - self._last_speech_time < self._debounce_time:
                # Too soon after last speech, ignore
                return
            
            self._is_speaking = True
            self._speech_start_time = now
            self._silence_start_time = 0.0
            
            logger.debug("Speech started | level={:.3f}", level)
            
            # Update state
            if self.state_engine.can_listen():
                self.state_engine.state = AssistantState.LISTENING
            
            # Notify callback
            if self._on_speech_start:
                try:
                    self._on_speech_start()
                except Exception as e:
                    logger.error("Speech start callback error: {}", e)
        else:
            # Speech continuing
            self._last_speech_time = now
            self._silence_start_time = 0.0
    
    def _handle_silence(self, now: float):
        """Handle silence detection."""
        if not self._is_speaking:
            return  # Already silent
        
        # Start tracking silence
        if self._silence_start_time == 0.0:
            self._silence_start_time = now
            return
        
        # Calculate silence duration
        silence_duration = now - self._silence_start_time
        
        # Check for pause (short silence)
        if silence_duration >= self._pause_duration and silence_duration < self._silence_duration:
            # This is a pause, not end of speech
            if self._on_pause:
                try:
                    self._on_pause()
                except Exception as e:
                    logger.error("Pause callback error: {}", e)
        
        # Check for end of speech (long silence)
        if silence_duration >= self._silence_duration:
            # Speech has ended
            speech_duration = self._last_speech_time - self._speech_start_time
            
            # Check minimum speech duration
            if speech_duration < self._min_speech_duration:
                # Too short, probably noise
                logger.debug("Speech too short ({:.2f}s), ignoring", speech_duration)
                self._false_trigger_count += 1
                self._reset_speech_state()
                return
            
            logger.debug("Speech ended | duration={:.2f}s", speech_duration)
            self._speech_count += 1
            
            # Notify callback
            if self._on_speech_end:
                try:
                    self._on_speech_end()
                except Exception as e:
                    logger.error("Speech end callback error: {}", e)
            
            # Reset state
            self._reset_speech_state()
    
    def _reset_speech_state(self):
        """Reset speech tracking state."""
        self._is_speaking = False
        self._speech_start_time = 0.0
        self._silence_start_time = 0.0
    
    # ── Manual Control ────────────────────────────────────────
    
    def force_speech_start(self):
        """Manually trigger speech start."""
        with self._lock:
            now = time.time()
            self._is_speaking = True
            self._speech_start_time = now
            self._silence_start_time = 0.0
            
            if self._on_speech_start:
                try:
                    self._on_speech_start()
                except Exception as e:
                    logger.error("Speech start callback error: {}", e)
    
    def force_speech_end(self):
        """Manually trigger speech end."""
        with self._lock:
            if self._is_speaking:
                logger.debug("Speech force-ended")
                self._speech_count += 1
                
                if self._on_speech_end:
                    try:
                        self._on_speech_end()
                    except Exception as e:
                        logger.error("Speech end callback error: {}", e)
                
                self._reset_speech_state()
    
    # ── Configuration ─────────────────────────────────────────
    
    def enable(self):
        """Enable silence detection."""
        with self._lock:
            self._enabled = True
            logger.info("Silence detection enabled")
    
    def disable(self):
        """Disable silence detection."""
        with self._lock:
            self._enabled = False
            logger.info("Silence detection disabled")
    
    def is_enabled(self) -> bool:
        """Check if silence detection is enabled."""
        return self._enabled
    
    def set_silence_duration(self, seconds: float):
        """
        Set silence duration before speech endpoint.
        
        Shorter = faster response but may cut off speech
        Longer = more natural but slower response
        """
        with self._lock:
            self._silence_duration = max(0.2, min(3.0, seconds))
            logger.debug("Silence duration: {}s", self._silence_duration)
    
    def get_silence_duration(self) -> float:
        """Get current silence duration setting."""
        return self._silence_duration
    
    def set_pause_duration(self, seconds: float):
        """Set pause detection duration."""
        with self._lock:
            self._pause_duration = max(0.1, min(1.0, seconds))
            logger.debug("Pause duration: {}s", self._pause_duration)
    
    def set_silence_threshold(self, threshold: float):
        """Set audio level threshold for silence."""
        with self._lock:
            self._silence_threshold = max(0.001, min(0.5, threshold))
            logger.debug("Silence threshold: {}", self._silence_threshold)
    
    def set_adaptive_threshold(self, enabled: bool):
        """Enable/disable adaptive noise floor tracking."""
        with self._lock:
            self._adaptive_threshold = enabled
            logger.debug("Adaptive threshold: {}", enabled)
    
    def set_min_speech_duration(self, seconds: float):
        """Set minimum speech duration to count as valid."""
        with self._lock:
            self._min_speech_duration = max(0.05, min(1.0, seconds))
            logger.debug("Min speech duration: {}s", self._min_speech_duration)
    
    # ── State Queries ─────────────────────────────────────────
    
    def is_speaking(self) -> bool:
        """Check if currently detecting speech."""
        with self._lock:
            return self._is_speaking
    
    def get_speech_duration(self) -> float:
        """Get current speech duration (if speaking)."""
        with self._lock:
            if self._is_speaking and self._speech_start_time > 0:
                return time.time() - self._speech_start_time
            return 0.0
    
    def get_silence_duration(self) -> float:
        """Get current silence duration (if in silence)."""
        with self._lock:
            if self._is_speaking and self._silence_start_time > 0:
                return time.time() - self._silence_start_time
            return 0.0
    
    def get_noise_floor(self) -> float:
        """Get current noise floor estimate."""
        return self._noise_floor
    
    # ── Statistics ────────────────────────────────────────────
    
    def get_stats(self) -> dict:
        """Get silence detector statistics."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "is_speaking": self._is_speaking,
                "adaptive_threshold": self._adaptive_threshold,
                "noise_floor": self._noise_floor,
                "effective_threshold": self._get_effective_threshold(),
                "silence_duration_setting": self._silence_duration,
                "speech_count": self._speech_count,
                "false_trigger_count": self._false_trigger_count,
            }
    
    def reset_stats(self):
        """Reset statistics."""
        with self._lock:
            self._speech_count = 0
            self._false_trigger_count = 0
    
    # ── Utilities ─────────────────────────────────────────────
    
    def reset(self):
        """Reset silence detector state."""
        with self._lock:
            self._reset_speech_state()
            self._noise_samples.clear()
            self._noise_floor = 0.01
            self._speech_count = 0
            self._false_trigger_count = 0
            logger.debug("SilenceDetector reset")
    
    def destroy(self):
        """Clean up and destroy the silence detector."""
        self.reset()
        logger.debug("SilenceDetector destroyed")
    
    def __repr__(self) -> str:
        return (
            f"SilenceDetector(enabled={self._enabled}, "
            f"speaking={self._is_speaking}, "
            f"count={self._speech_count})"
        )