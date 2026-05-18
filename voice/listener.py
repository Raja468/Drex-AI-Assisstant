import threading
import queue
from typing import Optional, Callable
from loguru import logger
from config import get_config, VoiceConfig


class Listener:
    def __init__(self, on_result: Callable[[str], None] = None):
        self.cfg: VoiceConfig = get_config().voice
        self.on_result = on_result
        self._recognizer = None
        self._microphone = None
        self._listening = False
        self._continuous_thread: Optional[threading.Thread] = None
        self._stop_listening = None
        self._available: Optional[bool] = None
        self._result_queue: queue.Queue = queue.Queue()
        self._init()

    def _init(self):
        try:
            import speech_recognition as sr
            self._sr = sr
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = self.cfg.energy_threshold
            self._recognizer.pause_threshold = self.cfg.pause_threshold
            self._recognizer.dynamic_energy_threshold = True

            # Test microphone access
            with sr.Microphone() as source:
                logger.info("Microphone detected. Calibrating for ambient noise...")
                self._recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("Microphone ready. Energy threshold: {}",
                            self._recognizer.energy_threshold)

            self._available = True

        except ImportError:
            logger.error("speech_recognition not installed")
            self._available = False
        except OSError as e:
            logger.error("Microphone not accessible: {}", e)
            self._available = False
        except Exception as e:
            logger.error("Listener init failed: {}", e)
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available is True

    def listen_once(self, timeout: int = None, phrase_limit: int = None) -> Optional[str]:
        """Listen for a single utterance and return transcribed text."""
        if not self.is_available:
            logger.warning("Listener not available")
            return None

        sr = self._sr
        t = timeout or self.cfg.timeout
        pl = phrase_limit or self.cfg.phrase_limit

        try:
            with sr.Microphone() as source:
                logger.debug("Listening... (timeout={}s)", t)
                self._listening = True
                audio = self._recognizer.listen(source, timeout=t, phrase_time_limit=pl)

            result = self._transcribe(audio)
            logger.info("Heard: '{}'", result)
            return result

        except sr.WaitTimeoutError:
            logger.debug("Listen timeout — no speech detected")
            return None
        except Exception as e:
            logger.error("Listen error: {}", e)
            return None
        finally:
            self._listening = False

    def _transcribe(self, audio) -> Optional[str]:
        """Try Google Web Speech → fallback to Sphinx offline."""
        sr = self._sr
        try:
            text = self._recognizer.recognize_google(audio, language=self.cfg.language)
            return text.strip()
        except sr.UnknownValueError:
            logger.debug("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.warning("Google Speech API error: {}. Trying offline fallback.", e)
            try:
                return self._recognizer.recognize_sphinx(audio)
            except Exception:
                return None

    def start_continuous(self, callback: Callable[[str], None] = None):
        """Start background continuous listening thread."""
        if not self.is_available:
            logger.warning("Cannot start continuous listening — microphone unavailable")
            return

        cb = callback or self.on_result
        if not cb:
            logger.warning("No callback set for continuous listening")
            return

        if self._stop_listening:
            logger.debug("Continuous listening already running")
            return

        sr = self._sr

        def audio_callback(recognizer, audio):
            try:
                text = self._transcribe(audio)
                if text:
                    logger.info("Continuous heard: '{}'", text)
                    cb(text)
            except Exception as e:
                logger.error("Continuous listen callback error: {}", e)

        with sr.Microphone() as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=0.5)

        self._stop_listening = self._recognizer.listen_in_background(
            sr.Microphone(),
            audio_callback,
            phrase_time_limit=self.cfg.phrase_limit,
        )
        logger.info("Continuous listening started")

    def stop_continuous(self):
        if self._stop_listening:
            self._stop_listening(wait_for_stop=False)
            self._stop_listening = None
            logger.info("Continuous listening stopped")

    def list_microphones(self) -> list[dict]:
        if not self._sr:
            return []
        try:
            sr = self._sr
            mics = sr.Microphone.list_microphone_names()
            return [{"index": i, "name": name} for i, name in enumerate(mics)]
        except Exception as e:
            logger.error("Could not list microphones: {}", e)
            return []

    @property
    def is_listening(self) -> bool:
        return self._listening

    def recalibrate(self):
        """Re-adjust for ambient noise."""
        if not self.is_available:
            return
        try:
            with self._sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=1)
            logger.info("Recalibrated. New energy threshold: {}",
                        self._recognizer.energy_threshold)
        except Exception as e:
            logger.error("Recalibration failed: {}", e)

    def shutdown(self):
        self.stop_continuous()
        self._listening = False