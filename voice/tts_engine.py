"""
DEPRECATED -- Sprint-4 Modern Voice Stack

This module is NOT currently wired into the main application flow.
The application uses the legacy Speaker (voice/speaker.py).
This code is preserved for future integration. Do not delete.

---

voice/tts_engine.py - Modular text-to-speech.

Interchangeable TTS backends with automatic fallback:

    Kokoro (offline)  ->  edge-tts (online neural)  ->  pyttsx3 (offline)

OpenAI TTS and ElevenLabs are available when explicitly selected.
Playback goes through pygame.mixer so we can cancel it mid-utterance
for barge-in / interruption support.
"""

from __future__ import annotations

import os
import queue
import tempfile
import threading
from typing import Callable, Optional

from loguru import logger


# ------------------------------------------------------------------
#  Playback helper - pygame.mixer wrapper with cancel support
# ------------------------------------------------------------------

class _AudioPlayer:
    def __init__(self):
        self._pygame = None
        self._available = False
        try:
            import pygame                       # type: ignore
            pygame.mixer.init()
            self._pygame = pygame
            self._available = True
        except Exception as e:
            logger.warning("pygame mixer unavailable: {}", e)

    @property
    def available(self) -> bool:
        return self._available

    def play_file(self, path: str, block: bool = True,
                  stop_event: Optional[threading.Event] = None) -> None:
        if not self._available:
            return
        try:
            self._pygame.mixer.music.load(path)
            self._pygame.mixer.music.play()
        except Exception as e:
            logger.error("Audio play failed: {}", e)
            return
        if not block:
            return
        while self._pygame.mixer.music.get_busy():
            if stop_event is not None and stop_event.is_set():
                self._pygame.mixer.music.stop()
                return
            self._pygame.time.wait(50)

    def stop(self) -> None:
        if not self._available:
            return
        try:
            self._pygame.mixer.music.stop()
        except Exception:
            pass


# ------------------------------------------------------------------
#  Backend base class
# ------------------------------------------------------------------

class TTSBackend:
    name: str = "base"
    available: bool = False

    def synth_to_file(self, text: str) -> Optional[str]:
        raise NotImplementedError

    def shutdown(self) -> None:
        pass


# ------------------------------------------------------------------
#  Kokoro (offline neural)
# ------------------------------------------------------------------

class KokoroBackend(TTSBackend):
    name = "kokoro"

    def __init__(self, voice: str = "af_bella", lang: str = "en-us"):
        self.voice = voice
        self.lang = lang
        self._pipeline = None
        try:
            from kokoro import KPipeline           # type: ignore
            self._pipeline = KPipeline(lang_code=lang[:2])
            self.available = True
            logger.info("Kokoro TTS ready")
        except Exception as e:
            logger.debug("Kokoro unavailable: {}", e)
            self.available = False

    def synth_to_file(self, text: str) -> Optional[str]:
        if not self.available or not text:
            return None
        try:
            import soundfile as sf                 # type: ignore
            import numpy as np                     # type: ignore
            chunks = []
            for _, _, audio in self._pipeline(text, voice=self.voice):
                chunks.append(audio)
            if not chunks:
                return None
            audio = np.concatenate(chunks)
            fd = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            fd.close()
            sf.write(fd.name, audio, 24000)
            return fd.name
        except Exception as e:
            logger.error("Kokoro synth failed: {}", e)
            return None


# ------------------------------------------------------------------
#  Edge-TTS (online neural, free)
# ------------------------------------------------------------------

