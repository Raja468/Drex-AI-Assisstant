"""
voice/vad.py - Voice Activity Detection.

Primary backend: Silero VAD (torch). If torch is unavailable, falls back
to an RMS-energy detector that is still usable in noisy conditions with
manual calibration.

Both backends expose the same interface:
    detector.is_speech(pcm_bytes: bytes) -> bool
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from loguru import logger


class _EnergyVAD:
    """Simple RMS energy VAD - fallback when torch is unavailable."""

    def __init__(self, threshold: float = 500.0):
        self.threshold = threshold

    def is_speech(self, pcm_bytes: bytes) -> bool:
        if not pcm_bytes:
            return False
        arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        if arr.size == 0:
            return False
        rms = float(np.sqrt(np.mean(arr * arr)))
        return rms >= self.threshold

    def reset(self) -> None:
        pass


class _SileroVAD:
    """Silero VAD backed by torch (loads once, kept in memory)."""

    def __init__(self, threshold: float = 0.45):
        self.threshold = threshold
        self._model = None
        self._torch = None
        self._load()

    def _load(self) -> None:
        try:
            import torch                          # type: ignore
            self._torch = torch
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True,
                verbose=False,
            )
            model.eval()
            self._model = model
            logger.info("Silero VAD loaded")
        except Exception as e:
            logger.warning("Silero VAD unavailable: {}", e)
            self._model = None
            self._torch = None

    @property
    def available(self) -> bool:
        return self._model is not None and self._torch is not None

    def is_speech(self, pcm_bytes: bytes) -> bool:
        if not self.available or not pcm_bytes:
            return False
        try:
            audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            tensor = self._torch.from_numpy(audio)
            with self._torch.no_grad():
                prob = float(self._model(tensor, 16000).item())
            return prob >= self.threshold
        except Exception as e:
            logger.debug("Silero VAD inference error: {}", e)
            return False

    def reset(self) -> None:
        try:
            if self._model is not None:
                self._model.reset_states()
        except Exception:
            pass


class VAD:
    """
    Facade around Silero VAD with automatic fallback to energy VAD.
    The public interface is intentionally tiny.
    """

    def __init__(self, prefer_silero: bool = True, energy_threshold: float = 500.0):
        self._silero: Optional[_SileroVAD] = None
        self._energy = _EnergyVAD(threshold=energy_threshold)

        if prefer_silero:
            silero = _SileroVAD()
            if silero.available:
                self._silero = silero

    @property
    def backend(self) -> str:
        return "silero" if self._silero is not None else "energy"

    def is_speech(self, pcm_bytes: bytes) -> bool:
        if self._silero is not None:
            return self._silero.is_speech(pcm_bytes)
        return self._energy.is_speech(pcm_bytes)

    def reset(self) -> None:
        if self._silero is not None:
            self._silero.reset()
        self._energy.reset()

    def calibrate(self, frames: list, multiplier: float = 2.0) -> None:
        """Tune the energy-VAD threshold from ambient noise samples."""
        if not frames:
            return
        rms_values = []
        for f in frames:
            arr = np.frombuffer(f, dtype=np.int16).astype(np.float32)
            if arr.size:
                rms_values.append(float(np.sqrt(np.mean(arr * arr))))
        if rms_values:
            avg = sum(rms_values) / len(rms_values)
            self._energy.threshold = max(300.0, avg * multiplier)
            logger.debug("Energy VAD calibrated: threshold={:.1f}", self._energy.threshold)


# Legacy names kept so any lingering `from voice.vad import ...` won't crash.
VoiceActivityDetector = VAD
