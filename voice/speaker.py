import threading
import queue
from loguru import logger
from config import get_config, VoiceConfig


class Speaker:
    def __init__(self):
        self.cfg: VoiceConfig = get_config().voice
        self._engine = None
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._speaking = False
        self._init_engine()
        self._start_worker()

    def _init_engine(self):
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.cfg.rate)
            self._engine.setProperty("volume", self.cfg.volume)

            voices = self._engine.getProperty("voices")
            if voices:
                idx = min(self.cfg.voice_index, len(voices) - 1)
                self._engine.setProperty("voice", voices[idx].id)
                logger.info("Speaker ready. Voice: {} | Rate: {} | Volume: {}",
                            voices[idx].name, self.cfg.rate, self.cfg.volume)
            else:
                logger.warning("No TTS voices found on this system")

        except Exception as e:
            logger.error("Speaker init failed: {}", e)
            self._engine = None

    def _start_worker(self):
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="drex-speaker")
        self._thread.start()

    def _worker(self):
        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
                if text is None:
                    break
                self._speak_sync(text)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error("Speaker worker error: {}", e)

    def _speak_sync(self, text: str):
        if not self._engine:
            logger.warning("TTS engine not available, cannot speak: {}", text[:50])
            return
        try:
            self._speaking = True
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as e:
            logger.error("TTS speak error: {}", e)
            # Reinit engine on failure
            self._init_engine()
        finally:
            self._speaking = False

    def speak(self, text: str, priority: bool = False):
        """Queue text for speaking. priority=True clears the queue first."""
        if not text or not text.strip():
            return
        # Clean up text for TTS
        clean = self._clean_text(text)
        if priority:
            self._clear_queue()
        self._queue.put(clean)
        logger.debug("Queued speech: {}...", clean[:60])

    def speak_sync(self, text: str):
        """Speak immediately on calling thread (blocks)."""
        clean = self._clean_text(text)
        self._speak_sync(clean)

    def _clear_queue(self):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _clean_text(self, text: str) -> str:
        """Remove markdown and symbols that sound bad in TTS."""
        import re
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'#+\s', '', text)
        text = re.sub(r'`+', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
        return text.strip()

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    @property
    def is_available(self) -> bool:
        return self._engine is not None

    def set_rate(self, rate: int):
        self.cfg.rate = rate
        if self._engine:
            self._engine.setProperty("rate", rate)

    def set_volume(self, volume: float):
        self.cfg.volume = volume
        if self._engine:
            self._engine.setProperty("volume", volume)

    def list_voices(self) -> list[dict]:
        if not self._engine:
            return []
        voices = self._engine.getProperty("voices")
        return [{"id": i, "name": v.name, "lang": getattr(v, "languages", [""])[0]}
                for i, v in enumerate(voices)]

    def stop(self):
        self._clear_queue()
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

    def shutdown(self):
        self._running = False
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)