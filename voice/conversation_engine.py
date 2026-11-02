"""
voice/conversation_engine.py — Duplex Voice Conversation Engine for DREX

Replaces the simple "listen → transcribe → process → repeat" loop with
a true duplex conversation that feels like ChatGPT Voice Mode:

  - Continuous audio capture via AudioStream
  - Real-time VAD-based speech/silence turn detection
  - Automatic endpointing (no button press after every sentence)
  - Interruption-aware: detects user speech during TTS and barge-in
  - Seamless listen→process→speak→listen flow
  - Echo mitigation via speaker-state gating and cooldown
  - Configurable silence timeout, min/max utterance duration

Integrates with the existing Speaker for auto-pause/resume around TTS.
The InterruptionHandler is NOT required when this engine is active —
the engine handles both conversation listening and interruption detection
from a single AudioStream source.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from loguru import logger

import speech_recognition as sr
from voice.audio_stream import AudioStream
from voice.vad import VAD
from config import get_config


class ConversationState:
    """States for the duplex conversation engine."""
    IDLE = "idle"
    LISTENING = "listening"
    HEARING = "hearing"
    THINKING = "thinking"
    WAITING = "waiting"


class ConversationEngine:
    """
    Duplex voice conversation engine with automatic turn detection.

    Architecture:
      - AudioStream provides continuous 16kHz mono PCM frames
      - VAD distinguishes speech from silence in real time
      - Speech frames are accumulated until silence times out
      - Google STT transcribes the complete utterance
      - Orchestrator callback receives the transcribed text
      - During TTS, the engine monitors for interruption (barge-in)

    The engine auto-manages its listen/speak state by monitoring
    the Speaker's is_speaking property and applying cooldown periods.
    """

    SILENCE_TIMEOUT_MS = 800
    MIN_UTTERANCE_MS = 300
    MAX_UTTERANCE_MS = 15000
    PRE_ROLL_FRAMES = 5
    TTS_COOLDOWN_MS = 300
    INTERRUPT_SPEECH_FRAMES = 8
    INTERRUPT_SILENCE_MS = 600

    def __init__(self):
        self.cfg = get_config().voice

        self._audio_stream: Optional[AudioStream] = None
        self._vad: Optional[VAD] = None
        self._recognizer: Optional[sr.Recognizer] = None

        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._speaker = None

        self.on_utterance: Optional[Callable[[str], None]] = None
        self.on_interruption: Optional[Callable[[], None]] = None
        self.on_speech_start: Optional[Callable[[], None]] = None
        self.on_state_change: Optional[Callable[[str, str], None]] = None

        self._utterance_count = 0
        self._interruption_count = 0
        self._state = ConversationState.IDLE

        self._init()

    def _init(self):
        self._vad = VAD(prefer_silero=True)
        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = True
        logger.info("ConversationEngine init | VAD: {}", self._vad.backend)

    def wire_speaker(self, speaker):
        self._speaker = speaker

    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, new_state: str):
        old = self._state
        self._state = new_state
        if old != new_state and self.on_state_change:
            try:
                self.on_state_change(old, new_state)
            except Exception:
                pass

    @property
    def stats(self) -> dict:
        return {
            "utterance_count": self._utterance_count,
            "interruption_count": self._interruption_count,
            "state": self._state,
            "vad_backend": self._vad.backend if self._vad else "none",
        }

    # ── Lifecycle ──────────────────────────────────────────

    def start(self, on_utterance: Callable[[str], None] = None):
        with self._lock:
            if self._running:
                return
            self._stop_event.clear()
            self._running = True
            self._paused = False

        if on_utterance:
            self.on_utterance = on_utterance

        if not self._audio_stream:
            self._audio_stream = AudioStream()
        if not self._audio_stream.start():
            self._running = False
            logger.error("ConversationEngine: audio stream start failed")
            return

        self._calibrate()
        self._set_state(ConversationState.LISTENING)

        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="drex-conversation"
        )
        self._thread.start()
        logger.info("ConversationEngine started — duplex active")

    def _calibrate(self):
        frames = [self._audio_stream.read_frame(timeout=0.1) for _ in range(30)]
        valid = [f for f in frames if f]
        if valid and self._vad:
            self._vad.calibrate(valid, multiplier=2.5)
            logger.debug("VAD calibrated ({} ambient frames)", len(valid))

    def stop(self):
        with self._lock:
            self._running = False
            self._stop_event.set()

        if self._audio_stream:
            self._audio_stream.stop()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None

        self._set_state(ConversationState.IDLE)
        logger.info("ConversationEngine stopped")

    def pause(self):
        """Pause listening — called by orchestrator when processing begins."""
        with self._lock:
            self._paused = True
        self._set_state(ConversationState.THINKING)
        logger.debug("ConversationEngine paused (processing)")

    def resume(self):
        """Unpause — called by orchestrator after full response delivery."""
        with self._lock:
            self._paused = False
        self._set_state(ConversationState.WAITING)
        logger.debug("ConversationEngine unpaused — will resume after cooldown")

    def shutdown(self):
        self.stop()
        self._audio_stream = None
        self._vad = None
        self._recognizer = None
        self._speaker = None
        logger.info("ConversationEngine shutdown")

    # ── Main Loop ──────────────────────────────────────────

    def _loop(self):
        """Main duplex conversation loop."""
        self._set_state(ConversationState.LISTENING)

        speech_buffer: list[bytes] = []
        pre_roll: list[bytes] = []
        speaking = False
        silence_count = 0
        speech_count = 0

        interrupt_buffer: list[bytes] = []
        interrupt_count = 0
        interrupt_silence = 0

        was_speaker_active = False
        cooldown_end = 0.0

        FRAME_MS = 30
        SILENCE_MAX = max(1, int(self.SILENCE_TIMEOUT_MS / FRAME_MS))
        SPEECH_MIN = max(2, int(self.MIN_UTTERANCE_MS / FRAME_MS))
        SPEECH_MAX = int(self.MAX_UTTERANCE_MS / FRAME_MS)
        INT_SPEECH_MIN = self.INTERRUPT_SPEECH_FRAMES
        INT_SILENCE_MAX = max(1, int(self.INTERRUPT_SILENCE_MS / FRAME_MS))

        while not self._stop_event.is_set():
            now = time.time()

            # ── Speaker state tracking ──
            speaker_active = self._speaker and getattr(self._speaker, "is_speaking", False)

            if was_speaker_active and not speaker_active:
                cooldown_end = now + (self.TTS_COOLDOWN_MS / 1000.0)
            was_speaker_active = speaker_active

            # ── Interruption monitoring during speaker activity ──
            if speaker_active:
                frame = self._audio_stream.read_frame(timeout=0.05)
                if frame is not None:
                    is_speech = self._vad.is_speech(frame) if self._vad else False
                    if is_speech:
                        if interrupt_count == 0:
                            interrupt_buffer = [frame]
                            interrupt_count = 1
                            interrupt_silence = 0
                        else:
                            interrupt_buffer.append(frame)
                            interrupt_count += 1
                            interrupt_silence = 0

                        if interrupt_count >= INT_SPEECH_MIN:
                            self._handle_interruption(interrupt_buffer)
                            interrupt_buffer = []
                            interrupt_count = 0
                            interrupt_silence = 0
                    else:
                        if interrupt_count > 0:
                            interrupt_silence += 1
                            if interrupt_silence >= INT_SILENCE_MAX:
                                interrupt_buffer = []
                                interrupt_count = 0
                                interrupt_silence = 0

                # Reset conversation buffers during speaker activity
                if speaking:
                    speaking = False
                    speech_buffer = []
                    speech_count = 0
                    silence_count = 0

                time.sleep(0.02)
                continue

            # ── Wait during orchestrator pause ──
            if self._paused:
                time.sleep(0.05)
                continue

            # ── Cooldown after TTS stops ──
            if now < cooldown_end:
                self._set_state(ConversationState.WAITING)
                time.sleep(0.05)
                continue
            elif self._state == ConversationState.WAITING:
                self._set_state(ConversationState.LISTENING)

            # ── Read frame ──
            frame = self._audio_stream.read_frame(timeout=0.05)
            if frame is None:
                continue

            is_speech = self._vad.is_speech(frame) if self._vad else False

            if is_speech:
                if not speaking:
                    speaking = True
                    speech_buffer = list(pre_roll[-self.PRE_ROLL_FRAMES:])
                    speech_count = len(speech_buffer)
                    silence_count = 0
                    self._set_state(ConversationState.HEARING)
                    if self.on_speech_start:
                        try:
                            self.on_speech_start()
                        except Exception:
                            pass

                speech_buffer.append(frame)
                speech_count += 1
                silence_count = 0

                if speech_count >= SPEECH_MAX:
                    self._transcribe_and_dispatch(speech_buffer)
                    speaking = False
                    speech_buffer = []
                    speech_count = 0
                    self._set_state(ConversationState.LISTENING)
                    time.sleep(0.1)
            else:
                pre_roll.append(frame)
                if len(pre_roll) > self.PRE_ROLL_FRAMES * 3:
                    pre_roll = pre_roll[-self.PRE_ROLL_FRAMES * 3:]

                if speaking:
                    silence_count += 1
                    if silence_count >= SILENCE_MAX:
                        if speech_count >= SPEECH_MIN:
                            self._transcribe_and_dispatch(speech_buffer)
                        else:
                            ms_dur = speech_count * FRAME_MS
                            logger.debug("Utterance too short ({}ms), ignored", ms_dur)

                        speaking = False
                        speech_buffer = []
                        speech_count = 0
                        silence_count = 0
                        self._set_state(ConversationState.LISTENING)

        logger.info("ConversationEngine loop exited")

    # ── Interruption ───────────────────────────────────────

    def _handle_interruption(self, frames: list[bytes]):
        self._interruption_count += 1
        logger.info("🔇 Barge-in detected — {} frames", len(frames))

        if self._speaker:
            try:
                self._speaker.stop()
            except Exception:
                pass

        if self.on_interruption:
            try:
                self.on_interruption()
            except Exception:
                pass

        self._transcribe_and_dispatch(frames)

    # ── Transcription ──────────────────────────────────────

    def _transcribe_and_dispatch(self, frames: list[bytes]):
        raw = b"".join(frames)

        try:
            audio_data = sr.AudioData(
                raw, sample_rate=16000, sample_width=2
            )
        except Exception as e:
            logger.error("AudioData creation failed: {}", e)
            return

        try:
            text = self._recognizer.recognize_google(
                audio_data, language=self.cfg.language
            )
        except sr.UnknownValueError:
            logger.debug("VAD triggered but STT returned no text")
            return
        except sr.RequestError as e:
            logger.warning("Google STT error: {}", e)
            return
        except Exception as e:
            logger.error("Transcription error: {}", e)
            return

        if not text or not text.strip():
            return

        self._utterance_count += 1
        duration = len(frames) * 0.030
        logger.info("🎤 Heard [{:.1f}s]: '{}'", duration, text)

        if self.on_utterance:
            try:
                self.on_utterance(text)
            except Exception as e:
                logger.error("Utterance callback error: {}", e)
