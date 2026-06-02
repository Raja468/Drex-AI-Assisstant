"""
voice/vad.py — Voice Activity Detection for DREX

Provides real-time voice activity detection using webrtcvad.
Detects when the user starts and stops speaking, reducing unnecessary
processing and improving realtime responsiveness.

Architecture:
  - Modular implementation, clean integration into voice/listener.py
  - Configurable sensitivity (mode 0-3)
  - Adjustable silence duration threshold
  - Frame-based audio analysis

Requirements:
  pip install webrtcvad

Usage:
    vad = VoiceActivityDetector(mode=1, silence_duration=0.8)
    if vad.is_speech(audio_frame):
        # process speech
    vad.process_frames(audio_frames, sample_rate=16000)
"""

import time
import struct
from typing import Optional
from loguru import logger
from config import get_config


# Default audio parameters for VAD processing
VAD_SAMPLE_RATE = 16000  # webrtcvad requires 16kHz
VAD_FRAME_MS = 30        # frame duration in ms (10, 20, or 30)
VAD_FRAME_SIZE = int(VAD_SAMPLE_RATE * VAD_FRAME_MS / 1000) * 2  # 16-bit PCM bytes


class VoiceActivityDetector:
    """
    Voice Activity Detector using webrtcvad.

    Detects speech/non-speech in audio frames.
    Tracks speaking state to determine when the user starts and stops speaking.

    Attributes:
        mode: Aggressiveness mode (0=most aggressive filtering, 3=least)
        silence_duration: Seconds of silence before considering speech ended
        is_speaking: Current speaking state
    """

    def __init__(self, mode: int = 1, silence_duration: float = 0.8):
        """
        Initialize the VAD detector.

        Args:
            mode: VAD aggressiveness (0-3). 0 = most aggressive (filters more noise).
                  1 = default. 3 = least aggressive (detects more speech).
            silence_duration: Seconds of continuous silence before marking
                              speech as ended.
        """
        self.mode = max(0, min(3, mode))
        self.silence_duration = max(0.1, silence_duration)
        self._vad = None
        self._available = False
        self.is_speaking = False
        self._speech_start_time: Optional[float] = None
        self._silence_start_time: Optional[float] = None
        self._init()

    def _init(self):
        """Initialize the webrtcvad detector."""
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(self.mode)
            self._available = True
            logger.info(
                "✅ VoiceActivityDetector initialized (mode={}, silence_duration={}s)",
                self.mode, self.silence_duration,
            )
        except ImportError:
            logger.warning(
                "webrtcvad not installed. Run: pip install webrtcvad"
            )
            self._available = False
        except Exception as e:
            logger.error("VAD init failed: {}", e)
            self._available = False

    @property
    def is_available(self) -> bool:
        """Returns True if webrtcvad is loaded and functional."""
        return self._available

    def is_speech_frame(self, audio_frame: bytes) -> bool:
        """
        Check if a single audio frame contains speech.

        Args:
            audio_frame: 16-bit PCM audio frame at 16kHz sample rate.
                         Must be 10ms, 20ms, or 30ms in duration.

        Returns:
            True if the frame contains speech, False otherwise.
        """
        if not self._available or not self._vad:
            return False

        try:
            return self._vad.is_speech(audio_frame, VAD_SAMPLE_RATE)
        except Exception as e:
            logger.debug("VAD frame error: {}", e)
            return False

    def process_frame(self, audio_frame: bytes) -> bool:
        """
        Process a single audio frame and update speaking state.

        Args:
            audio_frame: 16-bit PCM audio frame at 16kHz.

        Returns:
            True if currently in a speaking state, False if silent.
        """
        if not self._available:
            return False

        is_speech = self.is_speech_frame(audio_frame)
        now = time.time()

        if is_speech:
            # User is speaking
            if not self.is_speaking:
                # Transition: silence -> speech
                self.is_speaking = True
                self._speech_start_time = now
                self._silence_start_time = None
                logger.debug("VAD: Speech started")
            return True
        else:
            # No speech detected in this frame
            if self.is_speaking:
                # Transition: speech -> possible silence
                if self._silence_start_time is None:
                    self._silence_start_time = now
                elif (now - self._silence_start_time) >= self.silence_duration:
                    # Sustained silence — speech has ended
                    self.is_speaking = False
                    speech_duration = self._silence_start_time - (
                        self._speech_start_time or self._silence_start_time
                    )
                    logger.debug(
                        "VAD: Speech ended (duration: {:.1f}s)",
                        speech_duration,
                    )
                    self._speech_start_time = None
                    self._silence_start_time = None
            return False

    def reset(self):
        """Reset the speaking state."""
        self.is_speaking = False
        self._speech_start_time = None
        self._silence_start_time = None

    def get_speech_segment(
        self, audio_data: bytes, sample_rate: int = 16000
    ) -> Optional[bytes]:
        """
        Extract speech segment from raw audio data by removing silence.

        This is a simplified implementation that returns the audio data
        if speech is detected within it.

        Args:
            audio_data: Raw PCM audio data.
            sample_rate: Sample rate of the audio data.

        Returns:
            Audio segment with speech, or None if no speech detected.
        """
        if not self._available or not audio_data:
            return None

        # Convert sample rate if needed
        if sample_rate != VAD_SAMPLE_RATE:
            logger.debug(
                "VAD sample rate mismatch: got {}Hz, need {}Hz",
                sample_rate, VAD_SAMPLE_RATE,
            )
            return audio_data  # pass through without processing

        frame_size = int(sample_rate * VAD_FRAME_MS / 1000) * 2
        speech_frames = []
        speech_detected = False

        for i in range(0, len(audio_data) - frame_size + 1, frame_size):
            frame = audio_data[i:i + frame_size]
            if len(frame) == frame_size:
                is_speech = self.is_speech_frame(frame)
                speech_frames.append((frame, is_speech))
                if is_speech:
                    speech_detected = True

        if not speech_detected:
            return None

        # Return concatenated speech frames with some silence padding
        result = b"".join(f for f, _ in speech_frames)
        return result if result else None

    def shutdown(self):
        """Clean up VAD resources."""
        self._vad = None
        self._available = False
        self.reset()
        logger.info("VoiceActivityDetector shutdown")