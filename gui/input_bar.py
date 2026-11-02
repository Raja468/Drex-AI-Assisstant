# ============================================================
#  DREX - AI Desktop Assistant
#  gui/input_bar.py - Premium Input Bar
#
#  The most polished component in the UI. A single rounded
#  container that hosts:
#    - Multiline auto-expanding textbox
#    - Attach button
#    - Model chip
#    - Mic button
#    - Send button (accent, always visible when text present)
# ============================================================

import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional

from gui.theme import Colors, Fonts, Sizing, Spacing, Icons
from utils.logger import logger


class InputBar(ctk.CTkFrame):
    """
    Modern input bar with rounded container and auto-expanding textbox.
    Enter to send, Shift+Enter for newline.
    """

    LINE_HEIGHT = 22   # approximate line height in pixels for auto-expand
    MIN_LINES   = 1
    MAX_LINES   = 6

    def __init__(
        self,
        parent,
        on_submit: Callable[[str], None],
        on_voice_toggle: Callable[[], None],
        on_attach: Optional[Callable[[], None]] = None,
        on_model_click: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(
            parent,
            fg_color=Colors.BG_BASE,
            corner_radius=0,
            border_width=0,
            **kwargs,
        )

        self.on_submit       = on_submit
        self.on_voice_toggle = on_voice_toggle
        self.on_attach       = on_attach
        self.on_model_click  = on_model_click

        self._is_listening = False
        self._is_disabled  = False

        self._build()

    # -----------------------------------------------------
    #  Layout
    # -----------------------------------------------------

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # Outer padding so the pill floats above the bottom edge.
        # Centered and width-capped so it doesn't stretch edge-to-edge on wide windows.
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.grid(row=0, column=0,
                     padx=Spacing.XXL, pady=(Spacing.SM, Spacing.LG))
        wrapper.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ----- Rounded container -----
        self._container = ctk.CTkFrame(
            wrapper,
            fg_color=Colors.BG_ELEVATED,
            corner_radius=Sizing.INPUT_RADIUS,
            border_width=1,
            border_color=Colors.BORDER,
        )
        self._container.grid(row=0, column=0, sticky="ew")
        self._container.grid_columnconfigure(0, weight=1)

        # Row 0: multiline textbox
        self._text = tk.Text(
            self._container,
            height=1,
            wrap="word",
            bd=0,
            highlightthickness=0,
            bg=Colors.BG_ELEVATED,
            fg=Colors.TEXT_PRIMARY,
            insertbackground=Colors.ACCENT,
            selectbackground=Colors.ACCENT_SUBTLE,
            selectforeground=Colors.TEXT_PRIMARY,
            font=(Fonts.PRIMARY, Fonts.MD),
            padx=4,
            pady=2,
            spacing1=2,
            spacing3=2,
            undo=True,
            cursor="xterm",
        )
        self._text.grid(row=0, column=0, sticky="ew",
                        padx=(Spacing.XL, Spacing.XL),
                        pady=(Spacing.LG, Spacing.SM))

        # Placeholder handling
        self._placeholder = "Message DREX..."
        self._show_placeholder()
        self._text.bind("<FocusIn>",   self._on_focus_in)
        self._text.bind("<FocusOut>",  self._on_focus_out)
        self._text.bind("<KeyRelease>", self._on_key_release)
        self._text.bind("<Return>",     self._on_return)
        self._text.bind("<Shift-Return>", self._on_shift_return)

        # Row 1: action strip
        actions = ctk.CTkFrame(self._container, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew",
                     padx=Spacing.SM, pady=(0, Spacing.SM))
        actions.grid_columnconfigure(1, weight=1)

        # Left cluster: attach + model chip
        left = ctk.CTkFrame(actions, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        self._attach_btn = self._icon_button(
            left, Icons.ATTACH, self._on_attach_click)
        self._attach_btn.pack(side="left", padx=(2, 2))

        self._model_chip = ctk.CTkButton(
            left,
            text="Auto",
            width=0,
            height=30,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            fg_color="transparent",
            hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=Sizing.RADIUS_PILL,
            command=self._on_model_click,
        )
        self._model_chip.pack(side="left", padx=(2, 0))

        # Right cluster: mic + send
        right = ctk.CTkFrame(actions, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e")

        self._mic_btn = self._icon_button(
            right, Icons.MIC, self._on_mic_click)
        self._mic_btn.pack(side="left", padx=(0, Spacing.SM))

        self._send_btn = ctk.CTkButton(
            right,
            text=Icons.SEND,
            width=Sizing.BTN_ICON_SIZE,
            height=Sizing.BTN_ICON_SIZE,
            font=ctk.CTkFont(family=Fonts.ICON, size=17),
            fg_color=Colors.BG_OVERLAY,
            hover_color=Colors.BG_PRESSED,
            text_color=Colors.TEXT_MUTED,
            corner_radius=Sizing.RADIUS_PILL,
            command=self._submit,
        )
        self._send_btn.pack(side="left")
        self._send_enabled = False

        # Hint row (kept intentionally subtle)
        self._hint = ctk.CTkLabel(
            wrapper,
            text="Enter to send    Shift + Enter for a new line",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_FAINT,
        )
        self._hint.grid(row=1, column=0, pady=(Spacing.SM, 0))

    def _icon_button(self, parent, glyph, command, size=16):
        return ctk.CTkButton(
            parent,
            text=glyph,
            width=Sizing.BTN_ICON_SIZE,
            height=Sizing.BTN_ICON_SIZE,
            font=ctk.CTkFont(family=Fonts.ICON, size=size),
            fg_color="transparent",
            hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=Sizing.RADIUS_PILL,
            command=command,
        )

    def _refresh_send_state(self):
        """Send button lights up (accent) only when there's text to send."""
        has_text = bool(self._get_raw_text().strip())
        if self._is_disabled:
            return
        if has_text and not self._send_enabled:
            self._send_enabled = True
            self._send_btn.configure(
                fg_color=Colors.ACCENT,
                hover_color=Colors.ACCENT_HOVER,
                text_color=Colors.TEXT_INVERSE,
            )
        elif not has_text and self._send_enabled:
            self._send_enabled = False
            self._send_btn.configure(
                fg_color=Colors.BG_OVERLAY,
                hover_color=Colors.BG_PRESSED,
                text_color=Colors.TEXT_MUTED,
            )

    # -----------------------------------------------------
    #  Placeholder
    # -----------------------------------------------------

    def _show_placeholder(self):
        self._text.configure(fg=Colors.TEXT_MUTED)
        self._text.delete("1.0", "end")
        self._text.insert("1.0", self._placeholder)
        self._placeholder_visible = True

    def _hide_placeholder(self):
        if getattr(self, "_placeholder_visible", False):
            self._text.delete("1.0", "end")
            self._text.configure(fg=Colors.TEXT_PRIMARY)
            self._placeholder_visible = False

    def _on_focus_in(self, _event=None):
        if getattr(self, "_placeholder_visible", False):
            self._hide_placeholder()
        # Focus ring: accent border while typing
        try:
            self._container.configure(border_color=Colors.BORDER_FOCUS)
        except Exception:
            pass

    def _on_focus_out(self, _event=None):
        if not self._get_raw_text():
            self._show_placeholder()
        try:
            self._container.configure(border_color=Colors.BORDER)
        except Exception:
            pass

    # -----------------------------------------------------
    #  Auto-expand
    # -----------------------------------------------------

    def _on_key_release(self, _event=None):
        self._adjust_height()
        self._refresh_send_state()

    def _adjust_height(self):
        content = self._get_raw_text()
        if not content:
            self._text.configure(height=self.MIN_LINES)
            return
        lines = content.count("\n") + 1
        # Add wrap estimate: rough characters-per-line based on widget width
        try:
            self._text.update_idletasks()
            widget_w = max(1, self._text.winfo_width())
            approx_chars = max(20, widget_w // 8)
        except Exception:
            approx_chars = 80
        wrapped = 0
        for line in content.split("\n"):
            wrapped += max(1, (len(line) // approx_chars) + (1 if len(line) % approx_chars else 0))
        rows = min(self.MAX_LINES, max(self.MIN_LINES, wrapped))
        self._text.configure(height=rows)

    # -----------------------------------------------------
    #  Submission
    # -----------------------------------------------------

    def _on_return(self, _event=None):
        if self._is_disabled:
            return "break"
        self._submit()
        return "break"

    def _on_shift_return(self, _event=None):
        # Let default behavior insert newline
        self._adjust_height()
        return None

    def _get_raw_text(self) -> str:
        if getattr(self, "_placeholder_visible", False):
            return ""
        return self._text.get("1.0", "end-1c")

    def _submit(self):
        text = self._get_raw_text().strip()
        if not text or self._is_disabled:
            return
        self._text.delete("1.0", "end")
        self._adjust_height()
        self._refresh_send_state()
        try:
            self.on_submit(text)
        except Exception as e:
            # Never swallow submit failures silently — a handler crash
            # here previously killed sends with no trace in the logs.
            logger.error(f"Submit handler failed: {e}")

    # -----------------------------------------------------
    #  Handlers
    # -----------------------------------------------------

    def _on_attach_click(self):
        if self.on_attach:
            self.on_attach()

    def _on_mic_click(self):
        if self.on_voice_toggle:
            self.on_voice_toggle()

    def _on_model_click(self):
        if self.on_model_click:
            self.on_model_click()

    # -----------------------------------------------------
    #  Public API
    # -----------------------------------------------------

    def set_listening(self, is_listening: bool):
        self._is_listening = is_listening
        if is_listening:
            self._mic_btn.configure(
                text=Icons.STOP,
                fg_color=Colors.LISTENING,
                hover_color="#DC2C3A",
                text_color=Colors.TEXT_PRIMARY,
            )
            self._placeholder = "Listening..."
        else:
            self._mic_btn.configure(
                text=Icons.MIC,
                fg_color="transparent",
                hover_color=Colors.BG_OVERLAY,
                text_color=Colors.TEXT_SECONDARY,
            )
            self._placeholder = "Message DREX..."
        if not self._get_raw_text():
            self._show_placeholder()

    def set_processing(self, is_processing: bool):
        self._is_disabled = is_processing
        state = "disabled" if is_processing else "normal"
        self._text.configure(state=state)
        if is_processing:
            self._send_enabled = False
            self._send_btn.configure(
                state="disabled",
                fg_color=Colors.BG_OVERLAY,
                text_color=Colors.TEXT_FAINT,
            )
        else:
            self._send_btn.configure(state="normal")
            # Restore whatever state the current text implies
            self._refresh_send_state()

    def set_model(self, model: str):
        self._model_chip.configure(text=model or "Auto")

    def insert_text(self, text: str):
        self._hide_placeholder()
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._text.focus_set()
        self._adjust_height()
        self._refresh_send_state()

    def focus(self):
        self._text.focus_set()
