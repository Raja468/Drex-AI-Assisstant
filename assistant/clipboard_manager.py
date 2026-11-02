# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/clipboard_manager.py  —  Clipboard Manager
#
#  Provides clipboard monitoring and management for DREX.
#
#  Features:
#  - Clipboard content monitoring
#  - Smart content detection (text, code, URLs, files)
#  - Clipboard history
#  - Copy/paste integration with assistant
#  - "Ask DREX about clipboard" feature
#
#  Uses pyperclip for cross-platform clipboard access.
#  Falls back gracefully if not available.
# ============================================================

import threading
import time
import re
from typing import Callable, Optional
from collections import deque
from loguru import logger

from assistant.state_engine import StateEngine

# Try to import pyperclip (optional dependency)
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False
    logger.warning("pyperclip not available - clipboard features disabled")


class ClipboardManager:
    """
    Clipboard manager for DREX.
    
    Provides clipboard monitoring, history, and smart content detection.
    
    Usage:
        manager = ClipboardManager(state_engine)
        manager.set_callbacks(on_content_change=handle_clipboard)
        manager.start_monitoring()
    """
    
    # Content type patterns
    URL_PATTERN = re.compile(r'https?://[^\s]+')
    EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    CODE_PATTERNS = {
        "python": re.compile(r'(def |class |import |from .+ import )'),
        "javascript": re.compile(r'(function |const |let |var |=>)'),
        "json": re.compile(r'^\s*[\{\[].*[\}\]]\s*$', re.DOTALL),
    }
    
    def __init__(self, state_engine: StateEngine):
        self.state_engine = state_engine
        self._lock = threading.RLock()
        
        # Clipboard state
        self._last_content = ""
        self._history: deque = deque(maxlen=50)
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Callbacks
        self._on_content_change: Optional[Callable[[str, str], None]] = None
        self._on_url_detected: Optional[Callable[[str], None]] = None
        self._on_code_detected: Optional[Callable[[str, str], None]] = None
        
        # Configuration
        self._enabled = True
        self._monitor_interval = 0.5  # seconds
        self._max_history = 50
        self._auto_detect_content = True
        
        logger.debug("ClipboardManager initialized | available={}", PYPERCLIP_AVAILABLE)
    
    # ── Callback Registration ─────────────────────────────────
    
    def set_callbacks(
        self,
        on_content_change: Optional[Callable[[str, str], None]] = None,
        on_url_detected: Optional[Callable[[str], None]] = None,
        on_code_detected: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Set clipboard callbacks.
        
        on_content_change: Called with (content, content_type) when clipboard changes
        on_url_detected: Called when a URL is detected in clipboard
        on_code_detected: Called with (code, language) when code is detected
        """
        with self._lock:
            if on_content_change:
                self._on_content_change = on_content_change
            if on_url_detected:
                self._on_url_detected = on_url_detected
            if on_code_detected:
                self._on_code_detected = on_code_detected
    
    # ── Clipboard Operations ──────────────────────────────────
    
    def get_content(self) -> str:
        """Get current clipboard content."""
        if not PYPERCLIP_AVAILABLE:
            return ""
        
        try:
            return pyperclip.paste()
        except Exception as e:
            logger.error("Failed to get clipboard: {}", e)
            return ""
    
    def set_content(self, text: str):
        """Set clipboard content."""
        if not PYPERCLIP_AVAILABLE:
            logger.warning("Cannot set clipboard - pyperclip not available")
            return
        
        try:
            pyperclip.copy(text)
            self._last_content = text
            self._add_to_history(text)
            logger.debug("Clipboard set ({} chars)", len(text))
        except Exception as e:
            logger.error("Failed to set clipboard: {}", e)
    
    def clear(self):
        """Clear clipboard content."""
        self.set_content("")
    
    # ── Content Detection ─────────────────────────────────────
    
    def detect_content_type(self, content: str) -> tuple[str, dict]:
        """
        Detect the type of content in clipboard.
        
        Returns:
            Tuple of (content_type, metadata)
        """
        if not content:
            return "empty", {}
        
        metadata = {}
        
        # Check for URL
        url_match = self.URL_PATTERN.search(content)
        if url_match:
            metadata["url"] = url_match.group(0)
            return "url", metadata
        
        # Check for email
        email_match = self.EMAIL_PATTERN.search(content)
        if email_match:
            metadata["email"] = email_match.group(0)
            return "email", metadata
        
        # Check for code
        for lang, pattern in self.CODE_PATTERNS.items():
            if pattern.search(content):
                metadata["language"] = lang
                return "code", metadata
        
        # Check for file path (Windows/Unix)
        if re.match(r'^[A-Za-z]:\\|^\./|^~/|^\w+/\w+', content):
            return "path", metadata
        
        # Check for JSON
        if content.strip().startswith(("{", "[")):
            try:
                import json
                json.loads(content)
                return "json", metadata
            except:
                pass
        
        # Default to text
        metadata["word_count"] = len(content.split())
        metadata["char_count"] = len(content)
        return "text", metadata
    
    # ── Monitoring ────────────────────────────────────────────
    
    def start_monitoring(self):
        """Start monitoring clipboard for changes."""
        if not PYPERCLIP_AVAILABLE:
            logger.warning("Cannot monitor clipboard - pyperclip not available")
            return
        
        if self._monitoring:
            logger.debug("Already monitoring")
            return
        
        logger.info("Starting clipboard monitoring")
        
        self._monitoring = True
        self._stop_event.clear()
        self._last_content = self.get_content()
        
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ClipboardMonitor",
        )
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring clipboard."""
        if not self._monitoring:
            return
        
        logger.info("Stopping clipboard monitoring")
        
        self._stop_event.set()
        self._monitoring = False
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        logger.debug("Clipboard monitor started")
        
        while not self._stop_event.is_set():
            try:
                current = self.get_content()
                
                if current != self._last_content:
                    self._handle_content_change(current)
                    self._last_content = current
                
            except Exception as e:
                logger.error("Monitor loop error: {}", e)
            
            self._stop_event.wait(self._monitor_interval)
        
        logger.debug("Clipboard monitor stopped")
    
    def _handle_content_change(self, content: str):
        """Handle clipboard content change."""
        if not self._enabled:
            return
        
        logger.debug("Clipboard changed ({} chars)", len(content))
        
        # Add to history
        self._add_to_history(content)
        
        # Detect content type
        content_type, metadata = self.detect_content_type(content)
        
        # Notify content change callback
        if self._on_content_change:
            try:
                self._on_content_change(content, content_type)
            except Exception as e:
                logger.error("Content change callback error: {}", e)
        
        # Notify specific callbacks
        if content_type == "url" and self._on_url_detected:
            try:
                self._on_url_detected(metadata.get("url", ""))
            except Exception as e:
                logger.error("URL callback error: {}", e)
        
        if content_type == "code" and self._on_code_detected:
            try:
                self._on_code_detected(content, metadata.get("language", "unknown"))
            except Exception as e:
                logger.error("Code callback error: {}", e)
    
    # ── History ───────────────────────────────────────────────
    
    def _add_to_history(self, content: str):
        """Add content to clipboard history."""
        with self._lock:
            # Don't add duplicates at the end
            if self._history and self._history[-1] == content:
                return
            
            self._history.append(content)
    
    def get_history(self, limit: int = 10) -> list[str]:
        """Get recent clipboard history."""
        with self._lock:
            return list(self._history)[-limit:]
    
    def clear_history(self):
        """Clear clipboard history."""
        with self._lock:
            self._history.clear()
    
    # ── Configuration ─────────────────────────────────────────
    
    def enable(self):
        """Enable clipboard manager."""
        with self._lock:
            self._enabled = True
            logger.info("Clipboard manager enabled")
    
    def disable(self):
        """Disable clipboard manager."""
        with self._lock:
            self._enabled = False
            logger.info("Clipboard manager disabled")
    
    def is_enabled(self) -> bool:
        """Check if clipboard manager is enabled."""
        return self._enabled
    
    def set_monitor_interval(self, seconds: float):
        """Set clipboard check interval."""
        self._monitor_interval = max(0.1, min(5.0, seconds))
        logger.debug("Monitor interval: {}s", self._monitor_interval)
    
    # ── Utilities ─────────────────────────────────────────────
    
    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        return self._monitoring
    
    def get_stats(self) -> dict:
        """Get clipboard manager statistics."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "monitoring": self._monitoring,
                "history_size": len(self._history),
                "last_content_length": len(self._last_content),
                "available": PYPERCLIP_AVAILABLE,
            }
    
    def destroy(self):
        """Clean up and destroy the clipboard manager."""
        self.stop_monitoring()
        logger.debug("ClipboardManager destroyed")
    
    def __repr__(self) -> str:
        return f"ClipboardManager(monitoring={self._monitoring}, history={len(self._history)})"


def is_clipboard_available() -> bool:
    """Check if clipboard support is available."""
    return PYPERCLIP_AVAILABLE