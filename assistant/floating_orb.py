# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/floating_orb.py  —  Floating Orb Widget
#
#  A small, always-on-top floating orb that serves as the
#  primary interaction point for Agent Mode.
#
#  Features:
#  - Draggable positioning
#  - State-based animations (pulse, glow, color changes)
#  - Click to expand to Agent Panel
#  - Right-click context menu
#  - Visual feedback for all assistant states
#
#  States visual:
#  - IDLE: Subtle glow, neutral color
#  - LISTENING: Pulsing rings, microphone icon
#  - THINKING: Spinning animation, loading dots
#  - SPEAKING: Wave animation, speaker icon
#  - EXECUTING: Progress indicator
#  - ERROR: Red pulse
# ============================================================

import tkinter as tk
from tkinter import Menu
import threading
import math
from typing import Callable, Optional
from loguru import logger

from assistant.state_engine import StateEngine, AssistantState, AssistantMode


class FloatingOrb:
    """
    Floating orb widget for Agent Mode interaction.
    
    A small, circular, always-on-top window that:
    - Shows assistant state via color/animation
    - Can be dragged anywhere on screen
    - Expands to Agent Panel on click
    - Provides quick access via context menu
    
    Usage:
        orb = FloatingOrb(root, state_engine)
        orb.show()
    """
    
    # ── Visual Constants ──────────────────────────────────────
    
    ORB_SIZE = 56  # pixels
    CANVAS_SIZE = 80  # Extra space for glow effects
    
    # State colors
    STATE_COLORS = {
        AssistantState.IDLE: "#6366f1",       # Indigo
        AssistantState.LISTENING: "#22c55e",  # Green
        AssistantState.THINKING: "#f59e0b",   # Amber
        AssistantState.SPEAKING: "#3b82f6",   # Blue
        AssistantState.EXECUTING: "#8b5cf6",  # Purple
        AssistantState.MUTED: "#6b7280",      # Gray
        AssistantState.ERROR: "#ef4444",      # Red
        AssistantState.MINIMIZED: "#6366f1",  # Indigo
    }
    
    # State icons (simple text representations)
    STATE_ICONS = {
        AssistantState.IDLE: "●",
        AssistantState.LISTENING: "🎤",
        AssistantState.THINKING: "⋯",
        AssistantState.SPEAKING: "🔊",
        AssistantState.EXECUTING: "⚡",
        AssistantState.MUTED: "🔇",
        AssistantState.ERROR: "!",
        AssistantState.MINIMIZED: "●",
    }
    
    def __init__(
        self,
        parent: tk.Tk,
        state_engine: StateEngine,
        on_click: Optional[Callable] = None,
    ):
        self.parent = parent
        self.state_engine = state_engine
        self._on_click = on_click
        
        # Window setup
        self.window = tk.Toplevel(parent)
        self.window.title("DREX")
        self.window.overrideredirect(True)  # No title bar
        self.window.attributes("-topmost", True)  # Always on top
        self.window.attributes("-alpha", 0.95)  # Slight transparency
        
        # Make background transparent (Windows)
        try:
            self.window.attributes("-transparentcolor", "#010101")
        except tk.TclError:
            pass  # Not supported on all platforms
        
        # Position (bottom-right corner by default)
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        self.x = screen_width - 120
        self.y = screen_height - 150
        
        # Drag state
        self._drag_data = {"x": 0, "y": 0}
        self._is_dragging = False
        
        # Animation state
        self._animation_id = None
        self._pulse_phase = 0.0
        self._ring_radius = 0
        
        # Create canvas
        self.canvas = tk.Canvas(
            self.window,
            width=self.CANVAS_SIZE,
            height=self.CANVAS_SIZE,
            bg="#010101",  # Transparent background
            highlightthickness=0,
        )
        self.canvas.pack()
        
        # Draw orb
        self._draw_orb()
        
        # Bind events
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_click)  # Context menu
        
        # Register state callback
        self.state_engine.register_state_callback(self._on_state_change)
        
        # Start animation loop
        self._animate()
        
        logger.debug("FloatingOrb initialized at ({}, {})", self.x, self.y)
    
    # ── Drawing ───────────────────────────────────────────────
    
    def _draw_orb(self):
        """Draw the orb with current state."""
        self.canvas.delete("all")
        
        center = self.CANVAS_SIZE // 2
        radius = self.ORB_SIZE // 2
        
        # Get current state color
        state = self.state_engine.state
        color = self.STATE_COLORS.get(state, "#6366f1")
        
        # Draw glow rings (for active states)
        if state in (AssistantState.LISTENING, AssistantState.SPEAKING):
            self._draw_glow_rings(center, radius, color)
        
        # Draw main orb (circle)
        self.canvas.create_oval(
            center - radius,
            center - radius,
            center + radius,
            center + radius,
            fill=color,
            outline="",
            tags="orb",
        )
        
        # Draw inner highlight (3D effect)
        highlight_radius = radius - 8
        self.canvas.create_oval(
            center - highlight_radius,
            center - highlight_radius - 4,
            center + highlight_radius,
            center + highlight_radius - 4,
            fill="",
            outline=self._lighten_color(color, 40),
            width=2,
            tags="highlight",
        )
        
        # Draw state icon
        icon = self.STATE_ICONS.get(state, "●")
        self.canvas.create_text(
            center, center,
            text=icon,
            fill="white",
            font=("Segoe UI", 16, "bold"),
            tags="icon",
        )
    
    def _draw_glow_rings(self, center: int, radius: int, color: str):
        """Draw animated glow rings for active states."""
        # Outer ring (pulsing)
        ring_radius = radius + 4 + self._ring_radius
        alpha_color = self._lighten_color(color, 20)
        
        self.canvas.create_oval(
            center - ring_radius,
            center - ring_radius,
            center + ring_radius,
            center + ring_radius,
            fill="",
            outline=alpha_color,
            width=2,
            tags="ring",
        )
        
        # Second ring (delayed)
        ring_radius2 = radius + 8 + self._ring_radius * 0.5
        self.canvas.create_oval(
            center - ring_radius2,
            center - ring_radius2,
            center + ring_radius2,
            center + ring_radius2,
            fill="",
            outline=self._lighten_color(color, 10),
            width=1,
            tags="ring2",
        )
    
    # ── Animation ─────────────────────────────────────────────
    
    def _animate(self):
        """Animation loop."""
        state = self.state_engine.state
        
        # Update pulse phase
        self._pulse_phase += 0.1
        
        # Calculate ring radius based on state
        if state in (AssistantState.LISTENING, AssistantState.SPEAKING):
            self._ring_radius = int(4 * math.sin(self._pulse_phase)) + 4
        elif state == AssistantState.THINKING:
            self._ring_radius = int(3 * abs(math.sin(self._pulse_phase * 2)))
        else:
            self._ring_radius = 0
        
        # Redraw orb
        self._draw_orb()
        
        # Schedule next frame (30 FPS)
        self._animation_id = self.window.after(33, self._animate)
    
    def _stop_animation(self):
        """Stop the animation loop."""
        if self._animation_id:
            self.window.after_cancel(self._animation_id)
            self._animation_id = None
    
    # ── Event Handlers ────────────────────────────────────────
    
    def _on_press(self, event):
        """Handle mouse press (start drag)."""
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._is_dragging = False
    
    def _on_drag(self, event):
        """Handle mouse drag."""
        dx = abs(event.x - self._drag_data["x"])
        dy = abs(event.y - self._drag_data["y"])
        
        if dx > 5 or dy > 5:
            self._is_dragging = True
            x = self.window.winfo_x() + event.x - self._drag_data["x"]
            y = self.window.winfo_y() + event.y - self._drag_data["y"]
            self.window.geometry(f"+{x}+{y}")
    
    def _on_release(self, event):
        """Handle mouse release (click or end drag)."""
        if not self._is_dragging:
            # This was a click, not a drag
            self._handle_click()
    
    def _handle_click(self):
        """Handle orb click."""
        logger.debug("Orb clicked")
        if self._on_click:
            try:
                self._on_click()
            except Exception as e:
                logger.error("Orb click callback error: {}", e)
    
    def _on_right_click(self, event):
        """Handle right-click (context menu)."""
        menu = Menu(self.window, tearoff=0)
        
        state = self.state_engine.state
        mode = self.state_engine.mode
        
        # Mode toggle
        if mode == AssistantMode.AGENT:
            menu.add_command(label="Switch to Chat Mode", command=self._switch_to_chat)
        else:
            menu.add_command(label="Switch to Agent Mode", command=self._switch_to_agent)
        
        menu.add_separator()
        
        # State-specific actions
        if state == AssistantState.MUTED:
            menu.add_command(label="Unmute", command=self._unmute)
        else:
            menu.add_command(label="Mute", command=self._mute)
        
        menu.add_separator()
        
        # General actions
        menu.add_command(label="Minimize to Tray", command=self._minimize)
        menu.add_command(label="Settings", command=self._open_settings)
        
        menu.add_separator()
        menu.add_command(label="Quit DREX", command=self._quit)
        
        # Show menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _on_state_change(self, old_state: AssistantState, new_state: AssistantState):
        """Handle state change (update visual)."""
        logger.debug("Orb state change: {} → {}", old_state.name, new_state.name)
        # Orb will redraw on next animation frame
    
    # ── Context Menu Actions ──────────────────────────────────
    
    def _switch_to_chat(self):
        """Switch to Chat mode."""
        self.state_engine.switch_mode(AssistantMode.CHAT)
    
    def _switch_to_agent(self):
        """Switch to Agent mode."""
        self.state_engine.switch_mode(AssistantMode.AGENT)
    
    def _mute(self):
        """Mute microphone."""
        self.state_engine.state = AssistantState.MUTED
    
    def _unmute(self):
        """Unmute microphone."""
        self.state_engine.state = AssistantState.IDLE
    
    def _minimize(self):
        """Minimize to system tray."""
        self.state_engine.state = AssistantState.MINIMIZED
        self.hide()
    
    def _open_settings(self):
        """Open settings window."""
        logger.info("Settings requested from orb")
        # TODO: Implement settings window
    
    def _quit(self):
        """Quit DREX."""
        logger.info("Quit requested from orb")
        self.parent.quit()
    
    # ── Visibility ────────────────────────────────────────────
    
    def show(self):
        """Show the floating orb."""
        self.window.geometry(f"+{self.x}+{self.y}")
        self.window.deiconify()
        logger.debug("Floating orb shown")
    
    def hide(self):
        """Hide the floating orb."""
        self.window.withdraw()
        logger.debug("Floating orb hidden")
    
    def is_visible(self) -> bool:
        """Check if orb is visible."""
        return self.window.winfo_viewable()
    
    # ── Position ──────────────────────────────────────────────
    
    def set_position(self, x: int, y: int):
        """Set orb position."""
        self.x = x
        self.y = y
        self.window.geometry(f"+{x}+{y}")
    
    def get_position(self) -> tuple[int, int]:
        """Get orb position."""
        return (self.window.winfo_x(), self.window.winfo_y())
    
    # ── Utilities ─────────────────────────────────────────────
    
    def _lighten_color(self, hex_color: str, amount: int) -> str:
        """Lighten a hex color by amount."""
        hex_color = hex_color.lstrip("#")
        r = min(255, int(hex_color[0:2], 16) + amount)
        g = min(255, int(hex_color[2:4], 16) + amount)
        b = min(255, int(hex_color[4:6], 16) + amount)
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def destroy(self):
        """Clean up and destroy the orb."""
        self._stop_animation()
        self.state_engine.unregister_state_callback(self._on_state_change)
        self.window.destroy()
        logger.debug("FloatingOrb destroyed")
    
    def __repr__(self) -> str:
        return f"FloatingOrb(pos={self.get_position()}, visible={self.is_visible()})"