# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/global_hotkey.py  —  Global Hotkey Manager
#
#  Provides system-wide hotkey support for DREX.
#
#  Features:
#  - Global hotkey registration (works when app is minimized)
#  - Configurable hotkey bindings
#  - Default hotkeys:
#    - Ctrl+Space: Toggle listening
#    - Ctrl+Shift+Space: Push-to-talk
#    - Ctrl+Shift+D: Show/hide DREX
#    - Ctrl+Shift+M: Mute/unmute
#    - Ctrl+Shift+Q: Quick query
#
#  Uses keyboard library for cross-platform hotkey support.
#  Falls back gracefully if keyboard is not available.
# ============================================================

import threading
from typing import Callable, Optional
from loguru import logger

from assistant.state_engine import StateEngine, AssistantState

# Try to import keyboard (optional dependency)
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    logger.warning("keyboard not available - global hotkeys disabled")


class GlobalHotkey:
    """
    Global hotkey manager for DREX.
    
    Provides system-wide hotkey support that works even when
    DREX is minimized or in the background.
    
    Usage:
        hotkey = GlobalHotkey(state_engine)
        hotkey.set_callbacks(on_toggle_listen=toggle_listening)
        hotkey.start()
    """
    
    # Default hotkey bindings
    DEFAULT_HOTKEYS = {
        "toggle_listen": "ctrl+space",
        "push_to_talk": "ctrl+shift+space",
        "show_hide": "ctrl+shift+d",
        "mute": "ctrl+shift+m",
        "quick_query": "ctrl+shift+q",
        "agent_mode": "ctrl+shift+a",
        "chat_mode": "ctrl+shift+c",
    }
    
    def __init__(self, state_engine: StateEngine):
        self.state_engine = state_engine
        self._lock = threading.RLock()
        
        # Callbacks
        self._callbacks: dict[str, Callable] = {}
        
        # Hotkey configuration
        self._hotkeys = self.DEFAULT_HOTKEYS.copy()
        self._registered_hotkeys: list[str] = []
        
        # State
        self._running = False
        self._push_to_talk_active = False
        
        logger.debug("GlobalHotkey initialized | available={}", KEYBOARD_AVAILABLE)
    
    # ── Callback Registration ─────────────────────────────────
    
    def set_callbacks(
        self,
        on_toggle_listen: Optional[Callable] = None,
        on_push_to_talk_start: Optional[Callable] = None,
        on_push_to_talk_end: Optional[Callable] = None,
        on_show_hide: Optional[Callable] = None,
        on_mute: Optional[Callable] = None,
        on_quick_query: Optional[Callable] = None,
        on_agent_mode: Optional[Callable] = None,
        on_chat_mode: Optional[Callable] = None,
    ):
        """Set hotkey action callbacks."""
        with self._lock:
            if on_toggle_listen:
                self._callbacks["toggle_listen"] = on_toggle_listen
            if on_push_to_talk_start:
                self._callbacks["push_to_talk_start"] = on_push_to_talk_start
            if on_push_to_talk_end:
                self._callbacks["push_to_talk_end"] = on_push_to_talk_end
            if on_show_hide:
                self._callbacks["show_hide"] = on_show_hide
            if on_mute:
                self._callbacks["mute"] = on_mute
            if on_quick_query:
                self._callbacks["quick_query"] = on_quick_query
            if on_agent_mode:
                self._callbacks["agent_mode"] = on_agent_mode
            if on_chat_mode:
                self._callbacks["chat_mode"] = on_chat_mode
    
    # ── Hotkey Configuration ──────────────────────────────────
    
    def set_hotkey(self, action: str, hotkey: str):
        """
        Set a custom hotkey for an action.
        
        Args:
            action: Action name (e.g., "toggle_listen")
            hotkey: Hotkey string (e.g., "ctrl+space")
        """
        with self._lock:
            if action in self._hotkeys:
                old_hotkey = self._hotkeys[action]
                self._hotkeys[action] = hotkey
                logger.info("Hotkey changed: {} {} → {}", action, old_hotkey, hotkey)
                
                # Re-register if running
                if self._running:
                    self._unregister_hotkey(old_hotkey)
                    self._register_hotkey(action, hotkey)
            else:
                logger.warning("Unknown action: {}", action)
    
    def get_hotkey(self, action: str) -> Optional[str]:
        """Get the hotkey for an action."""
        return self._hotkeys.get(action)
    
    def get_all_hotkeys(self) -> dict[str, str]:
        """Get all hotkey bindings."""
        return self._hotkeys.copy()
    
    # ── Hotkey Handlers ───────────────────────────────────────
    
    def _handle_toggle_listen(self):
        """Handle toggle listening hotkey."""
        logger.debug("Hotkey: toggle_listen")
        callback = self._callbacks.get("toggle_listen")
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error("Toggle listen callback error: {}", e)
    
    def _handle_push_to_talk_start(self):
        """Handle push-to-talk start (key down)."""
        if self._push_to_talk_active:
            return
        
        self._push_to_talk_active = True
        logger.debug("Hotkey: push_to_talk START")
        
        callback = self._callbacks.get("push_to_talk_start")
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error("Push-to-talk start callback error: {}", e)
    
    def _handle_push_to_talk_end(self):
        """Handle push-to-talk end (key up)."""
        if not self._push_to_talk_active:
            return
        
        self._push_to_talk_active = False
        logger.debug("Hotkey: push_to_talk END")
        
        callback = self._callbacks.get("push_to_talk_end")
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error("Push-to-talk end callback error: {}", e)
    
    def _handle_show_hide(self):
        """Handle show/hide hotkey."""
        logger.debug("Hotkey: show_hide")
        callback = self._callbacks.get("show_hide")
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error("Show/hide callback error: {}", e)
    
    def _handle_mute(self):
        """Handle mute/unmute hotkey."""
        logger.debug("Hotkey: mute")
        
        # Toggle mute state
        if self.state_engine.state == AssistantState.MUTED:
            self.state_engine.state = AssistantState.IDLE
        else:
            self.state_engine.state = AssistantState.MUTED
        
        callback = self._callbacks.get("mute")
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error("Mute callback error: {}", e)
    
    def _handle_quick_query(self):
        """Handle quick query hotkey."""
        logger.debug("Hotkey: quick_query")
        callback = self._callbacks.get("quick_query")
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error("Quick query callback error: {}", e)
    
    def _handle_agent_mode(self):
        """Handle agent mode hotkey."""
        logger.debug("Hotkey: agent_mode")
        from assistant.state_engine import AssistantMode
        self.state_engine.switch_mode(AssistantMode.AGENT)
        
        callback = self._callbacks.get("agent_mode")
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error("Agent mode callback error: {}", e)
    
    def _handle_chat_mode(self):
        """Handle chat mode hotkey."""
        logger.debug("Hotkey: chat_mode")
        from assistant.state_engine import AssistantMode
        self.state_engine.switch_mode(AssistantMode.CHAT)
        
        callback = self._callbacks.get("chat_mode")
        if callback:
            try:
                callback()
            except Exception as e:
                logger.error("Chat mode callback error: {}", e)
    
    # ── Hotkey Registration ───────────────────────────────────
    
    def _register_hotkey(self, action: str, hotkey: str):
        """Register a single hotkey."""
        if not KEYBOARD_AVAILABLE:
            return
        
        handler_map = {
            "toggle_listen": self._handle_toggle_listen,
            "show_hide": self._handle_show_hide,
            "mute": self._handle_mute,
            "quick_query": self._handle_quick_query,
            "agent_mode": self._handle_agent_mode,
            "chat_mode": self._handle_chat_mode,
        }
        
        handler = handler_map.get(action)
        if handler:
            try:
                keyboard.add_hotkey(hotkey, handler, suppress=True)
                self._registered_hotkeys.append(hotkey)
                logger.debug("Registered hotkey: {} → {}", hotkey, action)
            except Exception as e:
                logger.error("Failed to register hotkey {}: {}", hotkey, e)
        
        # Special handling for push-to-talk (needs key down/up)
        if action == "push_to_talk":
            try:
                keyboard.on_press_key(hotkey.split("+")[-1], 
                    lambda e: self._handle_push_to_talk_start() if e.is_keypad else None,
                    suppress=True)
                keyboard.on_release_key(hotkey.split("+")[-1],
                    lambda e: self._handle_push_to_talk_end() if e.is_keypad else None,
                    suppress=True)
                logger.debug("Registered push-to-talk: {}", hotkey)
            except Exception as e:
                logger.error("Failed to register push-to-talk: {}", e)
    
    def _unregister_hotkey(self, hotkey: str):
        """Unregister a single hotkey."""
        if not KEYBOARD_AVAILABLE:
            return
        
        try:
            keyboard.unhook_key(hotkey)
            if hotkey in self._registered_hotkeys:
                self._registered_hotkeys.remove(hotkey)
            logger.debug("Unregistered hotkey: {}", hotkey)
        except Exception as e:
            logger.error("Failed to unregister hotkey {}: {}", hotkey, e)
    
    # ── Lifecycle ─────────────────────────────────────────────
    
    def start(self):
        """Start global hotkey listener."""
        if not KEYBOARD_AVAILABLE:
            logger.warning("Cannot start hotkeys - keyboard not available")
            return
        
        if self._running:
            logger.debug("Hotkeys already running")
            return
        
        logger.info("Starting global hotkeys...")
        
        # Register all hotkeys
        for action, hotkey in self._hotkeys.items():
            self._register_hotkey(action, hotkey)
        
        self._running = True
        logger.info("Global hotkeys started")
    
    def stop(self):
        """Stop global hotkey listener."""
        if not self._running:
            return
        
        logger.info("Stopping global hotkeys...")
        
        # Unregister all hotkeys
        for hotkey in self._registered_hotkeys.copy():
            self._unregister_hotkey(hotkey)
        
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.unhook_all()
            except Exception as e:
                logger.error("Failed to unhook all: {}", e)
        
        self._running = False
        logger.info("Global hotkeys stopped")
    
    def is_running(self) -> bool:
        """Check if hotkey listener is running."""
        return self._running
    
    # ── Utilities ─────────────────────────────────────────────
    
    def get_hotkey_display(self) -> dict[str, str]:
        """
        Get hotkeys formatted for display.
        
        Returns dict of action → formatted hotkey string.
        """
        display = {}
        for action, hotkey in self._hotkeys.items():
            # Format: "Ctrl+Space" instead of "ctrl+space"
            formatted = "+".join(k.capitalize() for k in hotkey.split("+"))
            display[action] = formatted
        return display
    
    def destroy(self):
        """Clean up and destroy the hotkey manager."""
        self.stop()
        logger.debug("GlobalHotkey destroyed")
    
    def __repr__(self) -> str:
        return f"GlobalHotkey(running={self._running}, hotkeys={len(self._hotkeys)})"


def is_hotkey_available() -> bool:
    """Check if global hotkey support is available."""
    return KEYBOARD_AVAILABLE