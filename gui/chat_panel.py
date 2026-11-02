# ============================================================
#  DREX - AI Desktop Assistant
#  gui/chat_panel.py - Chat conversation display
#
#  Wide message area with:
#    - Left-aligned avatar + bubble for assistant
#    - Right-aligned bubble (accent color) for user
#    - Timestamps, copy / retry / regenerate actions
#    - Streaming typing indicator
#    - Welcome screen when empty
#
#  SCROLL DESIGN NOTES (read this before touching scroll code again):
#
#  CTkScrollableFrame wraps a raw tk.Canvas (self.scroll_frame._parent_canvas)
#  with an embedded frame window. Its scrollregion is normally kept in sync
#  by customtkinter's own internal <Configure> binding. That works fine for
#  simple/static content, but breaks down here because MessageBubble uses
#  MarkdownMessage, which resizes ASYNCHRONOUSLY over several Tk idle
#  cycles after being packed (see widgets.py _fit_height). If a scroll
#  happens to run while customtkinter's internal bookkeeping is mid-sync,
#  the scrollregion can be momentarily stale (too tall or too short),
#  which is what produces "cuts off the top message" / "gap below the
#  last message" symptoms.
#
#  To make this reliable without depending on any single well-timed call,
#  THREE independent, redundant mechanisms all funnel into one function
#  (_robust_scroll_to_bottom):
#    1. Called directly after any structural change (add_message, typing
#       indicator, streaming start/flush/finalize).
#    2. Bound to <Configure> on messages_container -- fires on literally
#       any height change of the message list, from any cause.
#    3. A repeating series of delayed re-checks (0 / 60 / 150 / 300 / 500ms)
#       after any "content changed" event, so even if customtkinter's
#       internal handler runs after ours and overwrites the scrollregion,
#       we get the last word.
#
#  Every one of these calls explicitly recomputes scrollregion from
#  canvas.bbox("all") right before moving the viewport -- never trusts
#  whatever customtkinter last set it to.
# ============================================================

import customtkinter as ctk
from datetime import datetime
import time
from typing import Optional, Callable

from gui.theme import Colors, Fonts, Sizing, Spacing, Icons
from gui.widgets import MessageBubble, TypingIndicator, StreamingLabel
from utils.logger import logger


