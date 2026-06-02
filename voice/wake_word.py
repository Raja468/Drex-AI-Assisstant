"""
voice/wake_word.py — Wake Word Detection for DREX

Provides background wake word detection so DREX can operate in
always-listening mode without processing every utterance.

Architecture:
  - Modular design, independent of the main voice pipeline
  - Support for pvporcupine (preferred) with openwakeword fallback
  - Configurable wake words via config
  - Low CPU usage for background operation
  - Enable/disable via config flag

The wake word detector runs a separate thread that monitors audio
for the configured wake word. When detected, it triggers a callback.

Requirements:
  pip install pvporcupine  # preferred
  OR
  pip install openwakeword  # fallback (heavier but free)

Usage:
    detector = WakeWordDetector()
    detector.start(callback=lambda: print("Wake word detected!"))
    # ... later ...
    detector.stop()
"""

import os
import struct
import threading
import time
from typing import Callable, Optional
from loguru import logger
from config import get_config


# Audio parameters for wake word detection
WAKE_SAMPLE_RATE = 16000
WAKE_FRAME_LENGTH = 512  # porcupine default frame length
WAKE_CHANNELS = 1
WAKE_BIT_DEPTH = 16  # PCM 16-bit


class WakeWordDetector:
    """
    Background wake word detector for DREX.

    Uses pvporcupine with openwakeword as fallback.
    Runs in a separate thread for non-blocking operation.

    Attributes:
        enabled: Whether wake word detection is enabled in config
        is_active: Whether the detector thread is currently running
        wake_word: The configured wake word phrase
    """

    def __init__(self):
        self.cfg = get_config().app
        self._engine = None
        self._detector = None
        self._audio_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callback: Optional[Callable[[], None]] = None
        self._available = False
        self._lock = threading.Lock()
        self._backend = None  # "porcupine" or "openwakeword"
        self._init()

    def _init(self):
        """Initialize the wake word detector with the best available backend."""
        # Try pvporcupine first (preferred — low CPU, accurate)
        if self._try_init_porcupine():
            return

        # Fallback to openwakeword
        if self._try_init_openwakeword():
            return

        logger.warning(
            "No wake word engine available. "
            "Install: pip install pvporcupine  OR  pip install openwakeword"
        )

    def _try_init_porcupine(self) -> bool:
        """Try to initialize pvporcupine backend."""
        try:
            import pvporcupine

            # Build keyword list
            wake_words = self._get_wake_words()
            keywords = []
            sensitivities = []

            for ww in wake_words:
                try:
                    keyword_path = pvporcupine.KEYWORD_PATHS.get(ww.lower())
                    if keyword_path:
                        keywords.append(keyword_path)
                    else:
                        # Use built-in keyword
                        keywords.append(ww.lower())
                    sensitivities.append(self.cfg.wake_word_sensitivity)
                except Exception:
                    # Fall back to built-in keyword
                    keywords.append(ww.lower())
                    sensitivities.append(self.cfg.wake_word_sensitivity)

            self._detector = pvporcupine.create(
                keywords=keywords,
                sensitivities=sensitivities,
            )
            self._backend = "porcupine"
            self._available = True
            logger.info(
                "✅ WakeWordDetector initialized (pvporcupine) | words: {}",
                wake_words,
            )
            return True
        except ImportError:
            logger.debug("pvporcupine not installed, trying openwakeword fallback")
            return False
        except Exception as e:
            logger.error("pvporcupine init failed: {}", e)
            return False

    def _try_init_openwakeword(self) -> bool:
        """Try to initialize openwakeword backend (fallback)."""
        try:
            import openwakeword
            from openwakeword.Model import Model

            # openwakeword runs on raw audio frames
            self._detector = openwakeword.Model(
                wakeword_models=self._get_wake_words(),
            )
            self._backend = "openwakeword"
            self._available = True
            logger.info(
                "✅ WakeWordDetector initialized (openwakeword) | words: {}",
                self._get_wake_words(),
            )
            return True
        except ImportError:
            logger.debug("openwakeword not installed")
            return False
        except Exception as e:
            logger.error("openwakeword init failed: {}", e)
            return False

    def _get_wake_words(self) -> list[str]:
        """Get the configured wake words as a list."""
        raw = self.cfg.wake_word
        # Split on commas or use as single phrase
        words = [w.strip().lower() for w in raw.split(",")]
        return words if words else ["hey drex"]

    @property
    def is_available(self) -> bool:
        """Returns True if at least one backend is initialized."""
        return self._available

    @property
    def is_active(self) -> bool:
        """Returns True if the detector thread is running."""
        return self._audio_thread is not None and self._audio_thread.is_alive()

    def start(self, callback: Optional[Callable[[], None]] = None):
        """
        Start background wake word detection.

        Args:
            callback: Function to call when wake word is detected.
                      If not provided, the detector runs silently.
        """
        if not self.is_available:
            logger.warning("Cannot start wake word — no detection engine available")
            return

        with self._lock:
            if self.is_active:
                logger.debug("Wake word detection already running")
                return

            self._stop_event.clear()
            self._callback = callback
            self._audio_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True,
                name="drex-wakeword",
            )
            self._audio_thread.start()
            logger.info("Wake word detection started (backend: {})", self._backend)

    def _detection_loop(self):
        """
        Background loop that captures audio and checks for wake word.

        Uses pyaudio for microphone access and feeds frames to
        the wake word detection engine.
        """
        try:
            import pyaudio
        except ImportError:
            logger.error("pyaudio not installed — cannot run wake word detection")
            return

        audio = None
        stream = None

        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                rate=WAKE_SAMPLE_RATE,
                channels=WAKE_CHANNELS,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=WAKE_FRAME_LENGTH,
            )

            logger.debug("Wake word audio stream opened")

            while not self._stop_event.is_set():
                try:
                    pcm = stream.read(WAKE_FRAME_LENGTH, exception_on_overflow=False)
                except Exception as e:
                    logger.error("Wake word audio read error: {}", e)
                    time.sleep(0.1)
                    continue

                if self._backend == "porcupine":
                    self._check_porcupine(pcm)
                elif self._backend == "openwakeword":
                    self._check_openwakeword(pcm)

        except OSError as e:
            logger.error("Wake word microphone access error: {}", e)
        except Exception as e:
            logger.error("Wake word detection loop error: {}", e)
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if audio is not None:
                try:
                    audio.terminate()
                except Exception:
                    pass
            logger.debug("Wake word detection loop exited")

    def _check_porcupine(self, pcm: bytes):
        """
        Process audio frame with pvporcupine detector.

        Args:
            pcm: Raw PCM audio data (16-bit, 16kHz, mono).
        """
        try:
            pcm_array = struct.unpack_from("h" * (len(pcm) // 2), pcm)
            keyword_index = self._detector.process(pcm_array)
            if keyword_index >= 0:
                logger.info("🔊 Wake word detected (porcupine)")
                self._on_detected()
        except Exception as e:
            logger.debug("Porcupine processing error: {}", e)

    def _check_openwakeword(self, pcm: bytes):
        """
        Process audio frame with openwakeword detector.

        Args:
            pcm: Raw PCM audio data (16-bit, 16kHz, mono).
        """
        try:
            import numpy as np
            audio_array = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            prediction = self._detector.predict(audio_array)

            # Check if any wake word score exceeds threshold
            for word, score in prediction.items():
                if score > 0.5:  # detection threshold
                    logger.info("🔊 Wake word '{}' detected (openwakeword)", word)
                    self._on_detected()
                    break
        except Exception as e:
            logger.debug("openwakeword processing error: {}", e)

    def _on_detected(self):
        """
        Handle wake word detection.

        Calls the registered callback if set.
        Pauses briefly to avoid double-triggering.
        """
        if self._callback:
            try:
                self._callback()
            except Exception as e:
                logger.error("Wake word callback error: {}", e)
        # Brief cooldown to avoid double detection
        time.sleep(0.5)

    def stop(self):
        """
        Stop the wake word detection thread.

        Thread-safe and idempotent.
        """
        with self._lock:
            if not self.is_active:
                return

            logger.info("Stopping wake word detection...")
            self._stop_event.set()

            if self._audio_thread:
                self._audio_thread.join(timeout=3.0)
                if self._audio_thread.is_alive():
                    logger.warning(
                        "Wake word thread did not exit in time — continuing"
                    )
                self._audio_thread = None

            logger.info("Wake word detection stopped")

    def shutdown(self):
        """Clean shutdown of the wake word detector."""
        self.stop()
        if self._detector:
            try:
                if self._backend == "porcupine":
                    self._detector.delete()
                self._detector = None
            except Exception as e:
                logger.debug("Wake word detector cleanup error: {}", e)
        self._available = False
        logger.info("WakeWordDetector shutdown")