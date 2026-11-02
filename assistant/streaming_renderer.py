"""
DREX - AI Assistant Runtime
assistant/streaming_renderer.py - Smooth Token Rendering

Provides smooth, flicker-free rendering of streaming AI responses.
"""

import threading
import time
from typing import Optional, Callable, List
from dataclasses import dataclass, field
from queue import Queue, Empty
from loguru import logger


@dataclass
class RenderState:
    """State of the streaming renderer."""
    is_streaming: bool = False
    current_text: str = ""
    token_count: int = 0
    start_time: float = 0.0
    last_update: float = 0.0


class StreamingRenderer:
    """
    Smooth streaming text renderer for AI responses.
    
    Features:
    - Token buffering for smooth rendering
    - Rate limiting to prevent UI flicker
    - Thread-safe updates
    - Cancellation support
    - Progress tracking
    """
    
    def __init__(
        self,
        update_callback: Optional[Callable[[str], None]] = None,
        complete_callback: Optional[Callable[[str], None]] = None,
        min_update_interval: float = 0.016,  # ~60 FPS
        buffer_size: int = 5,
    ):
        """
        Initialize the streaming renderer.
        
        Args:
            update_callback: Called with partial text during streaming
            complete_callback: Called with full text when streaming completes
            min_update_interval: Minimum time between UI updates (seconds)
            buffer_size: Number of tokens to buffer before updating
        """
        self._update_callback = update_callback
        self._complete_callback = complete_callback
        self._min_update_interval = min_update_interval
        self._buffer_size = buffer_size
        
        self._state = RenderState()
        self._token_queue: Queue = Queue()
        self._lock = threading.Lock()
        self._cancelled = False
        self._render_thread: Optional[threading.Thread] = None
        
        logger.debug("StreamingRenderer initialized")
    
    @property
    def is_streaming(self) -> bool:
        """Check if currently streaming."""
        return self._state.is_streaming
    
    @property
    def current_text(self) -> str:
        """Get the current rendered text."""
        with self._lock:
            return self._state.current_text
    
    @property
    def token_count(self) -> int:
        """Get the number of tokens received."""
        return self._state.token_count
    
    def start_stream(self):
        """Start a new streaming session."""
        with self._lock:
            self._state = RenderState(
                is_streaming=True,
                current_text="",
                token_count=0,
                start_time=time.time(),
                last_update=0.0,
            )
            self._cancelled = False
        
        # Clear the queue
        while not self._token_queue.empty():
            try:
                self._token_queue.get_nowait()
            except Empty:
                break
        
        # Start render thread
        self._render_thread = threading.Thread(
            target=self._render_loop,
            daemon=True,
            name="StreamingRenderer"
        )
        self._render_thread.start()
        
        logger.debug("Stream started")
    
    def add_token(self, token: str):
        """
        Add a token to the stream.
        
        Args:
            token: Text token to add
        """
        if not self._state.is_streaming:
            return
        
        self._token_queue.put(token)
    
    def end_stream(self):
        """End the streaming session."""
        with self._lock:
            self._state.is_streaming = False
        
        # Signal render thread to stop
        self._token_queue.put(None)
        
        # Wait for render thread
        if self._render_thread and self._render_thread.is_alive():
            self._render_thread.join(timeout=2.0)
        
        # Call complete callback
        if self._complete_callback and not self._cancelled:
            try:
                self._complete_callback(self._state.current_text)
            except Exception as e:
                logger.error(f"Complete callback error: {e}")
        
        elapsed = time.time() - self._state.start_time if self._state.start_time else 0
        logger.debug(f"Stream ended | tokens={self._state.token_count} | elapsed={elapsed:.2f}s")
    
    def cancel(self):
        """Cancel the current stream."""
        self._cancelled = True
        self.end_stream()
        logger.debug("Stream cancelled")
    
    def set_update_callback(self, callback: Callable[[str], None]):
        """Set the update callback."""
        self._update_callback = callback
    
    def set_complete_callback(self, callback: Callable[[str], None]):
        """Set the complete callback."""
        self._complete_callback = callback
    
    def _render_loop(self):
        """Main render loop running in background thread."""
        buffer: List[str] = []
        
        while self._state.is_streaming or not self._token_queue.empty():
            try:
                # Get token with timeout
                token = self._token_queue.get(timeout=0.1)
                
                # None signals end of stream
                if token is None:
                    break
                
                buffer.append(token)
                
                with self._lock:
                    self._state.token_count += 1
                
                # Check if we should update
                should_update = (
                    len(buffer) >= self._buffer_size or
                    time.time() - self._state.last_update >= self._min_update_interval
                )
                
                if should_update and not self._cancelled:
                    # Flush buffer
                    text_to_add = "".join(buffer)
                    buffer.clear()
                    
                    with self._lock:
                        self._state.current_text += text_to_add
                        self._state.last_update = time.time()
                        current = self._state.current_text
                    
                    # Call update callback
                    if self._update_callback:
                        try:
                            self._update_callback(current)
                        except Exception as e:
                            logger.error(f"Update callback error: {e}")
            
            except Empty:
                # Flush any remaining buffer
                if buffer and not self._cancelled:
                    text_to_add = "".join(buffer)
                    buffer.clear()
                    
                    with self._lock:
                        self._state.current_text += text_to_add
                        self._state.last_update = time.time()
                        current = self._state.current_text
                    
                    if self._update_callback:
                        try:
                            self._update_callback(current)
                        except Exception as e:
                            logger.error(f"Update callback error: {e}")
            
            except Exception as e:
                logger.error(f"Render loop error: {e}")
                break
        
        # Final flush
        if buffer and not self._cancelled:
            text_to_add = "".join(buffer)
            with self._lock:
                self._state.current_text += text_to_add
                current = self._state.current_text
            
            if self._update_callback:
                try:
                    self._update_callback(current)
                except Exception as e:
                    logger.error(f"Final update callback error: {e}")


class StreamingTextBuffer:
    """
    Simple text buffer for accumulating streaming text.
    Useful when you don't need the full renderer.
    """
    
    def __init__(self):
        """Initialize the text buffer."""
        self._text = ""
        self._lock = threading.Lock()
    
    def append(self, text: str):
        """Append text to the buffer."""
        with self._lock:
            self._text += text
    
    def get(self) -> str:
        """Get the current buffer contents."""
        with self._lock:
            return self._text
    
    def clear(self):
        """Clear the buffer."""
        with self._lock:
            self._text = ""
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._text)
    
    def __str__(self) -> str:
        return self.get()