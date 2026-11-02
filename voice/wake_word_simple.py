"""
voice/wake_word_simple.py — Fallback Wake Word Detector for DREX

Fallback wake word detector that doesn't require pvporcupine or openwakeword.
Listens for keyword 'drex' or 'hey drex' using SpeechRecognition.
Runs in background thread.
Fires on_detected() callback when wake word heard.
"""

import threading
import time
from typing import Callable, Optional
from loguru import logger
from config import get_config


class SimpleWakeWord:
    """
    Fallback wake word detector using SpeechRecognition (no pvporcupine needed).
    Listens for keyword phrases in background thread.
    Fires on_detected() callback when wake word heard.
    """

    WAKE_PHRASES = [
        "drex", "hey drex", "ok drex",
        "yo drex", "drex wake up",
    ]

    def __init__(self, wake_phrases: list[str] = None):
        """
        Args:
            wake_phrases: Custom wake phrases. Defaults to WAKE_PHRASES.
        """
        self.phrases = [p.lower() for p in (wake_phrases or self.WAKE_PHRASES)]
        self.on_detected: Optional[Callable[[], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._available = False
        self._recognizer = None
        self._sr = None
        self._init()

    def _init(self):
        """Initialize SpeechRecognition recognizer."""
        try:
            import speech_recognition as sr
            self._sr = sr
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 3000
            self._recognizer.pause_threshold = 0.8
            self._recognizer.dynamic_energy_threshold = True

            # Quick mic test
            try:
                with sr.Microphone() as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                self._available = True
                logger.info(
                    "✅ SimpleWakeWord initialized | phrases: {}",
                    self.phrases,
                )
            except Exception as e:
                logger.warning("SimpleWakeWord mic test failed: {}", e)
                self._available = False
        except ImportError:
            logger.warning(
                "speech_recognition not installed — SimpleWakeWord unavailable"
            )
            self._available = False
        except Exception as e:
            logger.error("SimpleWakeWord init failed: {}", e)
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def start(self):
        """Start background listening thread."""
        if not self._available:
            logger.warning("SimpleWakeWord not available")
            return
        if self._running:
            return

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="drex-simple-wakeword",
        )
        self._thread.start()
        logger.info("SimpleWakeWord listening started")

    def stop(self):
        """Stop cleanly."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("SimpleWakeWord stopped")

    def shutdown(self):
        """Clean shutdown."""
        self.stop()
        self._available = False
        self._recognizer = None
        self._sr = None

    def _listen_loop(self):
        """
        Continuously listens with short timeout (~2 second phrases).
        If any WAKE_PHRASES detected in result -> fire on_detected().
        Uses Google STT for recognition.
        """
        sr = self._sr
        if sr is None or self._recognizer is None:
            return

        while self._running and not self._stop_event.is_set():
            try:
                with sr.Microphone() as source:
                    logger.debug("Wake word listening...")
                    audio = self._recognizer.listen(
                        source, timeout=1.0, phrase_time_limit=3
                    )
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                logger.debug("Wake word listen error: {}", e)
                time.sleep(0.5)
                continue

            try:
                text = self._recognizer.recognize_google(audio).strip().lower()
                logger.debug("Wake word heard: '{}'", text)
            except sr.UnknownValueError:
                continue
            except sr.RequestError:
                continue
            except Exception:
                continue

            # Check if any wake phrase is in the text
            for phrase in self.phrases:
                if phrase in text:
                    logger.info("🔊 Wake word detected: '{}' (matched: '{}')", text, phrase)
                    if self.on_detected:
                        try:
                            self.on_detected()
                        except Exception as e:
                            logger.error("Wake word callback error: {}", e)
                    # Brief cooldown
                    time.sleep(0.5)
                    break