# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/agent_panel.py  —  Compact Agent Panel
#
#  A compact, modern assistant panel that appears when the
#  floating orb is clicked. Designed for quick interactions.
#
#  Features:
#  - Compact size (400x500px)
#  - Modern dark glassmorphism design
#  - Streaming text display
#  - Voice status indicator
#  - Quick input bar
#  - Smooth slide-in animation
#  - Auto-hide on inactivity
#
#  Layout:
#  ┌─────────────────────────┐
#  │  DREX          [─][□][×]│  Header
#  ├─────────────────────────┤
#  │                         │
#  │   Streaming response    │  Content area
#  │   area with smooth      │
#  │   token rendering       │
#  │                         │
#  ├─────────────────────────┤
#  │  🎤 Listening...        │  Status bar
#  ├─────────────────────────┤
#  │  [Type or speak...  ] [→]│  Input bar
#  └─────────────────────────┘
# ============================================================

import tkinter as tk
from tkinter import font as tkfont
import threading
import time
from typing import Callable, Optional
from loguru import logger

from assistant.state_engine import StateEngine, AssistantState, AssistantMode


class AgentPanel:
    """
    Compact agent panel for quick interactions.
    
    Appears when floating orb is clicked.
    Provides streaming text display and quick input.
    
    Usage:
        panel = AgentPanel(root, state_engine)
        panel.show()
    """
    
    # ── Visual Constants ──────────────────────────────────────
    
    WIDTH = 400
    HEIGHT = 520
    HEADER_HEIGHT = 48
    STATUS_HEIGHT = 36
    INPUT_HEIGHT = 52
    
    # Colors (dark glassmorphism)
    BG_PRIMARY = "#1a1a2e"
    BG_SECONDARY = "#16213e"
    BG_TERTIARY = "#0f3460"
    BG_INPUT = "#1e1e3f"
    
    TEXT_PRIMARY = "#e4e4e7"
    TEXT_SECONDARY = "#a1a1aa"
    TEXT_MUTED = "#71717a"
    
    ACCENT = "#6366f1"
    ACCENT_HOVER = "#818cf8"
    
    BORDER = "#27272a"
    
    # State colors
    STATE_COLORS = {
        AssistantState.IDLE: "#6366f1",
        AssistantState.LISTENING: "#22c55e",
        AssistantState.THINKING: "#f59e0b",
        AssistantState.SPEAKING: "#3b82f6",
        AssistantState.EXECUTING: "#8b5cf6",
        AssistantState.MUTED: "#6b7280",
        AssistantState.ERROR: "#ef4444",
        AssistantState.MINIMIZED: "#6366f1",
    }
    
    def __init__(
        self,
        parent: tk.Tk,
        state_engine: StateEngine,
        on_send: Optional[Callable[[str], None]] = None,
        on_close: Optional[Callable] = None,
    ):
        self.parent = parent
        self.state_engine = state_engine
        self._on_send = on_send
        self._on_close = on_close
        
        # Window setup
        self.window = tk.Toplevel(parent)
        self.window.title("DREX Assistant")
        self.window.overrideredirect(True)  # No title bar
        self.window.attributes("-topmost", True)
        
        # Size and position
        self._setup_geometry()
        
        # Visibility state
        self._visible = False
        self._animation_id = None
        
        # Content state
        self._messages: list[dict] = []
        self._streaming_text = ""
        self._stream_buffer = ""
        
        # Build UI
        self._build_ui()
        
        # Register state callback
        self.state_engine.register_state_callback(self._on_state_change)
        
        # Hide initially
        self.window.withdraw()
        
        logger.debug("AgentPanel initialized")
    
    def _setup_geometry(self):
        """Set up window geometry and position."""
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # Position: right side, vertically centered
        x = screen_width - self.WIDTH - 20
        y = (screen_height - self.HEIGHT) // 2
        
        self.window.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        
        # Make window draggable
        self.window.bind("<Button-1>", self._start_drag)
        self.window.bind("<B1-Motion>", self._on_drag)
    
    def _build_ui(self):
        """Build the panel UI."""
        # Main container
        self.main_frame = tk.Frame(
            self.window,
            bg=self.BG_PRIMARY,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        self.main_frame.pack(fill="both", expand=True)
        
        # ── Header ────────────────────────────────────────────
        self._build_header()
        
        # ── Content Area ──────────────────────────────────────
        self._build_content()
        
        # ── Status Bar ────────────────────────────────────────
        self._build_status_bar()
        
        # ── Input Bar ─────────────────────────────────────────
        self._build_input_bar()
    
    def _build_header(self):
        """Build the header section."""
        header = tk.Frame(
            self.main_frame,
            bg=self.BG_SECONDARY,
            height=self.HEADER_HEIGHT,
        )
        header.pack(fill="x")
        header.pack_propagate(False)
        
        # Logo and title
        title_frame = tk.Frame(header, bg=self.BG_SECONDARY)
        title_frame.pack(side="left", padx=16, pady=8)
        
        # State indicator dot
        self.state_dot = tk.Canvas(
            title_frame,
            width=12, height=12,
            bg=self.BG_SECONDARY,
            highlightthickness=0,
        )
        self.state_dot.pack(side="left", padx=(0, 8))
        self.state_dot.create_oval(2, 2, 10, 10, fill=self.ACCENT, outline="")
        
        # Title
        title_label = tk.Label(
            title_frame,
            text="DREX",
            bg=self.BG_SECONDARY,
            fg=self.TEXT_PRIMARY,
            font=("Segoe UI", 14, "bold"),
        )
        title_label.pack(side="left")
        
        # Window controls
        controls = tk.Frame(header, bg=self.BG_SECONDARY)
        controls.pack(side="right", padx=8)
        
        # Minimize button
        self.min_btn = tk.Label(
            controls,
            text="─",
            bg=self.BG_SECONDARY,
            fg=self.TEXT_SECONDARY,
            font=("Segoe UI", 12),
            cursor="hand2",
        )
        self.min_btn.pack(side="left", padx=4)
        self.min_btn.bind("<Button-1>", lambda e: self.minimize())
        self.min_btn.bind("<Enter>", lambda e: self.min_btn.config(fg=self.TEXT_PRIMARY))
        self.min_btn.bind("<Leave>", lambda e: self.min_btn.config(fg=self.TEXT_SECONDARY))
        
        # Close button
        self.close_btn = tk.Label(
            controls,
            text="×",
            bg=self.BG_SECONDARY,
            fg=self.TEXT_SECONDARY,
            font=("Segoe UI", 14),
            cursor="hand2",
        )
        self.close_btn.pack(side="left", padx=4)
        self.close_btn.bind("<Button-1>", lambda e: self.hide())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(fg="#ef4444"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(fg=self.TEXT_SECONDARY))
    
    def _build_content(self):
        """Build the content/message area."""
        content_frame = tk.Frame(
            self.main_frame,
            bg=self.BG_PRIMARY,
        )
        content_frame.pack(fill="both", expand=True, padx=8, pady=8)
        
        # Scrollable text area
        self.content_text = tk.Text(
            content_frame,
            bg=self.BG_PRIMARY,
            fg=self.TEXT_PRIMARY,
            font=("Consolas", 11),
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            padx=12,
            pady=12,
            spacing1=2,
            spacing3=2,
            cursor="arrow",
            state="disabled",
        )
        self.content_text.pack(fill="both", expand=True)
        
        # Scrollbar
        scrollbar = tk.Scrollbar(
            content_frame,
            command=self.content_text.yview,
            bg=self.BG_SECONDARY,
            troughcolor=self.BG_PRIMARY,
            width=8,
        )
        scrollbar.pack(side="right", fill="y")
        self.content_text.config(yscrollcommand=scrollbar.set)
        
        # Configure text tags
        self.content_text.tag_configure("user", foreground=self.ACCENT_HOVER)
        self.content_text.tag_configure("assistant", foreground=self.TEXT_PRIMARY)
        self.content_text.tag_configure("system", foreground=self.TEXT_MUTED, font=("Consolas", 9, "italic"))
        self.content_text.tag_configure("streaming", foreground=self.TEXT_PRIMARY)
        
        # Welcome message
        self._append_message("system", "DREX Assistant ready. Click the orb or type below to start.")
    
    def _build_status_bar(self):
        """Build the status bar."""
        status_frame = tk.Frame(
            self.main_frame,
            bg=self.BG_SECONDARY,
            height=self.STATUS_HEIGHT,
        )
        status_frame.pack(fill="x")
        status_frame.pack_propagate(False)
        
        # State icon
        self.status_icon = tk.Label(
            status_frame,
            text="●",
            bg=self.BG_SECONDARY,
            fg=self.ACCENT,
            font=("Segoe UI", 10),
        )
        self.status_icon.pack(side="left", padx=(16, 8))
        
        # State text
        self.status_text = tk.Label(
            status_frame,
            text="Ready",
            bg=self.BG_SECONDARY,
            fg=self.TEXT_SECONDARY,
            font=("Segoe UI", 10),
        )
        self.status_text.pack(side="left")
        
        # Mode indicator
        self.mode_label = tk.Label(
            status_frame,
            text="AGENT",
            bg=self.BG_TERTIARY,
            fg=self.TEXT_PRIMARY,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
        )
        self.mode_label.pack(side="right", padx=16)
    
    def _build_input_bar(self):
        """Build the input bar."""
        input_frame = tk.Frame(
            self.main_frame,
            bg=self.BG_PRIMARY,
            height=self.INPUT_HEIGHT,
        )
        input_frame.pack(fill="x", padx=8, pady=(0, 8))
        input_frame.pack_propagate(False)
        
        # Input container (rounded look)
        input_container = tk.Frame(
            input_frame,
            bg=self.BG_INPUT,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        input_container.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Text input
        self.input_entry = tk.Entry(
            input_container,
            bg=self.BG_INPUT,
            fg=self.TEXT_PRIMARY,
            insertbackground=self.TEXT_PRIMARY,
            font=("Segoe UI", 11),
            borderwidth=0,
            highlightthickness=0,
        )
        self.input_entry.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        self.input_entry.insert(0, "")
        
        # Placeholder
        self._show_placeholder()
        self.input_entry.bind("<FocusIn>", self._on_input_focus)
        self.input_entry.bind("<FocusOut>", self._on_input_blur)
        self.input_entry.bind("<Return>", self._on_send_message)
        
        # Send button
        self.send_btn = tk.Label(
            input_container,
            text="→",
            bg=self.BG_INPUT,
            fg=self.ACCENT,
            font=("Segoe UI", 14, "bold"),
            cursor="hand2",
        )
        self.send_btn.pack(side="right", padx=12)
        self.send_btn.bind("<Button-1>", self._on_send_message)
    
    # ── Message Handling ──────────────────────────────────────
    
    def _append_message(self, role: str, text: str):
        """Append a message to the content area."""
        self.content_text.config(state="normal")
        
        if role == "user":
            self.content_text.insert("end", f"\nYou: {text}\n", "user")
        elif role == "assistant":
            self.content_text.insert("end", f"\nDREX: {text}\n", "assistant")
        else:
            self.content_text.insert("end", f"\n{text}\n", "system")
        
        self.content_text.config(state="disabled")
        self.content_text.see("end")
        
        self._messages.append({"role": role, "text": text})
    
    def start_streaming(self):
        """Start streaming response display."""
        self._streaming_text = ""
        self._stream_buffer = ""
        
        self.content_text.config(state="normal")
        self.content_text.insert("end", "\nDREX: ", "assistant")
        self._stream_start_index = self.content_text.index("end-1c")
        self.content_text.config(state="disabled")
    
    def append_stream_token(self, token: str):
        """Append a token to the streaming response."""
        self._streaming_text += token
        self._stream_buffer += token
        
        # Batch updates for performance (every 3 chars or on newline)
        if len(self._stream_buffer) >= 3 or "\n" in token:
            self._flush_stream_buffer()
    
    def _flush_stream_buffer(self):
        """Flush the stream buffer to the text widget."""
        if not self._stream_buffer:
            return
        
        self.content_text.config(state="normal")
        self.content_text.insert("end", self._stream_buffer, "streaming")
        self.content_text.config(state="disabled")
        self.content_text.see("end")
        
        self._stream_buffer = ""
    
    def end_streaming(self):
        """End streaming response display."""
        self._flush_stream_buffer()
        
        self.content_text.config(state="normal")
        self.content_text.insert("end", "\n", "streaming")
        self.content_text.config(state="disabled")
        
        self._messages.append({"role": "assistant", "text": self._streaming_text})
        self._streaming_text = ""
    
    # ── Input Handling ────────────────────────────────────────
    
    def _show_placeholder(self):
        """Show placeholder text in input."""
        self.input_entry.config(fg=self.TEXT_MUTED)
        self.input_entry.insert(0, "Type or speak...")
        self._has_placeholder = True
    
    def _on_input_focus(self, event):
        """Handle input focus."""
        if self._has_placeholder:
            self.input_entry.delete(0, "end")
            self.input_entry.config(fg=self.TEXT_PRIMARY)
            self._has_placeholder = False
    
    def _on_input_blur(self, event):
        """Handle input blur."""
        if not self.input_entry.get():
            self._show_placeholder()
    
    def _on_send_message(self, event=None):
        """Handle send message."""
        if self._has_placeholder:
            return
        
        text = self.input_entry.get().strip()
        if not text:
            return
        
        # Clear input
        self.input_entry.delete(0, "end")
        
        # Display user message
        self._append_message("user", text)
        
        # Call send callback
        if self._on_send:
            try:
                self._on_send(text)
            except Exception as e:
                logger.error("Send callback error: {}", e)
    
    # ── State Handling ────────────────────────────────────────
    
    def _on_state_change(self, old_state: AssistantState, new_state: AssistantState):
        """Handle state change."""
        # Update state dot color
        color = self.STATE_COLORS.get(new_state, self.ACCENT)
        self.state_dot.delete("all")
        self.state_dot.create_oval(2, 2, 10, 10, fill=color, outline="")
        
        # Update status icon
        self.status_icon.config(fg=color)
        
        # Update status text
        state_texts = {
            AssistantState.IDLE: "Ready",
            AssistantState.LISTENING: "Listening...",
            AssistantState.THINKING: "Thinking...",
            AssistantState.SPEAKING: "Speaking...",
            AssistantState.EXECUTING: "Executing...",
            AssistantState.MUTED: "Muted",
            AssistantState.ERROR: "Error",
            AssistantState.MINIMIZED: "Minimized",
        }
        self.status_text.config(text=state_texts.get(new_state, "Ready"))
    
    # ── Dragging ──────────────────────────────────────────────
    
    def _start_drag(self, event):
        """Start window drag."""
        self._drag_x = event.x
        self._drag_y = event.y
    
    def _on_drag(self, event):
        """Handle window drag."""
        x = self.window.winfo_x() + event.x - self._drag_x
        y = self.window.winfo_y() + event.y - self._drag_y
        self.window.geometry(f"+{x}+{y}")
    
    # ── Visibility ────────────────────────────────────────────
    
    def show(self):
        """Show the agent panel with slide-in animation."""
        if self._visible:
            return
        
        self._visible = True
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        
        logger.debug("Agent panel shown")
    
    def hide(self):
        """Hide the agent panel."""
        if not self._visible:
            return
        
        self._visible = False
        self.window.withdraw()
        
        if self._on_close:
            try:
                self._on_close()
            except Exception as e:
                logger.error("Close callback error: {}", e)
        
        logger.debug("Agent panel hidden")
    
    def minimize(self):
        """Minimize the panel (hide but keep orb)."""
        self.hide()
    
    def toggle(self):
        """Toggle panel visibility."""
        if self._visible:
            self.hide()
        else:
            self.show()
    
    def is_visible(self) -> bool:
        """Check if panel is visible."""
        return self._visible
    
    # ── Utilities ─────────────────────────────────────────────
    
    def clear_messages(self):
        """Clear all messages."""
        self.content_text.config(state="normal")
        self.content_text.delete("1.0", "end")
        self.content_text.config(state="disabled")
        self._messages.clear()
        self._append_message("system", "Conversation cleared.")
    
    def get_messages(self) -> list[dict]:
        """Get all messages."""
        return self._messages.copy()
    
    def set_send_callback(self, callback: Callable[[str], None]):
        """Set the send message callback."""
        self._on_send = callback
    
    def destroy(self):
        """Clean up and destroy the panel."""
        self.state_engine.unregister_state_callback(self._on_state_change)
        self.window.destroy()
        logger.debug("AgentPanel destroyed")
    
    def __repr__(self) -> str:
        return f"AgentPanel(visible={self._visible}, messages={len(self._messages)})"