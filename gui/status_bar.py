# ============================================================
#  DREX - AI Desktop Assistant
#  gui/status_bar.py  —  Top Status Bar
#
#  Shows current Drex state + AI status + session stats.
# ============================================================

import customtkinter as ctk
from gui.theme import Colors, Fonts, Sizing, Status
from gui.widgets import StatusDot
from utils.logger import logger


class StatusBar(ctk.CTkFrame):
    """Header bar showing Drex's current state."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_PANEL,
            corner_radius=0,
            height=Sizing.STATUS_HEIGHT + 20,
            border_width=1,
            border_color=Colors.BG_BORDER,
            **kwargs
        )
        self.grid_propagate(False)
        self._current_status = Status.IDLE
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        # ── Left: Status dot + label ──────────────────────────
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=16, pady=8)

        self._dot = StatusDot(left)
        self._dot.pack(side="left", padx=(0, 6))

        self._status_label = ctk.CTkLabel(
            left,
            text="Ready",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_SECONDARY,
        )
        self._status_label.pack(side="left")

        # ── Center: Session info ──────────────────────────────
        self._center_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
        )
        self._center_label.grid(row=0, column=1, pady=8)

        # ── Right: AI model indicator ─────────────────────────
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=16, pady=8)

        self._model_label = ctk.CTkLabel(
            right,
            text="No AI configured",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
        )
        self._model_label.pack(side="right")

    # ── Public API ────────────────────────────────────────────

    def set_status(self, state: str):
        """
        Update the displayed status.
        state: one of Status.IDLE/LISTENING/PROCESSING/SPEAKING/ERROR
        """
        if state not in Status.DISPLAY:
            return

        label, color, icon = Status.DISPLAY[state]
        self._current_status = state
        self._status_label.configure(text=f"{icon}  {label}", text_color=color)

        pulse = state in (Status.LISTENING, Status.PROCESSING)
        self._dot.set_state(color, pulse=pulse)

    def set_session_info(self, message_count: int, session_id: str = ""):
        """Update the center session info display."""
        text = f"{message_count} messages"
        if session_id:
            text += f"  ·  {session_id[:12]}"
        self._center_label.configure(text=text)

    def set_ai_model(self, model_text: str):
        """Update the AI model indicator on the right."""
        self._model_label.configure(text=model_text, text_color=Colors.TEXT_SECONDARY)

    @property
    def current_status(self) -> str:
        return self._current_status
