"""
DREX - AI Assistant Runtime
assistant/app_awareness.py - Active Window Detection

Provides context-aware responses based on the currently active window.
"""

import threading
from typing import Optional, Dict, Any
from loguru import logger

# Try to import pygetwindow
try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False
    logger.warning("pygetwindow not available - app awareness disabled")


class AppAwareness:
    """
    Tracks the currently active window and provides context to the assistant.
    
    Features:
    - Active window title detection
    - Application name extraction
    - Window state tracking
    - Context-aware suggestions
    """
    
    # Known application mappings
    APP_MAPPINGS = {
        "chrome": "Google Chrome",
        "firefox": "Mozilla Firefox",
        "edge": "Microsoft Edge",
        "code": "Visual Studio Code",
        "vscode": "Visual Studio Code",
        "notepad": "Notepad",
        "word": "Microsoft Word",
        "excel": "Microsoft Excel",
        "powerpoint": "Microsoft PowerPoint",
        "explorer": "File Explorer",
        "cmd": "Command Prompt",
        "powershell": "PowerShell",
        "terminal": "Terminal",
        "spotify": "Spotify",
        "discord": "Discord",
        "slack": "Slack",
        "teams": "Microsoft Teams",
        "zoom": "Zoom",
    }
    
    def __init__(self):
        """Initialize the app awareness system."""
        self._enabled = PYGETWINDOW_AVAILABLE
        self._current_app: Optional[str] = None
        self._current_title: Optional[str] = None
        self._lock = threading.Lock()
        
        logger.debug(f"AppAwareness initialized | enabled={self._enabled}")
    
    @property
    def enabled(self) -> bool:
        """Check if app awareness is enabled."""
        return self._enabled
    
    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the currently active window.
        
        Returns:
            Dictionary with window info or None if unavailable
        """
        if not self._enabled:
            return None
        
        try:
            window = gw.getActiveWindow()
            if window:
                title = window.title
                app_name = self._extract_app_name(title)
                
                with self._lock:
                    self._current_app = app_name
                    self._current_title = title
                
                return {
                    "title": title,
                    "app": app_name,
                    "app_display": self.APP_MAPPINGS.get(app_name.lower(), app_name),
                    "width": window.width,
                    "height": window.height,
                    "left": window.left,
                    "top": window.top,
                }
        except Exception as e:
            logger.debug(f"Failed to get active window: {e}")
        
        return None
    
    def get_current_app(self) -> Optional[str]:
        """Get the name of the currently active application."""
        if not self._enabled:
            return None
        
        # Refresh if needed
        if self._current_app is None:
            self.get_active_window()
        
        return self._current_app
    
    def get_current_title(self) -> Optional[str]:
        """Get the title of the currently active window."""
        if not self._enabled:
            return None
        
        # Refresh if needed
        if self._current_title is None:
            self.get_active_window()
        
        return self._current_title
    
    def get_context_prompt(self) -> str:
        """
        Generate a context prompt based on the active application.
        
        Returns:
            Context string to include in AI prompts
        """
        if not self._enabled:
            return ""
        
        window_info = self.get_active_window()
        if not window_info:
            return ""
        
        app = window_info.get("app_display", "Unknown")
        title = window_info.get("title", "")
        
        # Build context based on app type
        context_parts = [f"The user is currently using {app}."]
        
        # Add specific context based on app
        app_lower = app.lower()
        
        if "chrome" in app_lower or "firefox" in app_lower or "edge" in app_lower:
            if title and " - " in title:
                page_title = title.split(" - ")[0]
                context_parts.append(f"They are viewing: {page_title}")
        
        elif "code" in app_lower or "vscode" in app_lower:
            if title:
                context_parts.append(f"They have open: {title}")
        
        elif "word" in app_lower:
            if title:
                context_parts.append(f"They are editing: {title}")
        
        elif "explorer" in app_lower:
            if title:
                context_parts.append(f"They are browsing: {title}")
        
        return " ".join(context_parts)
    
    def _extract_app_name(self, title: str) -> str:
        """
        Extract the application name from a window title.
        
        Args:
            title: Window title string
            
        Returns:
            Extracted application name
        """
        if not title:
            return "Unknown"
        
        # Try to extract app name from title
        # Common patterns: "Document - App Name" or "App Name - Document"
        
        # Check for common separators
        for separator in [" - ", " — ", " | "]:
            if separator in title:
                parts = title.split(separator)
                # Usually the app name is the last part
                potential_app = parts[-1].strip()
                if potential_app:
                    return potential_app
        
        # Return the full title if no separator found
        return title[:50] if len(title) > 50 else title
    
    def is_browser_active(self) -> bool:
        """Check if a web browser is the active application."""
        app = self.get_current_app()
        if not app:
            return False
        
        app_lower = app.lower()
        return any(browser in app_lower for browser in ["chrome", "firefox", "edge", "safari", "opera"])
    
    def is_code_editor_active(self) -> bool:
        """Check if a code editor is the active application."""
        app = self.get_current_app()
        if not app:
            return False
        
        app_lower = app.lower()
        return any(editor in app_lower for editor in ["code", "vscode", "sublime", "atom", "notepad++", "pycharm", "intellij"])
    
    def is_terminal_active(self) -> bool:
        """Check if a terminal is the active application."""
        app = self.get_current_app()
        if not app:
            return False
        
        app_lower = app.lower()
        return any(term in app_lower for term in ["cmd", "powershell", "terminal", "console", "bash", "zsh"])


# Singleton instance
_app_awareness: Optional[AppAwareness] = None


def get_app_awareness() -> AppAwareness:
    """Get the singleton AppAwareness instance."""
    global _app_awareness
    if _app_awareness is None:
        _app_awareness = AppAwareness()
    return _app_awareness


def is_app_awareness_available() -> bool:
    """Check if app awareness is available."""
    return PYGETWINDOW_AVAILABLE
