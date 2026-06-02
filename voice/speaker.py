"""
voice/speaker.py — Dual-engine TTS Speaker for DREX

Supports two TTS engines:
  - pyttsx3 (offline, local SAPI5 voices on Windows)
  - edge-tts (online, Microsoft neural voices via Edge TTS service)

Engine selection is controlled via the TTS_ENGINE env var.
If the selected engine fails at runtime, falls back to the other.

VOICE PIPELINE HARDENING:
  ✓ Interruption support — stop() aborts playback immediately
  ✓ Speaking mutex — prevents self-listening race conditions
  ✓ Clean shutdown — pygame resources released properly
  ✓ Thread-safe lifecycle
"""

import asyncio
import os
import queue
import tempfile
import threading
from typing import Optional

from loguru import logger
from config import get_config

# ─────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────

_TEMP_DIR = os.path.join(tempfile.gettempdir(), "drex_tts")
os.makedirs(_TEMP_DIR, exist_ok=True)


class Speaker:
    """
    Thread-safe dual-engine TTS speaker with interruption support.

    Uses a background worker thread and a queue for non-blocking speech.
    Supports runtime engine switching via set_engine().
    """

    def __init__(self):
        self.cfg = get_config().voice
        self._pyttsx3_engine = None  # lazy init for pyttsx3
        self._current_engine: str = self.cfg.tts_engine  # "pyttsx3" or "edge"
        self._edge_available: Optional[bool] = None  # lazily determined

        # Queue-based worker thread architecture
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._speaking = False
        self._interrupt_event = threading.Event()

        self._init_pyttsx3()
        self._start_worker()

        engine_display = self._current_engine.upper()
        if self._current_engine == "edge":
            logger.info(
                "Speaker ready | Engine: edge-tts | Voice: {} | Rate: {} | Volume: {}",
                self.cfg.edge_voice,
                self.cfg.edge_rate,
                self.cfg.edge_volume,
            )
        else:
            logger.info(
                "Speaker ready | Engine: pyttsx3 | Rate: {} | Volume: {}",
                self.cfg.rate,
                self.cfg.volume,
            )

    # ──────────────────────────────────────────────────────────
    #  ENGINE INITIALISATION
    # ──────────────────────────────────────────────────────────

    def _init_pyttsx3(self):
        """Initialise the pyttsx3 engine (called once at startup)."""
        try:
            import pyttsx3

            self._pyttsx3_engine = pyttsx3.init()
            self._pyttsx3_engine.setProperty("rate", self.cfg.rate)
            self._pyttsx3_engine.setProperty("volume", self.cfg.volume)

            voices = self._pyttsx3_engine.getProperty("voices")
            if voices:
                idx = min(self.cfg.voice_index, len(voices) - 1)
                self._pyttsx3_engine.setProperty("voice", voices[idx].id)
                logger.debug(
                    "pyttsx3 voice: {} | Rate: {} | Volume: {}",
                    voices[idx].name,
                    self.cfg.rate,
                    self.cfg.volume,
                )
            else:
                logger.warning("No pyttsx3 voices found on this system")
        except Exception as e:
            logger.error("pyttsx3 init failed: {}", e)
            self._pyttsx3_engine = None

    def _check_edge_available(self) -> bool:
        """Check if edge-tts is importable."""
        if self._edge_available is not None:
            return self._edge_available
        try:
            import edge_tts  # noqa: F401

            self._edge_available = True
            logger.debug("edge-tts is available")
        except ImportError:
            self._edge_available = False
            logger.warning("edge-tts is not installed")
        return self._edge_available

    # ──────────────────────────────────────────────────────────
    #  WORKER THREAD
    # ──────────────────────────────────────────────────────────

    def _start_worker(self):
        """Start the background worker thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="drex-speaker"
        )
        self._thread.start()

    def _worker(self):
        """Background thread: pull items from queue and speak them."""
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

    # ──────────────────────────────────────────────────────────
    #  CORE SPEAK METHODS
    # ──────────────────────────────────────────────────────────

    def _speak_sync(self, text: str):
        """
        Speak text synchronously (blocks until done).
        Routes to the active engine.

        ALWAYS clears interrupt_event before speaking, since this is
        a fresh speech request. The interrupt event was set by a prior
        stop() and should not block subsequent speech.
        """
        self._speaking = True
        self._interrupt_event.clear()
        try:
            if self._current_engine == "edge":
                self._speak_edge(text)
            else:
                self._speak_pyttsx3(text)
        except Exception as e:
            logger.error("TTS speak error ({}): {}", self._current_engine, e)
            # Fallback: try the other engine
            if self._current_engine == "edge":
                logger.warning("edge-tts failed, falling back to pyttsx3")
                self._current_engine = "pyttsx3"
                try:
                    self._speak_pyttsx3(text)
                except Exception as e2:
                    logger.error("pyttsx3 fallback also failed: {}", e2)
            else:
                logger.warning("pyttsx3 failed, falling back to edge-tts")
                self._current_engine = "edge"
                try:
                    self._speak_edge(text)
                except Exception as e2:
                    logger.error("edge-tts fallback also failed: {}", e2)
        finally:
            self._speaking = False

    def _speak_pyttsx3(self, text: str):
        """Speak using pyttsx3 (offline, synchronous)."""
        if not self._pyttsx3_engine:
            logger.warning("pyttsx3 engine not available, cannot speak: {}", text[:50])
            return
        self._pyttsx3_engine.say(text)
        self._pyttsx3_engine.runAndWait()

    def _speak_edge(self, text: str):
        """
        Speak using edge-tts (online, neural voices).

        Saves audio to a temp file, then plays it with pygame.
        Supports interruption via stop().

        HARDENING: pygame.mixer.music is checked each loop iteration
        for stop events, allowing near-instant interruption.
        """
        if not self._check_edge_available():
            logger.warning("edge-tts not available, cannot speak with edge engine")
            raise RuntimeError("edge-tts not installed")

        import edge_tts

        # Generate a unique temp file name
        tmp_file = os.path.join(_TEMP_DIR, f"drex_tts_{threading.get_ident()}.mp3")

        async def _do_tts():
            communicate = edge_tts.Communicate(
                text,
                voice=self.cfg.edge_voice,
                rate=self.cfg.edge_rate,
                volume=self.cfg.edge_volume,
            )
            await communicate.save(tmp_file)

        # Run the async edge-tts call synchronously
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_do_tts())
        finally:
            loop.close()

        # Play the generated audio file (blocks) via pygame with interrupt support
        if os.path.exists(tmp_file):
            try:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(tmp_file)
                pygame.mixer.music.play()
                # Poll playback status + interrupt event for responsive stop
                while pygame.mixer.music.get_busy():
                    if self._interrupt_event.wait(timeout=0.05):
                        pygame.mixer.music.stop()
                        break
                pygame.mixer.quit()
            except Exception as e:
                logger.error("pygame playback failed: {}", e)
                raise
            finally:
                try:
                    os.remove(tmp_file)
                except PermissionError:
                    logger.warning("Could not remove temp TTS file: {}", tmp_file)

    # ──────────────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────────────

    def speak(self, text: str, priority: bool = False):
        """
        Queue text for speaking (non-blocking).

        Args:
            text: Text to speak.
            priority: If True, clear current queue and speak this immediately.
        """
        if not text or not text.strip():
            return
        clean = self._clean_text(text)
        if priority:
            self._clear_queue()
        self._queue.put(clean)
        logger.debug("Queued speech: {}...", clean[:60])

    def speak_sync(self, text: str):
        """Speak immediately on the calling thread (blocks until done)."""
        clean = self._clean_text(text)
        self._speak_sync(clean)

    def set_engine(self, engine: str):
        """
        Switch TTS engine at runtime.

        Args:
            engine: "pyttsx3" or "edge"
        """
        engine = engine.lower().strip()
        if engine not in ("pyttsx3", "edge"):
            logger.warning("Unknown TTS engine '{}', keeping current ({})", engine, self._current_engine)
            return
        if engine != self._current_engine:
            self._current_engine = engine
            logger.info("TTS engine switched to: {}", engine)

    @property
    def is_speaking(self) -> bool:
        """Return True if currently speaking."""
        return self._speaking

    @property
    def is_available(self) -> bool:
        """Return True if at least one engine is available."""
        if self._current_engine == "edge":
            return self._check_edge_available()
        return self._pyttsx3_engine is not None

    def set_rate(self, rate: int):
        """Set pyttsx3 speech rate (words per minute)."""
        self.cfg.rate = rate
        if self._pyttsx3_engine:
            self._pyttsx3_engine.setProperty("rate", rate)

    def set_volume(self, volume: float):
        """Set pyttsx3 volume (0.0 to 1.0)."""
        self.cfg.volume = volume
        if self._pyttsx3_engine:
            self._pyttsx3_engine.setProperty("volume", volume)

    def list_voices(self) -> list[dict]:
        """List available pyttsx3 voices."""
        if not self._pyttsx3_engine:
            return []
        voices = self._pyttsx3_engine.getProperty("voices")
        return [
            {"id": i, "name": v.name, "lang": getattr(v, "languages", [""])[0]}
            for i, v in enumerate(voices)
        ]

    def stop(self):
        """
        Stop speaking and clear the queue immediately.

        HARDENED: Sets interrupt event so edge-tts playback aborts
        within 50ms instead of waiting for full audio to complete.
        Also stops pyttsx3 and clears pending speech.
        """
        self._interrupt_event.set()
        self._clear_queue()
        if self._pyttsx3_engine:
            try:
                self._pyttsx3_engine.stop()
            except Exception:
                pass

    def _clear_queue(self):
        """Remove all pending items from the speech queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _clean_text(self, text: str) -> str:
        """
        Remove markdown formatting and symbols that sound bad in TTS.

        Strips: bold (**), headers (#), inline code (`), links, italics (_).
        """
        import re

        text = re.sub(r"\*+", "", text)
        text = re.sub(r"#+\s", "", text)
        text = re.sub(r"`+", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
        return text.strip()

    def shutdown(self):
        """Shut down the speaker thread and clean up resources."""
        logger.info("Speaker shutting down...")
        self.stop()  # Stop any in-progress speech immediately
        self._running = False
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2)
        # Clean up temp dir
        try:
            for f in os.listdir(_TEMP_DIR):
                try:
                    os.remove(os.path.join(_TEMP_DIR, f))
                except Exception:
                    pass
        except Exception:
            pass
        logger.info("Speaker shutdown complete")