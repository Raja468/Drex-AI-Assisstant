"""
DEPRECATED -- Sprint-4 Modern Voice Stack

This module is NOT currently wired into the main application flow.
The application uses the legacy Listener (voice/listener.py) with
Google STT. This code is preserved for future integration. Do not delete.

---

voice/whisper_engine.py - Faster-Whisper backend.

Provides accurate offline speech-to-text with automatic language
detection. Optimized for English + Urdu (both supported natively by
Whisper). Mixed-language utterances are handled by leaving the language
setting on ``None`` (auto-detect).
"""

from __future__ import annotations

import io
import tempfile
import wave
from typing import Optional

import numpy as np
from loguru import logger


DEFAULT_MODEL_SIZE = "base"      # tiny | base | small | medium | large-v3
DEFAULT_DEVICE     = "auto"      # auto | cpu | cuda
DEFAULT_COMPUTE    = "auto"      # auto | int8 | float16 | float32


class WhisperEngine:
    """
    Wraps :mod:`faster_whisper` for streaming-friendly transcription.

    Model is loaded lazily on the first call to :meth:`transcribe` so
    startup time stays fast. The model is kept in memory afterwards.
    """

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = DEFAULT_DEVICE,
        compute_type: str = DEFAULT_COMPUTE,
        language: Optional[str] = None,
    ):
        self.model_size   = model_size
        self.device       = device
        self.compute_type = compute_type
        self.language     = language        # None = auto-detect

        self._model = None
        self._available: Optional[bool] = None

    # -----------------------------------------------------
    #  Model loading
    # -----------------------------------------------------

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if self._available is False:
            return False
        try:
            from faster_whisper import WhisperModel   # type: ignore
        except Exception as e:
            logger.warning("faster-whisper not installed: {}", e)
            self._available = False
            return False

        try:
            device       = self._resolve_device()
            compute_type = self._resolve_compute(device)
            logger.info(
                "Loading Faster-Whisper model={} device={} compute={}",
                self.model_size, device, compute_type,
            )
            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            )
            self._available = True
            return True
        except Exception as e:
            logger.error("Faster-Whisper load failed: {}", e)
            self._available = False
            return False

    def _resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch                              # type: ignore
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _resolve_compute(self, device: str) -> str:
        if self.compute_type != "auto":
            return self.compute_type
        return "float16" if device == "cuda" else "int8"

    @property
    def is_available(self) -> bool:
        if self._available is None:
            self._ensure_model()
        return bool(self._available)

    # -----------------------------------------------------
    #  Transcription
    # -----------------------------------------------------

    def transcribe(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> Optional[str]:
        """
        Convert 16-bit PCM audio bytes into text.

        Returns None if transcription fails or produces no result.
        """
        if not pcm_bytes:
            return None
        if not self._ensure_model():
            return None

        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if audio.size == 0:
            return None

        lang = language if language is not None else self.language

        try:
            segments, info = self._model.transcribe(
                audio,
                language=lang,
                beam_size=1,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            parts = [seg.text for seg in segments]
            text = " ".join(p.strip() for p in parts).strip()
            detected = getattr(info, "language", None)
            if detected:
                logger.debug("Whisper: detected language={}", detected)
            return text or None
        except Exception as e:
            logger.error("Whisper transcription failed: {}", e)
            return None

    def transcribe_wav(self, wav_path: str, language: Optional[str] = None) -> Optional[str]:
        if not self._ensure_model():
            return None
        try:
            segments, _ = self._model.transcribe(
                wav_path,
                language=language if language is not None else self.language,
                beam_size=1,
                vad_filter=False,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return text or None
        except Exception as e:
            logger.error("Whisper wav transcription failed: {}", e)
            return None

    # -----------------------------------------------------
    #  Utility: PCM -> WAV bytes (for debugging or persistence)
    # -----------------------------------------------------

    @staticmethod
    def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    @staticmethod
    def pcm_to_wav_file(pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        fd = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            with wave.open(fd, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm_bytes)
            return fd.name
        finally:
            fd.close()

    def shutdown(self) -> None:
        self._model = None