class ChatPanel(ctk.CTkFrame):
    """Scrollable chat area — newest message at the bottom."""

    # Delays (ms) for the redundant post-change scroll re-checks.
    _SCROLL_RECHECK_DELAYS = (0, 60, 150, 300, 500)

    def __init__(
        self,
        parent,
        on_suggestion: Optional[Callable[[str], None]] = None,
        on_regenerate: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(
            parent,
            fg_color=Colors.BG_BASE,
            corner_radius=0,
            **kwargs,
        )

        self.on_suggestion = on_suggestion
        self.on_regenerate = on_regenerate

        self._message_count = 0
        self._typing_indicator: Optional[TypingIndicator] = None
        self._streaming_label: Optional[StreamingLabel] = None
        self._is_typing = False
        self._welcome_widget = None

        # Streaming token buffering (batches rapid tokens instead of
        # re-rendering on every single one).
        self._token_buffer = ""
        self._last_flush = 0.0
        self._flush_job = None

        # Scroll bookkeeping
        self._recheck_jobs = []
        self._last_seen_height = -1

        self._build()
        self._show_welcome()

    # -----------------------------------------------------
    #  Layout
    # -----------------------------------------------------

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=Colors.BG_BASE,
            corner_radius=0,
            scrollbar_button_color=Colors.BG_OVERLAY,
            scrollbar_button_hover_color=Colors.BORDER_LIGHT,
        )
        self.scroll_frame.grid(row=0, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self.messages_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.messages_container.pack(
            fill="x",
            expand=False,
            anchor="n",
            padx=Sizing.CHAT_PADDING,
            pady=Sizing.CHAT_PADDING,
        )

        # Mechanism #2: catch-all resize watcher. Fires on ANY height
        # change of the message list, no matter what caused it.
        self.messages_container.bind("<Configure>", self._on_content_resize)

    # -----------------------------------------------------
    #  Welcome
    # -----------------------------------------------------

    def _show_welcome(self):
        self._welcome_widget = ctk.CTkFrame(
            self.messages_container, fg_color="transparent"
        )
        self._welcome_widget.pack(fill="both", expand=True, pady=(80, 40))

        ctk.CTkLabel(
            self._welcome_widget,
            text=Icons.SPARKLE,
            width=64,
            height=64,
            font=ctk.CTkFont(family=Fonts.ICON, size=30),
            fg_color=Colors.ACCENT,
            text_color=Colors.TEXT_INVERSE,
            corner_radius=32,
        ).pack(pady=(0, Spacing.LG))

        ctk.CTkLabel(
            self._welcome_widget,
            text="How can I help you today?",
            font=ctk.CTkFont(family=Fonts.DISPLAY, size=Fonts.XXL, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(pady=(0, Spacing.SM))

        ctk.CTkLabel(
            self._welcome_widget,
            text="Ask DREX to launch apps, search the web, or answer questions.",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD),
            text_color=Colors.TEXT_SECONDARY,
        ).pack(pady=(0, Spacing.XL))

        grid = ctk.CTkFrame(self._welcome_widget, fg_color="transparent")
        grid.pack(pady=(0, 0))
        grid.grid_columnconfigure((0, 1), weight=1, uniform="cards")

        suggestions = [
            (Icons.SEARCH,  "Open Chrome",       "Launch a common application",
             "Open Chrome"),
            (Icons.CHAT,    "Search YouTube",    "Find music, videos, tutorials",
             "Search YouTube for lofi music"),
            (Icons.DOWNLOAD, "Take a screenshot", "Capture what's on your screen",
             "Take a screenshot"),
            (Icons.SPARKLE, "What can you do?",  "Explore DREX capabilities",
             "What can you do?"),
        ]

        for i, (icon, title, subtitle, prompt) in enumerate(suggestions):
            card = self._suggestion_card(grid, icon, title, subtitle, prompt)
            card.grid(row=i // 2, column=i % 2,
                      padx=Spacing.SM, pady=Spacing.SM, sticky="nsew")

    def _suggestion_card(self, parent, icon, title, subtitle, prompt):
        card = ctk.CTkFrame(
            parent,
            fg_color=Colors.BG_ELEVATED,
            border_width=1,
            border_color=Colors.BORDER,
            corner_radius=Sizing.RADIUS_LG,
            width=280,
            height=84,
        )
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)

        icon_lbl = ctk.CTkLabel(
            card,
            text=icon,
            width=28,
            font=ctk.CTkFont(family=Fonts.ICON, size=16),
            text_color=Colors.ACCENT,
        )
        icon_lbl.grid(row=0, column=0, rowspan=2, sticky="n",
                      padx=(Spacing.MD, Spacing.SM), pady=(Spacing.MD, 0))

        title_lbl = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        )
        title_lbl.grid(row=0, column=1, sticky="w", padx=(0, Spacing.MD),
                       pady=(Spacing.MD, 0))

        sub_lbl = ctk.CTkLabel(
            card,
            text=subtitle,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        )
        sub_lbl.grid(row=1, column=1, sticky="w", padx=(0, Spacing.MD),
                     pady=(0, Spacing.MD))

        widgets = [card, icon_lbl, title_lbl, sub_lbl]

        def _enter(_e=None):
            card.configure(fg_color=Colors.BG_OVERLAY, border_color=Colors.BORDER_LIGHT)

        def _leave(_e=None):
            card.configure(fg_color=Colors.BG_ELEVATED, border_color=Colors.BORDER)

        def _click(_e=None):
            if self.on_suggestion:
                self.on_suggestion(prompt)

        for w in widgets:
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
            w.bind("<Button-1>", _click)
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass
        return card

    def _dismiss_welcome(self):
        if self._welcome_widget is not None:
            self._welcome_widget.destroy()
            self._welcome_widget = None

    # -----------------------------------------------------
    #  Message API
    # -----------------------------------------------------

    def add_message(self, role: str, content: str,
                    provider: Optional[str] = None,
                    timestamp: Optional[str] = None):
        self._dismiss_welcome()
        self._hide_typing_indicator()

        self._message_count += 1
        ts = timestamp or datetime.now().strftime("%I:%M %p")

        bubble = MessageBubble(
            self.messages_container,
            role=role,
            content=content,
            timestamp=ts,
            provider=provider or None,
            on_regenerate=self._on_regenerate_callback,
        )
        bubble.pack(fill="x", pady=(8, 10))
        self._content_changed()
        return bubble

    def _on_regenerate_callback(self, _content):
        """Forward regenerate request to the app layer."""
        if self.on_regenerate:
            self.on_regenerate()

    # Legacy aliases used by app.py
    def show_typing(self):
        self.show_typing_indicator()

    def hide_typing(self):
        self._hide_typing_indicator()

    def show_streaming(self, provider: str = ""):
        self.start_streaming()

    def update_streaming(self, token: str):
        self.append_stream_token(token)

    def finish_streaming(self, provider: str = "", final_text: str = ""):
        self.finalize_streaming(provider=provider or None, final_text=final_text)

    # -----------------------------------------------------
    #  Typing / streaming
    # -----------------------------------------------------

    def show_typing_indicator(self):
        if self._is_typing:
            return
        self._is_typing = True
        self._dismiss_welcome()

        self._typing_indicator = TypingIndicator(self.messages_container)
        self._typing_indicator.pack(fill="x", pady=(4, 4))
        self._content_changed()

    def _hide_typing_indicator(self):
        if self._typing_indicator is not None:
            try:
                self._typing_indicator.destroy()
            except Exception:
                pass
            self._typing_indicator = None
        self._is_typing = False

    def start_streaming(self):
        if self._streaming_label is not None:
            return
        self._dismiss_welcome()
        self._hide_typing_indicator()

        self._token_buffer = ""
        self._last_flush = time.time()

        self._streaming_label = StreamingLabel(
            self.messages_container,
            on_regenerate=(lambda c: self._on_regenerate_callback(c)) if self.on_regenerate else None,
            on_height_settled=self._content_changed,
        )
        self._streaming_label.pack(fill="x", pady=(8, 10))
        self._is_typing = True
        self._content_changed()

    def append_stream_token(self, token: str):
        if self._streaming_label is None:
            logger.debug("Late stream token ignored.")
            return

        self._token_buffer += token
        now = time.time()

        if len(self._token_buffer) >= 8 or (now - self._last_flush) > 0.04:
            self._flush_tokens()
        else:
            if self._flush_job:
                self.after_cancel(self._flush_job)
            self._flush_job = self.after(50, self._flush_tokens)

    def _flush_tokens(self):
        if not self._token_buffer or self._streaming_label is None:
            return
        try:
            self._streaming_label.append(self._token_buffer)
        except Exception as e:
            logger.debug("Stream flush failed: {}", e)
        self._token_buffer = ""
        self._last_flush = time.time()
        if self._flush_job:
            self.after_cancel(self._flush_job)
            self._flush_job = None
        self._content_changed()

    def finalize_streaming(self, provider: Optional[str] = None, final_text: str = ""):
        if self._streaming_label is None:
            return

        self._flush_tokens()

        try:
            self._streaming_label.finalize(provider=provider, final_text=final_text)
        except Exception as e:
            logger.debug("Streaming finalize failed: {}", e)
            try:
                self._streaming_label.destroy()
            except Exception:
                pass

        self._streaming_label = None
        self._is_typing = False
        self._content_changed()

    def cancel_streaming(self):
        """Discard an active streaming bubble without rendering it."""
        if self._flush_job:
            self.after_cancel(self._flush_job)
            self._flush_job = None
        self._token_buffer = ""
        if self._streaming_label is not None:
            try:
                self._streaming_label.destroy()
            except Exception:
                pass
            self._streaming_label = None
        self._is_typing = False

    # -----------------------------------------------------
    #  Utilities
    # -----------------------------------------------------

    def clear_messages(self):
        for widget in self.messages_container.winfo_children():
            widget.destroy()
        self._message_count = 0
        self._is_typing = False
        self._typing_indicator = None
        self._streaming_label = None
        self._token_buffer = ""
        self._last_flush = 0.0
        if self._flush_job:
            self.after_cancel(self._flush_job)
            self._flush_job = None
        for job in self._recheck_jobs:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._recheck_jobs = []
        self._last_seen_height = -1
        self._show_welcome()
        self._scroll_to_top()

    # -----------------------------------------------------
    #  Scroll — see module docstring for the overall design
    # -----------------------------------------------------

    def _on_content_resize(self, event):
        """Mechanism #2: fires on any height change of the message list."""
        if event.height == self._last_seen_height:
            return
        self._last_seen_height = event.height
        self._content_changed()

    def _content_changed(self):
        """Central entry point: call this any time the message list's
        content changed in a way that might require scrolling.

        Triggers an immediate scroll attempt plus a staggered series of
        re-checks (mechanism #3), so that even if MarkdownMessage's async
        height-fitting or customtkinter's own internal scrollregion sync
        finishes later, we still land in the right place afterward.
        """
        for job in self._recheck_jobs:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._recheck_jobs = []

        for delay in self._SCROLL_RECHECK_DELAYS:
            job = self.after(delay, self._robust_scroll_to_bottom)
            self._recheck_jobs.append(job)

    def _robust_scroll_to_bottom(self):
        """The one function everything funnels into. Always recomputes
        scrollregion from the real, current content bounds before moving
        the viewport -- never trusts whatever customtkinter last set
        scrollregion to."""
        try:
            self.messages_container.update_idletasks()
            self.scroll_frame.update_idletasks()

            canvas = self.scroll_frame._parent_canvas
            canvas.update_idletasks()

            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)

            canvas.yview_moveto(1.0)
        except Exception as e:
            logger.debug(f"Auto-scroll failed: {e}")

    # Kept for any external caller still using the old name/signature
    # (e.g. app.py calling chat_panel._scroll_to_bottom(force=True)).
    def _scroll_to_bottom(self, force: bool = False):
        self._robust_scroll_to_bottom()

    def _scroll_to_top(self):
        try:
            canvas = self.scroll_frame._parent_canvas
            canvas.update_idletasks()
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)
            canvas.yview_moveto(0.0)
        except Exception:
            pass

    @property
    def message_count(self) -> int:
        return self._message_count

    def get_last_user_message(self) -> str:
        """Return the last user message content for regenerate support."""
        for child in reversed(self.messages_container.winfo_children()):
            if isinstance(child, MessageBubble) and child.role == "user":
                return child.content
        return ""