# ============================================================
#  DREX - AI Desktop Assistant
#  gui/input_bar.py  —  Message Input Bar
#
#  WHAT IT DOES:
#  The bottom input area where users type or speak commands.
#  Contains:
#  - Text entry field (multiline, auto-resize)
#  - Mic button (hold to record or click to toggle listening)
#  - Send button
#  - Keyboard shortcut: Enter to send, Shift+Enter for newline
# ============================================================

import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional
from gui.theme import Colors, Fonts, Sizing, Spacing
from utils.logger import logger


class InputBar(ctk.CTkFrame):
    """
    Message input bar at the bottom of the chat window.
    Fires on_submit(text) when user sends a message.
    Fires on_voice_toggle() when mic button is clicked.
    """

    def __init__(
        self,
        parent,
        on_submit: Callable[[str], None],
        on_voice_toggle: Callable[[], None],
        **kwargs
    ):
        super().__init__(
            parent,
            fg_color=Colors.BG_PANEL,
            corner_radius=0,
            border_width=1,
            border_color=Colors.BG_BORDER,
            height=80,
            **kwargs
        )
        self.grid_propagate(False)

        self.on_submit       = on_submit
        self.on_voice_toggle = on_voice_toggle
        self._is_listening   = False
        self._is_disabled    = False

        self._build()
        logger.debug("InputBar initialized")

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Mic button (left) ─────────────────────────────────
        self._mic_btn = ctk.CTkButton(
            self,
            text="🎤",
            width=Sizing.BTN_ICON_SIZE + 8,
            height=Sizing.BTN_ICON_SIZE + 8,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=18),
            fg_color=Colors.BG_ELEVATED,
            hover_color=Colors.BG_BORDER,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=Sizing.RADIUS_PILL,
            border_width=1,
            border_color=Colors.BG_BORDER,
            command=self._on_mic_click,
        )
        self._mic_btn.grid(row=0, column=0, padx=(16, 8), pady=16)

        # ── Text input (center) ───────────────────────────────
        input_frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_ELEVATED,
            corner_radius=Sizing.INPUT_RADIUS,
            border_width=1,
            border_color=Colors.BG_BORDER,
        )
        input_frame.grid(row=0, column=1, sticky="ew", pady=16)

        self._text_var = tk.StringVar()
        self._entry = ctk.CTkEntry(
            input_frame,
            textvariable=self._text_var,
            placeholder_text="Message Drex...  (Enter to send)",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD),
            fg_color="transparent",
            border_width=0,
            text_color=Colors.TEXT_PRIMARY,
            placeholder_text_color=Colors.TEXT_MUTED,
            height=Sizing.INPUT_HEIGHT - 4,
        )
        self._entry.pack(fill="x", padx=16, pady=0)

        # Keyboard bindings
        self._entry.bind("<Return>",       self._on_enter)
        self._entry.bind("<Shift-Return>", self._on_shift_enter)
        self._entry.bind("<KP_Enter>",     self._on_enter)
        self._entry.bind("<FocusIn>",      self._on_focus_in)
        self._entry.bind("<FocusOut>",     self._on_focus_out)

        # ── Send button (right) ───────────────────────────────
        self._send_btn = ctk.CTkButton(
            self,
            text="↑",
            width=Sizing.BTN_ICON_SIZE + 8,
            height=Sizing.BTN_ICON_SIZE + 8,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=20, weight="bold"),
            fg_color=Colors.ACCENT,
            hover_color=Colors.BTN_PRIMARY_HOVER,
            text_color=Colors.BG_DARK,
            corner_radius=Sizing.RADIUS_PILL,
            command=self._on_send_click,
        )
        self._send_btn.grid(row=0, column=2, padx=(8, 16), pady=16)

        # Focus the input field immediately
        self.after(100, self._entry.focus_set)

    # ── Event Handlers ────────────────────────────────────────

    def _on_enter(self, event=None):
        """Send on Enter key."""
        self._on_send_click()
        return "break"  # Prevent default newline

    def _on_shift_enter(self, event=None):
        """Shift+Enter does nothing special in single-line mode."""
        return None

    def _on_send_click(self):
        """Submit the current text."""
        if self._is_disabled:
            return
        text = self._text_var.get().strip()
        if not text:
            return
        self._text_var.set("")
        self.on_submit(text)

    def _on_mic_click(self):
        """Toggle voice listening."""
        if self._is_disabled:
            return
        self.on_voice_toggle()

    def _on_focus_in(self, event=None):
        """Highlight border when input is focused."""
        self._entry.master.configure(border_color=Colors.ACCENT_DIM)

    def _on_focus_out(self, event=None):
        """Reset border when input loses focus."""
        self._entry.master.configure(border_color=Colors.BG_BORDER)

    # ── Public Methods ────────────────────────────────────────

    def set_listening(self, is_listening: bool):
        """Update mic button appearance for listening state."""
        self._is_listening = is_listening
        if is_listening:
            self._mic_btn.configure(
                text="⏹",
                fg_color=Colors.LISTENING,
                hover_color="#CC2244",
                text_color=Colors.TEXT_PRIMARY,
                border_color=Colors.LISTENING,
            )
            self._entry.configure(placeholder_text="Listening... speak now 🎤")
        else:
            self._mic_btn.configure(
                text="🎤",
                fg_color=Colors.BG_ELEVATED,
                hover_color=Colors.BG_BORDER,
                text_color=Colors.TEXT_SECONDARY,
                border_color=Colors.BG_BORDER,
            )
            self._entry.configure(placeholder_text="Message Drex...  (Enter to send)")

    def set_processing(self, is_processing: bool):
        """Disable input while Drex is processing."""
        self._is_disabled = is_processing
        state = "disabled" if is_processing else "normal"
        self._entry.configure(state=state)
        self._send_btn.configure(
            state=state,
            fg_color=Colors.TEXT_MUTED if is_processing else Colors.ACCENT,
        )

    def insert_text(self, text: str):
        """Programmatically insert text into the input field."""
        self._text_var.set(text)
        self._entry.focus_set()
        # Move cursor to end
        self._entry.icursor("end")

    def focus(self):
        """Focus the text input."""
        self._entry.focus_set()