class EdgeBackend(TTSBackend):
    name = "edge"
    DEFAULT_VOICES = {
        "en": "en-US-AriaNeural",
        "ur": "ur-PK-UzmaNeural",
    }

    def __init__(self, voice: Optional[str] = None):
        self.voice = voice or self.DEFAULT_VOICES["en"]
        try:
            import edge_tts                        # type: ignore
            self._edge_tts = edge_tts
            self.available = True
        except Exception as e:
            logger.debug("edge-tts unavailable: {}", e)
            self._edge_tts = None
            self.available = False

    def synth_to_file(self, text: str) -> Optional[str]:
        if not self.available or not text:
            return None
        import asyncio
        fd = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        fd.close()

        async def _do() -> bool:
            try:
                comm = self._edge_tts.Communicate(text, self.voice)
                await comm.save(fd.name)
                return True
            except Exception as e:
                logger.error("edge-tts synth failed: {}", e)
                return False

        try:
            ok = asyncio.run(_do())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                ok = loop.run_until_complete(_do())
            finally:
                loop.close()
        return fd.name if ok and os.path.exists(fd.name) else None


# ------------------------------------------------------------------
#  OpenAI TTS
# ------------------------------------------------------------------

class OpenAIBackend(TTSBackend):
    name = "openai"

    def __init__(self, model: str = "tts-1", voice: str = "alloy",
                 api_key: Optional[str] = None):
        self.model = model
        self.voice = voice
        self._client = None
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            self.available = False
            return
        try:
            from openai import OpenAI              # type: ignore
            self._client = OpenAI(api_key=key)
            self.available = True
        except Exception as e:
            logger.debug("OpenAI TTS unavailable: {}", e)
            self.available = False

    def synth_to_file(self, text: str) -> Optional[str]:
        if not self.available or not text:
            return None
        fd = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        fd.close()
        try:
            with self._client.audio.speech.with_streaming_response.create(
                model=self.model, voice=self.voice, input=text,
            ) as resp:
                resp.stream_to_file(fd.name)
            return fd.name
        except Exception as e:
            logger.error("OpenAI TTS failed: {}", e)
            return None


# ------------------------------------------------------------------
#  ElevenLabs TTS
# ------------------------------------------------------------------

