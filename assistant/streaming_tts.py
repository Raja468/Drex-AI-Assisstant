# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/streaming_tts.py  —  Streaming TTS Engine
#
#  Enables TTS playback while AI is still generating text.
#
#  Traditional flow:
#  1. Generate full response (slow)
#  2. Convert to audio
#  3. Play audio
#
#  Streaming flow:
#  1. Start generating response
#  2. Buffer tokens until sentence boundary
#  3. Convert sentence to audio
#  4. Play audio while continuing generation
#  5. Repeat until complete
#
#  Benefits:
#  - Much lower time-to-first-audio
#  - More natural conversation flow
#  - Feels like real-time speech
# ============================================================

import threading
import queue
import time
import re
from typing import Callable, Optional, Generator
from loguru import logger

from assistant.state_engine import StateEngine, AssistantState


class StreamingTTS:
    """
    Streaming TTS engine for low-latency voice output.
    
    Buffers tokens until sentence boundaries, then converts
    and plays audio while generation continues.
    
    Usage:
        tts = StreamingTTS(state_engine, speaker)
        tts.start_stream()
        
        for token in ai_stream:
            tts.feed_token(token)
        
        tts.end_stream()
    """
    
    # Sentence boundary patterns
    SENTENCE_BOUNDARIES = re.compile(r'[.!?]+\s+|[\n]+')
    
    # Minimum buffer size before forcing flush
    MIN_BUFFER_SIZE = 20
    
    # Maximum buffer size before forcing flush
    MAX_BUFFER_SIZE = 200
    
    def __init__(
        self,
        state_engine: StateEngine,
        speaker=None,
    ):
        self.state_engine = state_engine
        self._speaker = speaker
        self._lock = threading.RLock()
        
        # Stream state
        self._is_streaming = False
        self._buffer = ""
        self._audio_queue: queue.Queue = queue.Queue()
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Configuration
        self._enabled = True
        self._sentence_buffering = True
        self._min_buffer_size = self.MIN_BUFFER_SIZE
        self._max_buffer_size = self.MAX_BUFFER_SIZE
        
        # Statistics
        self._tokens_received = 0
        self._sentences_spoken = 0
        self._first_audio_time: Optional[float] = None
        self._stream_start_time: Optional[float] = None
        
        logger.debug("StreamingTTS initialized | buffering={}", self._sentence_buffering)
    
    # ── Speaker Integration ───────────────────────────────────
    
    def set_speaker(self, speaker):
        """Set the TTS speaker component."""
        with self._lock:
            self._speaker = speaker
            logger.debug("Speaker set for streaming TTS")
    
    # ── Stream Control ────────────────────────────────────────
    
    def start_stream(self):
        """
        Start a new TTS stream.
        
        Call this before feeding tokens.
        """
        with self._lock:
            if self._is_streaming:
                logger.warning("Stream already active")
                return
            
            logger.debug("Starting TTS stream")
            
            # Reset state
            self._is_streaming = True
            self._buffer = ""
            self._tokens_received = 0
            self._stop_event.clear()
            self._stream_start_time = time.time()
            self._first_audio_time = None
            
            # Clear audio queue
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Start playback thread
            self._playback_thread = threading.Thread(
                target=self._playback_loop,
                daemon=True,
                name="StreamingTTS-Playback",
            )
            self._playback_thread.start()
            
            # Update state
            self.state_engine.state = AssistantState.SPEAKING
    
    def feed_token(self, token: str):
        """
        Feed a token to the TTS stream.
        
        Tokens are buffered until sentence boundaries.
        """
        with self._lock:
            if not self._is_streaming:
                logger.warning("No active stream")
                return
            
            self._buffer += token
            self._tokens_received += 1
            
            # Check for sentence boundary
            if self._sentence_buffering:
                self._check_sentence_boundary()
            else:
                # No buffering, flush on every token (not recommended)
                self._flush_buffer()
    
    def feed_text(self, text: str):
        """
        Feed a complete text chunk to the TTS stream.
        
        Useful for non-streaming responses.
        """
        with self._lock:
            if not self._is_streaming:
                self.start_stream()
            
            self._buffer += text
            self._check_sentence_boundary()
    
    def end_stream(self):
        """
        End the TTS stream.
        
        Flushes remaining buffer and waits for playback to complete.
        """
        with self._lock:
            if not self._is_streaming:
                return
            
            logger.debug("Ending TTS stream")
            
            # Flush remaining buffer
            if self._buffer.strip():
                self._flush_buffer()
            
            # Signal playback thread to stop
            self._audio_queue.put(None)  # Sentinel
            
            self._is_streaming = False
        
        # Wait for playback to complete
        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=10.0)
        
        # Update state
        if self.state_engine.state == AssistantState.SPEAKING:
            self.state_engine.state = AssistantState.IDLE
    
    def cancel_stream(self):
        """
        Cancel the TTS stream immediately.
        
        Stops playback without waiting for completion.
        """
        with self._lock:
            if not self._is_streaming:
                return
            
            logger.debug("Cancelling TTS stream")
            
            # Signal stop
            self._stop_event.set()
            self._is_streaming = False
            self._buffer = ""
            
            # Clear queue
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Stop speaker
            if self._speaker:
                try:
                    self._speaker.stop()
                except Exception as e:
                    logger.error("Failed to stop speaker: {}", e)
        
        # Update state
        if self.state_engine.state == AssistantState.SPEAKING:
            self.state_engine.state = AssistantState.IDLE
    
    # ── Buffer Management ─────────────────────────────────────
    
    def _check_sentence_boundary(self):
        """Check for sentence boundary and flush if found."""
        # Find sentence boundary
        match = self.SENTENCE_BOUNDARIES.search(self._buffer)
        
        if match:
            # Extract sentence
            end_pos = match.end()
            sentence = self._buffer[:end_pos].strip()
            self._buffer = self._buffer[end_pos:]
            
            if sentence:
                self._queue_sentence(sentence)
        
        # Force flush if buffer too large
        elif len(self._buffer) >= self._max_buffer_size:
            sentence = self._buffer.strip()
            self._buffer = ""
            if sentence:
                self._queue_sentence(sentence)
    
    def _flush_buffer(self):
        """Flush the current buffer to audio queue."""
        sentence = self._buffer.strip()
        self._buffer = ""
        
        if sentence:
            self._queue_sentence(sentence)
    
    def _queue_sentence(self, sentence: str):
        """Queue a sentence for TTS conversion and playback."""
        logger.debug("Queuing sentence ({} chars): {}...", 
                    len(sentence), sentence[:50])
        
        # Convert to audio (synchronous for now)
        # In production, this could be async with a TTS service
        self._audio_queue.put(sentence)
    
    # ── Playback Loop ─────────────────────────────────────────
    
    def _playback_loop(self):
        """Background thread for audio playback."""
        logger.debug("Playback loop started")
        
        while not self._stop_event.is_set():
            try:
                # Get next sentence (with timeout)
                sentence = self._audio_queue.get(timeout=0.5)
                
                # Check for sentinel
                if sentence is None:
                    break
                
                # Record first audio time
                if self._first_audio_time is None:
                    self._first_audio_time = time.time()
                    latency = self._first_audio_time - self._stream_start_time
                    logger.info("Time to first audio: {:.2f}s", latency)
                
                # Speak the sentence
                self._speak_sentence(sentence)
                self._sentences_spoken += 1
                
            except queue.Empty:
                # No audio ready yet, continue waiting
                continue
            except Exception as e:
                logger.error("Playback loop error: {}", e)
        
        logger.debug("Playback loop ended | sentences={}", self._sentences_spoken)
    
    def _speak_sentence(self, sentence: str):
        """Speak a single sentence."""
        if not self._speaker:
            logger.warning("No speaker available")
            return
        
        if self._stop_event.is_set():
            return
        
        try:
            # Use speaker's speak method
            if hasattr(self._speaker, 'speak'):
                self._speaker.speak(sentence)
            elif hasattr(self._speaker, 'speak_text'):
                self._speaker.speak_text(sentence)
            else:
                logger.warning("Speaker has no speak method")
        except Exception as e:
            logger.error("Failed to speak sentence: {}", e)
    
    # ── Configuration ─────────────────────────────────────────
    
    def enable(self):
        """Enable streaming TTS."""
        with self._lock:
            self._enabled = True
            logger.info("Streaming TTS enabled")
    
    def disable(self):
        """Disable streaming TTS."""
        with self._lock:
            self._enabled = False
            logger.info("Streaming TTS disabled")
    
    def is_enabled(self) -> bool:
        """Check if streaming TTS is enabled."""
        return self._enabled
    
    def set_sentence_buffering(self, enabled: bool):
        """Enable/disable sentence buffering."""
        with self._lock:
            self._sentence_buffering = enabled
            logger.debug("Sentence buffering: {}", enabled)
    
    def set_buffer_sizes(self, min_size: int, max_size: int):
        """Set min/max buffer sizes."""
        with self._lock:
            self._min_buffer_size = max(10, min_size)
            self._max_buffer_size = max(50, max_size)
            logger.debug("Buffer sizes: min={}, max={}", 
                        self._min_buffer_size, self._max_buffer_size)
    
    # ── Statistics ────────────────────────────────────────────
    
    def get_stats(self) -> dict:
        """Get streaming TTS statistics."""
        with self._lock:
            latency = None
            if self._first_audio_time and self._stream_start_time:
                latency = self._first_audio_time - self._stream_start_time
            
            return {
                "enabled": self._enabled,
                "is_streaming": self._is_streaming,
                "sentence_buffering": self._sentence_buffering,
                "tokens_received": self._tokens_received,
                "sentences_spoken": self._sentences_spoken,
                "buffer_size": len(self._buffer),
                "queue_size": self._audio_queue.qsize(),
                "time_to_first_audio": latency,
            }
    
    def reset_stats(self):
        """Reset statistics."""
        with self._lock:
            self._tokens_received = 0
            self._sentences_spoken = 0
            self._first_audio_time = None
            self._stream_start_time = None
    
    # ── Utilities ─────────────────────────────────────────────
    
    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        return self._is_streaming
    
    def get_buffer(self) -> str:
        """Get current buffer contents."""
        with self._lock:
            return self._buffer
    
    def destroy(self):
        """Clean up and destroy the streaming TTS engine."""
        self.cancel_stream()
        logger.debug("StreamingTTS destroyed")
    
    def __repr__(self) -> str:
        return (
            f"StreamingTTS(enabled={self._enabled}, "
            f"streaming={self._is_streaming}, "
            f"sentences={self._sentences_spoken})"
        )