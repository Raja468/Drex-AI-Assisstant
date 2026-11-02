"""
voice/audio_stream.py - Non-blocking microphone capture.

Wraps PyAudio with a background worker thread that produces PCM16 frames
into a queue. Uses a fixed sample rate (16 kHz mono) which matches the
requirements of Silero VAD and Faster-Whisper.
"""

from __future__ import annotations

import queue
import threading
from typing import Optional

import numpy as np
from loguru import logger

try:
    import pyaudio
except Exception as e:  # pragma: no cover - system dependent
    pyaudio = None
    logger.warning("pyaudio import failed: {}", e)


SAMPLE_RATE = 16000
FRAME_MS    = 30            # 30 ms VAD frames -> 480 samples @ 16 kHz
FRAME_SIZE  = SAMPLE_RATE * FRAME_MS // 1000
CHANNELS    = 1
FORMAT      = getattr(pyaudio, "paInt16", 8) if pyaudio else 8


class AudioStream:
    """Background microphone capture with a bounded frame queue."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        frame_size: int = FRAME_SIZE,
        device_index: Optional[int] = None,
        max_queue: int = 100,
    ):
        self.sample_rate  = sample_rate
        self.frame_size   = frame_size
        self.device_index = device_index

        self._pa: Optional["pyaudio.PyAudio"] = None
        self._stream = None
        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=max_queue)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # -----------------------------------------------------
    #  Availability
    # -----------------------------------------------------

    @property
    def is_available(self) -> bool:
        if pyaudio is None:
            return False
        try:
            pa = pyaudio.PyAudio()
            count = pa.get_device_count()
            pa.terminate()
            return count > 0
        except Exception:
            return False

    # -----------------------------------------------------
    #  Lifecycle
    # -----------------------------------------------------

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            if pyaudio is None:
                logger.error("AudioStream: pyaudio not installed")
                return False
            try:
                self._pa = pyaudio.PyAudio()
                self._stream = self._pa.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=self.device_index,
                    frames_per_buffer=self.frame_size,
                )
            except Exception as e:
                logger.error("AudioStream: failed to open mic: {}", e)
                self._cleanup()
                return False

            self._running = True
            self._thread = threading.Thread(
                target=self._capture_loop,
                name="AudioStream",
                daemon=True,
            )
            self._thread.start()
            logger.debug("AudioStream started (rate={} frame={})",
                         self.sample_rate, self.frame_size)
            return True

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._cleanup()
        # Drain any leftover frames
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
        except Exception:
            pass

    def _cleanup(self):
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    # -----------------------------------------------------
    #  Capture loop
    # -----------------------------------------------------

    def _capture_loop(self):
        while self._running:
            try:
                data = self._stream.read(self.frame_size, exception_on_overflow=False)
            except Exception as e:
                logger.debug("AudioStream: read error: {}", e)
                continue
            try:
                self._queue.put_nowait(data)
            except queue.Full:
                # Drop the oldest frame if consumer is slow
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(data)
                except Exception:
                    pass

    # -----------------------------------------------------
    #  Consumer API
    # -----------------------------------------------------

    def read_frame(self, timeout: float = 0.5) -> Optional[bytes]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @staticmethod
    def bytes_to_float32(data: bytes) -> np.ndarray:
        return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

    @staticmethod
    def rms(data: bytes) -> float:
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        if arr.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(arr * arr)))