class ElevenLabsBackend(TTSBackend):
    name = "elevenlabs"

    def __init__(self, voice: str = "Rachel", api_key: Optional[str] = None):
        self.voice = voice
        self._client = None
        key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not key:
            self.available = False
            return
        try:
            from elevenlabs.client import ElevenLabs  # type: ignore
            self._client = ElevenLabs(api_key=key)
            self.available = True
        except Exception as e:
            logger.debug("ElevenLabs unavailable: {}", e)
            self.available = False

    def synth_to_file(self, text: str) -> Optional[str]:
        if not self.available or not text:
            return None
        fd = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        fd.close()
        try:
            audio = self._client.text_to_speech.convert(
                voice_id=self.voice,
                model_id="eleven_multilingual_v2",
                text=text,
            )
            with open(fd.name, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            return fd.name
        except Exception as e:
            logger.error("ElevenLabs synth failed: {}", e)
            return None


# ------------------------------------------------------------------
#  Pyttsx3 (offline, last-resort fallback)
# ------------------------------------------------------------------

class Pyttsx3Backend(TTSBackend):
    name = "pyttsx3"

    def __init__(self, rate: int = 175, volume: float = 1.0):
        self.rate = rate
        self.volume = volume
        self._engine = None
        try:
            import pyttsx3                         # type: ignore
            self._pyttsx3 = pyttsx3
            self.available = True
        except Exception as e:
            logger.debug("pyttsx3 unavailable: {}", e)
            self.available = False

    def synth_to_file(self, text: str) -> Optional[str]:
        if not self.available or not text:
            return None
        fd = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        fd.close()
        try:
            eng = self._pyttsx3.init()
            eng.setProperty("rate", self.rate)
            eng.setProperty("volume", self.volume)
            eng.save_to_file(text, fd.name)
            eng.runAndWait()
            try:
                eng.stop()
            except Exception:
                pass
            return fd.name if os.path.exists(fd.name) else None
        except Exception as e:
            logger.error("pyttsx3 synth failed: {}", e)
            return None


# ------------------------------------------------------------------
#  TTS Engine (facade)
# ------------------------------------------------------------------

class TTSEngine:
    """
    Front-facing TTS engine. Selects the best available backend and
    exposes a small async speak API with a cancel primitive.
    """

    PREFERRED_ORDER = ("kokoro", "edge", "pyttsx3")

    def __init__(self, backend: Optional[str] = None,
                 voice: Optional[str] = None,
                 on_start: Optional[Callable[[], None]] = None,
                 on_finish: Optional[Callable[[], None]] = None):
        self._player  = _AudioPlayer()
        self._backend: Optional[TTSBackend] = None
        self._voice   = voice
        self._on_start = on_start
        self._on_finish = on_finish

        self._queue: "queue.Queue[Optional[str]]" = queue.Queue()
        self._stop_event = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._is_speaking = False
        self._lock = threading.RLock()

        self._choose_backend(backend)
        self._start_worker()

    # ------------------------------------------------------
    #  Backend selection
    # ------------------------------------------------------

    def _choose_backend(self, explicit: Optional[str]) -> None:
        candidates = [explicit] if explicit else list(self.PREFERRED_ORDER)
        for name in candidates:
            b = self._build_backend(name)
            if b and b.available:
                self._backend = b
                logger.info("TTS backend selected: {}", name)
                return
        logger.warning("No TTS backend available")

    def _build_backend(self, name: Optional[str]) -> Optional[TTSBackend]:
        if name is None:
            return None
        name = name.lower()
        if name == "kokoro":
            return KokoroBackend(voice=self._voice or "af_bella")
        if name == "edge":
            return EdgeBackend(voice=self._voice)
        if name == "openai":
            return OpenAIBackend(voice=self._voice or "alloy")
        if name == "elevenlabs":
            return ElevenLabsBackend(voice=self._voice or "Rachel")
        if name == "pyttsx3":
            return Pyttsx3Backend()
        return None

    def set_backend(self, name: str) -> bool:
        b = self._build_backend(name)
        if b and b.available:
            self._backend = b
            logger.info("TTS backend switched to {}", name)
            return True
        logger.warning("Requested backend '{}' unavailable", name)
        return False

    # ------------------------------------------------------
    #  Availability
    # ------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return self._backend is not None and self._player.available

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def backend_name(self) -> str:
        return self._backend.name if self._backend else "none"

    # ------------------------------------------------------
    #  Speak API
    # ------------------------------------------------------

    def speak(self, text: str, priority: bool = False) -> None:
        if not text or not text.strip():
            return
        if priority:
            self.stop()
        self._queue.put(text)

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
        self._player.stop()
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        self._is_speaking = False

    def shutdown(self) -> None:
        self.stop()
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=1.0)
        if self._backend is not None:
            try:
                self._backend.shutdown()
            except Exception:
                pass

    # ------------------------------------------------------
    #  Worker
    # ------------------------------------------------------

    def _start_worker(self) -> None:
        self._worker = threading.Thread(
            target=self._worker_loop, name="TTSWorker", daemon=True,
        )
        self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            text = self._queue.get()
            if text is None:
                return
            if self._backend is None:
                continue
            self._stop_event.clear()
            self._is_speaking = True
            if self._on_start:
                try:
                    self._on_start()
                except Exception:
                    pass

            path = self._backend.synth_to_file(text)
            if path and not self._stop_event.is_set():
                self._player.play_file(path, block=True, stop_event=self._stop_event)
            if path:
                try:
                    os.remove(path)
                except Exception:
                    pass

            self._is_speaking = False
            if self._on_finish:
                try:
                    self._on_finish()
                except Exception:
                    pass


__all__ = [
    "TTSEngine",
    "TTSBackend",
    "KokoroBackend",
    "EdgeBackend",
    "OpenAIBackend",
    "ElevenLabsBackend",
    "Pyttsx3Backend",
]
