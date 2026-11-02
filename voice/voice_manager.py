"""
DEPRECATED -- Sprint-4 Modern Voice Stack

This module is NOT currently wired into the main application flow.
The application uses the legacy VoiceEngine (voice/voice_engine.py).
This code is preserved for future integration. Do not delete.

---

voice/voice_manager.py - Single owner for all voice logic.

Responsibilities:

- Own the microphone, VAD, STT, TTS, and interruption modules.
- Expose a small state machine: IDLE / LISTENING / PROCESSING / SPEAKING.
- Provide two independent operating modes:
    * dictate()  ->  transcribe one utterance and return the text
    * conversation()  ->  continuous listen -> think -> speak -> listen loop

All heavy work runs on background threads. Public methods return
immediately; callers subscribe to state changes via ``on_state_change``.
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Callable, List, Optional

from loguru import logger

from voice.audio_stream import AudioStream, FRAME_SIZE, SAMPLE_RATE
from voice.interruption_manager import InterruptionManager
from voice.speech_to_text import SpeechToText
from voice.tts_engine import TTSEngine
from voice.vad import VAD


# ------------------------------------------------------------------
#  State
# ------------------------------------------------------------------

class VoiceState(Enum):
    IDLE       = "idle"
    LISTENING  = "listening"
    PROCESSING = "processing"
    SPEAKING   = "speaking"
    ERROR      = "error"


# ------------------------------------------------------------------
#  Utterance recorder - listens until a silence period after speech
# ------------------------------------------------------------------

class _UtteranceRecorder:
    """
    Captures a single utterance using VAD-driven boundaries.

    Rules:
      - Wait up to ``start_timeout`` seconds for speech to begin.
      - Record until we see ``silence_ms`` of consecutive non-speech.
      - Give up after ``max_utterance_ms`` regardless.
    """

    def __init__(
        self,
        stream: AudioStream,
        vad: VAD,
        start_timeout: float = 6.0,
        silence_ms: int = 800,
        max_utterance_ms: int = 15000,
        pre_roll_ms: int = 240,
    ):
        self.stream = stream
        self.vad = vad
        self.start_timeout = start_timeout
        self.silence_ms = silence_ms
        self.max_utterance_ms = max_utterance_ms
        self.pre_roll_ms = pre_roll_ms

    def record(self, stop_event: threading.Event) -> Optional[bytes]:
        frame_ms = int(1000 * FRAME_SIZE / SAMPLE_RATE)
        silence_frames_needed = max(1, self.silence_ms // frame_ms)
        max_frames = max(1, self.max_utterance_ms // frame_ms)
        pre_roll_frames = max(1, self.pre_roll_ms // frame_ms)

        started = False
        collected: List[bytes] = []
        pre_roll: List[bytes] = []
        silence_run = 0
        start_time = time.time()

        self.vad.reset()

        while not stop_event.is_set():
            frame = self.stream.read_frame(timeout=0.3)
            if frame is None:
                if not started and (time.time() - start_time) > self.start_timeout:
                    return None
                continue

            is_speech = self.vad.is_speech(frame)

            if not started:
                pre_roll.append(frame)
                if len(pre_roll) > pre_roll_frames:
                    pre_roll.pop(0)
                if is_speech:
                    started = True
                    collected.extend(pre_roll)
                    collected.append(frame)
                    silence_run = 0
                elif (time.time() - start_time) > self.start_timeout:
                    return None
                continue

            collected.append(frame)
            if is_speech:
                silence_run = 0
            else:
                silence_run += 1
                if silence_run >= silence_frames_needed:
                    break

            if len(collected) >= max_frames:
                break

        if not collected:
            return None
        return b"".join(collected)


# ------------------------------------------------------------------
#  Voice Manager
# ------------------------------------------------------------------

class VoiceManager:
    """Central voice controller for DREX."""

    def __init__(
        self,
        stt: Optional[SpeechToText] = None,
        tts: Optional[TTSEngine] = None,
        vad: Optional[VAD] = None,
        on_state_change: Optional[Callable[[VoiceState], None]] = None,
        on_partial_transcript: Optional[Callable[[str], None]] = None,
    ):
        self.stt = stt or SpeechToText()
        self.tts = tts or TTSEngine(
            on_start=lambda: self._set_state(VoiceState.SPEAKING),
            on_finish=lambda: self._set_state(VoiceState.IDLE),
        )
        self.vad = vad or VAD()

        self.on_state_change = on_state_change
        self.on_partial_transcript = on_partial_transcript

        self._state = VoiceState.IDLE
        self._lock = threading.RLock()

        self._stream: Optional[AudioStream] = None
        self._interruption: Optional[InterruptionManager] = None

        self._dictation_thread: Optional[threading.Thread] = None
        self._dictation_stop = threading.Event()

        self._conversation_thread: Optional[threading.Thread] = None
        self._conversation_stop = threading.Event()

    # -------------------------------------------------------
    #  State
    # -------------------------------------------------------

    @property
    def state(self) -> VoiceState:
        with self._lock:
            return self._state

    def _set_state(self, new_state: VoiceState) -> None:
        with self._lock:
            if self._state == new_state:
                return
            self._state = new_state
        logger.debug("VoiceManager state -> {}", new_state.value)
        if self.on_state_change is not None:
            try:
                self.on_state_change(new_state)
            except Exception as e:
                logger.error("on_state_change callback error: {}", e)

    # -------------------------------------------------------
    #  Availability
    # -------------------------------------------------------

    @property
    def mic_available(self) -> bool:
        return AudioStream().is_available

    @property
    def stt_available(self) -> bool:
        return self.stt.is_available

    @property
    def tts_available(self) -> bool:
        return self.tts.is_available

    # -------------------------------------------------------
    #  Mode 1: Voice-to-Text (dictate one utterance)
    # -------------------------------------------------------

    def dictate(self, on_result: Callable[[Optional[str]], None]) -> None:
        """
        Record one utterance, transcribe it, and deliver text via
        ``on_result``. Non-blocking - the work happens on a worker thread.
        """
        if not self.mic_available:
            on_result(None)
            return

        def _run():
            self._dictation_stop.clear()
            self._set_state(VoiceState.LISTENING)

            stream = AudioStream()
            if not stream.start():
                self._set_state(VoiceState.ERROR)
                on_result(None)
                return

            try:
                recorder = _UtteranceRecorder(stream, self.vad)
                pcm = recorder.record(self._dictation_stop)
                if pcm is None or self._dictation_stop.is_set():
                    self._set_state(VoiceState.IDLE)
                    on_result(None)
                    return

                self._set_state(VoiceState.PROCESSING)
                text = self.stt.transcribe(pcm)
                logger.info("Dictation: {!r}", text)
                self._set_state(VoiceState.IDLE)
                on_result(text)
            except Exception as e:
                logger.error("Dictation error: {}", e)
                self._set_state(VoiceState.ERROR)
                on_result(None)
            finally:
                stream.stop()

        self._dictation_thread = threading.Thread(
            target=_run, name="VoiceDictation", daemon=True,
        )
        self._dictation_thread.start()

    def cancel_dictation(self) -> None:
        self._dictation_stop.set()
        self._set_state(VoiceState.IDLE)

    # -------------------------------------------------------
    #  Mode 2: Voice Conversation (continuous loop)
    # -------------------------------------------------------

    def start_conversation(
        self,
        on_user_text: Callable[[str], str],
        on_assistant_text: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Start a continuous voice conversation.

        ``on_user_text(text) -> reply`` is called with each transcribed
        user utterance and must return the assistant reply as a string.
        ``on_assistant_text`` is fired once we know what to say (so the
        UI can render the reply before/while it plays).
        """
        with self._lock:
            if self._conversation_thread is not None and self._conversation_thread.is_alive():
                logger.debug("Conversation already running")
                return True
            if not self.mic_available:
                logger.warning("Cannot start conversation: mic unavailable")
                return False

            self._conversation_stop.clear()
            self._conversation_thread = threading.Thread(
                target=self._conversation_loop,
                args=(on_user_text, on_assistant_text),
                name="VoiceConversation",
                daemon=True,
            )
            self._conversation_thread.start()
            logger.info("Voice conversation started")
            return True

    def stop_conversation(self) -> None:
        self._conversation_stop.set()
        self.tts.stop()
        if self._interruption is not None:
            self._interruption.stop()
            self._interruption = None
        self._set_state(VoiceState.IDLE)
        logger.info("Voice conversation stopped")

    @property
    def is_in_conversation(self) -> bool:
        return (
            self._conversation_thread is not None
            and self._conversation_thread.is_alive()
        )

    def _conversation_loop(
        self,
        on_user_text: Callable[[str], str],
        on_assistant_text: Optional[Callable[[str], None]],
    ) -> None:
        interrupted = threading.Event()

        def _on_interrupt():
            interrupted.set()
            self.tts.stop()

        self._interruption = InterruptionManager(on_interrupt=_on_interrupt)

        stream = AudioStream()
        if not stream.start():
            self._set_state(VoiceState.ERROR)
            return

        try:
            while not self._conversation_stop.is_set():
                self._set_state(VoiceState.LISTENING)
                recorder = _UtteranceRecorder(stream, self.vad, start_timeout=30.0)
                pcm = recorder.record(self._conversation_stop)
                if self._conversation_stop.is_set():
                    break
                if pcm is None:
                    continue

                self._set_state(VoiceState.PROCESSING)
                text = self.stt.transcribe(pcm)
                if not text:
                    continue
                if self.on_partial_transcript is not None:
                    try:
                        self.on_partial_transcript(text)
                    except Exception:
                        pass

                reply: Optional[str] = None
                try:
                    reply = on_user_text(text)
                except Exception as e:
                    logger.error("on_user_text callback error: {}", e)

                if self._conversation_stop.is_set():
                    break
                if not reply:
                    continue

                if on_assistant_text is not None:
                    try:
                        on_assistant_text(reply)
                    except Exception:
                        pass

                interrupted.clear()
                self._interruption.set_on_interrupt(_on_interrupt)
                self._interruption.start()
                self._set_state(VoiceState.SPEAKING)
                self.tts.speak(reply)
                # Wait until playback finishes or is interrupted
                while self.tts.is_speaking and not self._conversation_stop.is_set():
                    if interrupted.is_set():
                        break
                    time.sleep(0.05)
                self._interruption.stop()

            self._set_state(VoiceState.IDLE)
        except Exception as e:
            logger.error("Conversation loop error: {}", e)
            self._set_state(VoiceState.ERROR)
        finally:
            stream.stop()
            if self._interruption is not None:
                self._interruption.stop()
                self._interruption = None

    # -------------------------------------------------------
    #  Direct speak (used outside of conversation mode)
    # -------------------------------------------------------

    def speak(self, text: str, priority: bool = False) -> None:
        if not text or not text.strip():
            return
        self.tts.speak(text, priority=priority)

    def stop_speaking(self) -> None:
        self.tts.stop()

    # -------------------------------------------------------
    #  Lifecycle
    # -------------------------------------------------------

    def shutdown(self) -> None:
        self.stop_conversation()
        self.cancel_dictation()
        try:
            self.tts.shutdown()
        except Exception:
            pass
        try:
            self.stt.shutdown()
        except Exception:
            pass
