"""
voice/interruption_handler.py — Mic-monitoring Interrupt for DREX

Monitors microphone while DREX is speaking.
If user speaks during TTS playback, stops audio immediately
and signals orchestrator to process new input.
"""

import threading
import time
from typing import Callable, Optional
from loguru import logger


class InterruptionHandler:
    """
    Monitors microphone while DREX is speaking.
    If user speaks during TTS playback, stops audio immediately
    and flags the orchestrator to process the new input.

    Uses a background thread that continuously monitors audio energy.
    When energy exceeds threshold while speaker is active -> interrupt.
    """

    def __init__(self, speaker, listener, threshold_multiplier: float = 1.5):
        """
        Args:
            speaker: The Speaker instance (must have is_speaking and stop()).
            listener: The Listener instance (for accessing PyAudio).
            threshold_multiplier: How much louder than ambient noise
                                  triggers an interruption (1.5 = 50% above baseline).
        """
        self._speaker = speaker
        self._listener = listener
        self._threshold_multiplier = threshold_multiplier
        self._ambient_level: Optional[float] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._available = False
        self._pyaudio = None
        self._stream = None
        self._lock = threading.Lock()

        # External callback — set from outside
        self.on_interrupt: Optional[Callable[[], None]] = None

        self._init_mic()

    def _init_mic(self):
        """Initialize PyAudio and test microphone access."""
        try:
            import pyaudio as pa

            self._pyaudio = pa
            audio = pa.PyAudio()

            # Find default input device info
            try:
                info = audio.get_default_input_device_info()
                self._device_index = info["index"]
                logger.debug(
                    "InterruptionHandler mic: {} (index {})",
                    info["name"], info["index"],
                )
            except Exception:
                self._device_index = None

            audio.terminate()
            self._available = True
            logger.info("✅ InterruptionHandler initialized")
        except ImportError:
            logger.warning("pyaudio not installed — interruption handler unavailable")
            self._available = False
        except Exception as e:
            logger.warning("InterruptionHandler mic init failed: {}", e)
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def calibrate_ambient(self, duration: float = 1.0):
        """
        Measure ambient noise level to use as baseline for interrupt detection.

        Args:
            duration: Seconds to sample ambient noise.
        """
        if not self._available or not self._pyaudio:
            return

        pa = self._pyaudio
        audio = pa.PyAudio()
        stream = None
        try:
            stream = audio.open(
                rate=16000,
                channels=1,
                format=pa.paInt16,
                input=True,
                input_device_index=self._device_index,
                frames_per_buffer=1024,
            )

            # Sample RMS energy over duration
            samples = []
            for _ in range(int(duration * 15)):  # ~15 reads per second
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                    # Calculate RMS
                    import struct
                    fmt = "h" * (len(data) // 2)
                    vals = struct.unpack(fmt, data)
                    rms = (sum(v * v for v in vals) / len(vals)) ** 0.5
                    samples.append(rms)
                except Exception:
                    continue
                time.sleep(0.065)

            if samples:
                self._ambient_level = sum(samples) / len(samples)
                logger.info(
                    "InterruptionHandler ambient level: {:.1f} (threshold: {:.1f})",
                    self._ambient_level,
                    self._ambient_level * self._threshold_multiplier,
                )
            else:
                logger.warning("No ambient samples collected")
        except Exception as e:
            logger.error("Ambient calibration failed: {}", e)
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            audio.terminate()

    def start_monitoring(self):
        """Start background thread monitoring for interruptions."""
        if not self._available:
            logger.warning("InterruptionHandler not available — cannot monitor")
            return

        with self._lock:
            if self._running:
                return

            self._stop_event.clear()
            self._running = True
            self._thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="drex-interrupt",
            )
            self._thread.start()
            logger.info("Interruption monitoring started")

    def stop_monitoring(self):
        """Stop monitoring thread cleanly."""
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            self._running = False
            if self._thread:
                self._thread.join(timeout=2.0)
                self._thread = None
            logger.info("Interruption monitoring stopped")

    def _monitor_loop(self):
        """
        Background thread loop.
        Samples microphone energy every 100ms.
        If speaker.is_speaking and energy > threshold -> trigger interrupt.
        """
        if not self._pyaudio:
            return

        pa = self._pyaudio
        audio = pa.PyAudio()
        stream = None
        try:
            stream = audio.open(
                rate=16000,
                channels=1,
                format=pa.paInt16,
                input=True,
                input_device_index=self._device_index,
                frames_per_buffer=1024,
            )

            while not self._stop_event.is_set():
                # Only monitor when speaker is active
                if not self._speaker.is_speaking:
                    time.sleep(0.05)
                    continue

                try:
                    data = stream.read(1024, exception_on_overflow=False)
                    import struct
                    fmt = "h" * (len(data) // 2)
                    vals = struct.unpack(fmt, data)
                    rms = (sum(v * v for v in vals) / len(vals)) ** 0.5
                except Exception:
                    time.sleep(0.02)
                    continue

                # Check if energy exceeds threshold
                if self._ambient_level is not None:
                    threshold = self._ambient_level * self._threshold_multiplier
                    if rms > threshold and self._speaker.is_speaking:
                        self._trigger_interrupt()
                        # Brief cooldown to avoid re-triggering
                        time.sleep(0.3)

                time.sleep(0.1)

        except Exception as e:
            logger.error("Interruption monitor loop error: {}", e)
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            audio.terminate()

    def _trigger_interrupt(self):
        """
        1. Call speaker.stop() to halt current TTS playback
        2. Log the interruption
        3. Signal orchestrator via on_interrupt callback
        """
        logger.info("🔇 Interruption detected — stopping speech")
        try:
            self._speaker.stop()
        except Exception as e:
            logger.error("Speaker stop during interrupt failed: {}", e)

        if self.on_interrupt:
            try:
                self.on_interrupt()
            except Exception as e:
                logger.error("Interruption callback error: {}", e)

    def shutdown(self):
        """Clean shutdown."""
        self.stop_monitoring()
        self._available = False
        self._pyaudio = None
        logger.info("InterruptionHandler shutdown")