"""
DEPRECATED -- Sprint-4 Modern Voice Stack

This module is NOT currently wired into the main application flow.
The application uses the legacy Listener (voice/listener.py).
This code is preserved for future integration. Do not delete.

---

voice/speech_to_text.py - STT facade.

Currently wraps Faster-Whisper via :class:`WhisperEngine`, but presents
a minimal, backend-agnostic surface so we can swap in a different STT
engine (Vosk, Deepgram, Whisper.cpp) without touching call sites.
"""

from __future__ import annotations

from typing import Optional

from voice.whisper_engine import WhisperEngine


class SpeechToText:
    """
    Thin wrapper over :class:`WhisperEngine` with a stable API.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        language: Optional[str] = None,
    ):
        self._engine = WhisperEngine(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            language=language,
        )

    @property
    def is_available(self) -> bool:
        return self._engine.is_available

    def transcribe(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> Optional[str]:
        return self._engine.transcribe(pcm_bytes, sample_rate, language)

    def shutdown(self) -> None:
        self._engine.shutdown()
