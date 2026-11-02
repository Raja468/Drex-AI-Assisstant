# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/system_tray.py  —  System Tray Integration
#
#  Provides system tray icon and menu for DREX.
#
#  Features:
#  - Tray icon with state-based appearance
#  - Context menu for quick actions
#  - Double-click to show/hide main window
#  - Balloon notifications for important events
#  - Background operation when minimized
#
#  Uses pystray library for cross-platform tray support.
#  Falls back gracefully if pystray is not available.
# ============================================================

import threading
from typing import Callable, Optional
from loguru import logger

from assistant.state_engine import StateEngine, AssistantState, AssistantMode

# Try to import pystray (optional dependency)
try:
    import pystray
    from pystray import MenuItem, Menu
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    logger.warning("pystray not available - system tray disabled")


class SystemTray:
    """
    System tray integration for DREX.
    
    Provides:
    - Tray icon with state-based appearance
    - Context menu for quick actions
    - Background operation support
    
    Usage:
        tray = SystemTray(state_engine)
        tray.set_callbacks(on_show=show_window, on_quit=quit_app)
        tray.start()
    """
    
    # State colors for tray icon
    STATE_COLORS = {
        AssistantState.IDLE: (99, 102, 241),       # Indigo
        AssistantState.LISTENING: (34, 197, 94),   # Green
        AssistantState.THINKING: (245, 158, 11),   # Amber
        AssistantState.SPEAKING: (59, 130, 246),   # Blue
        AssistantState.EXECUTING: (139, 92, 246),  # Purple
        AssistantState.MUTED: (107, 114, 128),     # Gray
        AssistantState.ERROR: (239, 68, 68),       # Red
        AssistantState.MINIMIZED: (99, 102, 241),  # Indigo
    }
    
    def __init__(self, state_engine: StateEngine):
        self.state_engine = state_engine
        self._lock = threading.RLock()
        
        # Callbacks
        self._on_show: Optional[Callable] = None
        self._on_hide: Optional[Callable] = None
        self._on_quit: Optional[Callable] = None
        self._on_settings: Optional[Callable] = None
        self._on_mode_change: Optional[Callable[[AssistantMode], None]] = None
        
        # Tray icon
        self._icon = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Register state callback
        if PYSTRAY_AVAILABLE:
            self.state_engine.register_state_callback(self._on_state_change)
        
        logger.debug("SystemTray initialized | available={}", PYSTRAY_AVAILABLE)
    
    # ── Icon Creation ─────────────────────────────────────────
    
    def _create_icon(self, state: AssistantState = AssistantState.IDLE) -> "Image.Image":
        """Create tray icon image based on state."""
        # Create 64x64 image
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Get state color
        color = self.STATE_COLORS.get(state, (99, 102, 241))
        
        # Draw circle
        margin = 8
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=color,
        )
        
        # Draw "D" letter
        draw.text(
            (size // 2 - 8, size // 2 - 12),
            "D",
            fill=(255, 255, 255),
        )
        
        return image
    
    # ── Menu Creation ─────────────────────────────────────────
    
    def _create_menu(self) -> "Menu":
        """Create tray context menu."""
        mode = self.state_engine.mode
        
        return Menu(
            MenuItem("Show DREX", self._handle_show, default=True),
            MenuItem("Hide DREX", self._handle_hide),
            Menu.SEPARATOR,
            MenuItem(
                "Agent Mode" if mode == AssistantMode.AGENT else "Switch to Agent",
                self._handle_agent_mode,
                checked=lambda item: self.state_engine.mode == AssistantMode.AGENT,
            ),
            MenuItem(
                "Chat Mode" if mode == AssistantMode.CHAT else "Switch to Chat",
                self._handle_chat_mode,
                checked=lambda item: self.state_engine.mode == AssistantMode.CHAT,
            ),
            Menu.SEPARATOR,
            MenuItem("Settings", self._handle_settings),
            Menu.SEPARATOR,
            MenuItem("Quit", self._handle_quit),
        )
    
    # ── Menu Handlers ─────────────────────────────────────────
    
    def _handle_show(self, icon=None, item=None):
        """Handle show menu item."""
        if self._on_show:
            try:
                self._on_show()
            except Exception as e:
                logger.error("Show callback error: {}", e)
    
    def _handle_hide(self, icon=None, item=None):
        """Handle hide menu item."""
        if self._on_hide:
            try:
                self._on_hide()
            except Exception as e:
                logger.error("Hide callback error: {}", e)
    
    def _handle_agent_mode(self, icon=None, item=None):
        """Handle agent mode menu item."""
        self.state_engine.switch_mode(AssistantMode.AGENT)
        if self._on_mode_change:
            try:
                self._on_mode_change(AssistantMode.AGENT)
            except Exception as e:
                logger.error("Mode change callback error: {}", e)
    
    def _handle_chat_mode(self, icon=None, item=None):
        """Handle chat mode menu item."""
        self.state_engine.switch_mode(AssistantMode.CHAT)
        if self._on_mode_change:
            try:
                self._on_mode_change(AssistantMode.CHAT)
            except Exception as e:
                logger.error("Mode change callback error: {}", e)
    
    def _handle_settings(self, icon=None, item=None):
        """Handle settings menu item."""
        if self._on_settings:
            try:
                self._on_settings()
            except Exception as e:
                logger.error("Settings callback error: {}", e)
    
    def _handle_quit(self, icon=None, item=None):
        """Handle quit menu item."""
        logger.info("Quit requested from tray")
        self.stop()
        if self._on_quit:
            try:
                self._on_quit()
            except Exception as e:
                logger.error("Quit callback error: {}", e)
    
    # ── State Handling ────────────────────────────────────────
    
    def _on_state_change(self, old_state: AssistantState, new_state: AssistantState):
        """Handle state change - update tray icon."""
        if self._icon:
            try:
                self._icon.icon = self._create_icon(new_state)
            except Exception as e:
                logger.error("Failed to update tray icon: {}", e)
    
    # ── Callbacks ─────────────────────────────────────────────
    
    def set_callbacks(
        self,
        on_show: Optional[Callable] = None,
        on_hide: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
        on_settings: Optional[Callable] = None,
        on_mode_change: Optional[Callable[[AssistantMode], None]] = None,
    ):
        """Set tray action callbacks."""
        with self._lock:
            if on_show:
                self._on_show = on_show
            if on_hide:
                self._on_hide = on_hide
            if on_quit:
                self._on_quit = on_quit
            if on_settings:
                self._on_settings = on_settings
            if on_mode_change:
                self._on_mode_change = on_mode_change
    
    # ── Lifecycle ─────────────────────────────────────────────
    
    def start(self):
        """Start the system tray icon."""
        if not PYSTRAY_AVAILABLE:
            logger.warning("Cannot start tray - pystray not available")
            return
        
        if self._running:
            logger.debug("Tray already running")
            return
        
        logger.info("Starting system tray...")
        
        # Create icon
        self._icon = pystray.Icon(
            "drex",
            icon=self._create_icon(self.state_engine.state),
            title="DREX AI Assistant",
            menu=self._create_menu(),
        )
        
        # Run in separate thread
        self._running = True
        self._thread = threading.Thread(
            target=self._run_tray,
            daemon=True,
            name="SystemTray",
        )
        self._thread.start()
        
        logger.info("System tray started")
    
    def _run_tray(self):
        """Run the tray icon (blocking, run in thread)."""
        try:
            self._icon.run()
        except Exception as e:
            logger.error("Tray icon error: {}", e)
        finally:
            self._running = False
    
    def stop(self):
        """Stop the system tray icon."""
        if not self._running:
            return
        
        logger.info("Stopping system tray...")
        
        if self._icon:
            try:
                self._icon.stop()
            except Exception as e:
                logger.error("Failed to stop tray icon: {}", e)
        
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        logger.info("System tray stopped")
    
    def is_running(self) -> bool:
        """Check if tray is running."""
        return self._running
    
    # ── Notifications ─────────────────────────────────────────
    
    def notify(self, title: str, message: str, timeout: float = 5.0):
        """
        Show a balloon notification.
        
        Args:
            title: Notification title
            message: Notification message
            timeout: Auto-dismiss time in seconds
        """
        if not self._icon:
            logger.debug("Cannot notify - tray not running")
            return
        
        try:
            self._icon.notify(message, title)
            logger.debug("Tray notification: {} - {}", title, message)
        except Exception as e:
            logger.error("Failed to show notification: {}", e)
    
    # ── Utilities ─────────────────────────────────────────────
    
    def update_tooltip(self, text: str):
        """Update tray icon tooltip."""
        if self._icon:
            try:
                self._icon.title = text
            except Exception as e:
                logger.error("Failed to update tooltip: {}", e)
    
    def destroy(self):
        """Clean up and destroy the tray."""
        self.stop()
        if PYSTRAY_AVAILABLE:
            self.state_engine.unregister_state_callback(self._on_state_change)
        logger.debug("SystemTray destroyed")
    
    def __repr__(self) -> str:
        return f"SystemTray(running={self._running}, available={PYSTRAY_AVAILABLE})"


def is_tray_available() -> bool:
    """Check if system tray support is available."""
    return PYSTRAY_AVAILABLE