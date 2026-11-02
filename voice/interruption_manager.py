"""
voice/interruption_manager.py - Detects user barge-in while TTS speaks.

Runs a lightweight VAD loop that samples the microphone while the
assistant is speaking. When sustained voice activity is detected,
it fires an ``on_interrupt`` callback so the caller can stop TTS and
start listening.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from loguru import logger

from voice.audio_stream import AudioStream
from voice.vad import VAD


class InterruptionManager:
    """
    Barge-in detector.

    Owns its own :class:`AudioStream` so it can listen while TTS is
    playing without competing with the main :class:`VoiceManager`
    capture loop.
    """

    def __init__(
        self,
        vad: Optional[VAD] = None,
        on_interrupt: Optional[Callable[[], None]] = None,
        min_speech_frames: int = 4,
    ):
        self._vad = vad or VAD()
        self._on_interrupt = on_interrupt
        self._min_speech_frames = min_speech_frames

        self._stream: Optional[AudioStream] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def set_on_interrupt(self, cb: Optional[Callable[[], None]]) -> None:
        self._on_interrupt = cb

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._stream = AudioStream()
            if not self._stream.start():
                self._stream = None
                logger.debug("InterruptionManager: mic unavailable")
                return False
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop, name="InterruptionMonitor", daemon=True,
            )
            self._thread.start()
            logger.debug("InterruptionManager started (vad={})", self._vad.backend)
            return True

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:
                pass
            self._stream = None

    def _loop(self) -> None:
        speech_frames = 0
        # Small settle delay so we don't detect the tail of the last utterance
        time.sleep(0.15)
        while not self._stop_event.is_set() and self._stream is not None:
            frame = self._stream.read_frame(timeout=0.3)
            if frame is None:
                continue
            if self._vad.is_speech(frame):
                speech_frames += 1
                if speech_frames >= self._min_speech_frames:
                    logger.info("Interruption detected (barge-in)")
                    if self._on_interrupt is not None:
                        try:
                            self._on_interrupt()
                        except Exception as e:
                            logger.error("on_interrupt callback error: {}", e)
                    speech_frames = 0
                    # Cool-off so a single interruption doesn't re-fire.
                    time.sleep(0.4)
            else:
                speech_frames = max(0, speech_frames - 1)
