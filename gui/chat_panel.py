# ============================================================
#  DREX - AI Desktop Assistant
#  gui/chat_panel.py  —  Chat Message Display
#
#  WHAT IT DOES:
#  The main chat area showing conversation history.
#  Handles:
#  - Rendering user and AI messages as styled bubbles
#  - Showing typing indicator while AI is processing
#  - Auto-scrolling to the latest message
#  - Clearing chat history
#  - Welcome screen on first launch
# ============================================================

import tkinter as tk
import customtkinter as ctk
from datetime import datetime
from typing import Optional
from gui.theme import Colors, Fonts, Sizing, Spacing
from gui.widgets import MessageBubble, TypingIndicator
from utils.logger import logger


class ChatPanel(ctk.CTkFrame):
    """
    Scrollable chat message display area.
    Messages appear bottom-up, newest at the bottom.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_DARK,
            corner_radius=0,
            **kwargs
        )

        self._message_count = 0
        self._typing_indicator: Optional[TypingIndicator] = None
        self._is_typing = False

        self._build()
        self._show_welcome()

        logger.debug("ChatPanel initialized")

    def _build(self):
        """Build the scrollable chat container."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Scrollable frame — this holds all messages
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=Colors.BG_DARK,
            corner_radius=0,
            scrollbar_button_color=Colors.BG_BORDER,
            scrollbar_button_hover_color=Colors.BG_ELEVATED,
        )
        self.scroll_frame.grid(row=0, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Messages are packed into this inner frame
        self.messages_container = ctk.CTkFrame(
            self.scroll_frame,
            fg_color="transparent"
        )
        self.messages_container.pack(
            fill="both",
            expand=True,
            padx=Sizing.CHAT_PADDING,
            pady=Sizing.CHAT_PADDING
        )

    def _show_welcome(self):
        """Display the welcome screen before any messages."""
        self._welcome_frame = ctk.CTkFrame(
            self.messages_container,
            fg_color="transparent"
        )
        self._welcome_frame.pack(fill="both", expand=True, pady=60)

        # Large glowing icon
        ctk.CTkLabel(
            self._welcome_frame,
            text="◈",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=64),
            text_color=Colors.ACCENT,
        ).pack()

        ctk.CTkLabel(
            self._welcome_frame,
            text="Drex",
            font=ctk.CTkFont(family=Fonts.DISPLAY, size=Fonts.HERO, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(pady=(8, 0))

        ctk.CTkLabel(
            self._welcome_frame,
            text="AI Desktop Assistant",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.LG),
            text_color=Colors.TEXT_SECONDARY,
        ).pack(pady=(4, 24))

        # Quick action hints
        hints_frame = ctk.CTkFrame(
            self._welcome_frame,
            fg_color=Colors.BG_CARD,
            corner_radius=Sizing.RADIUS_XL,
            border_width=1,
            border_color=Colors.BG_BORDER,
        )
        hints_frame.pack(padx=80)

        hints = [
            ("🚀", "Open Chrome",            "Open any app instantly"),
            ("🔍", "Search for Python tips",  "Search the web by voice"),
            ("📸", "Take a screenshot",       "Control your PC hands-free"),
            ("🤖", "What is machine learning?","Get AI answers on anything"),
        ]

        for icon, example, desc in hints:
            row = ctk.CTkFrame(hints_frame, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=8)

            ctk.CTkLabel(
                row,
                text=icon,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.LG),
                width=32,
            ).pack(side="left")

            text_col = ctk.CTkFrame(row, fg_color="transparent")
            text_col.pack(side="left", padx=12, fill="x", expand=True)

            ctk.CTkLabel(
                text_col,
                text=f'"{example}"',
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
                text_color=Colors.ACCENT,
                anchor="w",
            ).pack(fill="x")

            ctk.CTkLabel(
                text_col,
                text=desc,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            ).pack(fill="x")

        ctk.CTkLabel(
            self._welcome_frame,
            text="Type below or press the mic button to speak  🎤",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_MUTED,
        ).pack(pady=(24, 0))

    def _hide_welcome(self):
        """Remove the welcome screen when first message arrives."""
        if hasattr(self, '_welcome_frame') and self._welcome_frame:
            self._welcome_frame.destroy()
            self._welcome_frame = None

    # ── Public API ────────────────────────────────────────────

    def add_message(self, role: str, content: str):
        """
        Add a new message bubble to the chat.

        Args:
            role:    "user" | "assistant"
            content: Message text
        """
        # Remove welcome screen on first message
        if self._message_count == 0:
            self._hide_welcome()

        # Remove typing indicator before adding AI response
        if role == "assistant" and self._is_typing:
            self.hide_typing()

        self._message_count += 1
        timestamp = datetime.now().strftime("%I:%M %p")

        bubble = MessageBubble(
            self.messages_container,
            role=role,
            content=content,
            timestamp=timestamp,
        )
        bubble.pack(fill="x", pady=(4, 4))

        # Scroll to bottom after a short delay (let widget render first)
        self.after(50, self._scroll_to_bottom)

        logger.debug(f"Message added [{role}]: {content[:40]}...")

    def show_typing(self):
        """Show the 'Drex is thinking...' indicator."""
        if self._is_typing:
            return
        self._is_typing = True
        self._hide_welcome()

        self._typing_indicator = TypingIndicator(self.messages_container)
        self._typing_indicator.pack(fill="x", pady=(4, 4))
        self._typing_indicator.start()
        self.after(50, self._scroll_to_bottom)

    def hide_typing(self):
        """Remove the typing indicator."""
        if self._typing_indicator:
            self._typing_indicator.stop()
            self._typing_indicator.destroy()
            self._typing_indicator = None
        self._is_typing = False

    def clear_messages(self):
        """Remove all messages from the chat."""
        for widget in self.messages_container.winfo_children():
            widget.destroy()
        self._message_count = 0
        self._is_typing = False
        self._typing_indicator = None
        self._show_welcome()
        logger.info("Chat cleared")

    def _scroll_to_bottom(self):
        """Scroll the chat view to show the latest message."""
        try:
            self.scroll_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    @property
    def message_count(self) -> int:
        return self._message_count
