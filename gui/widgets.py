# ============================================================
#  DREX - AI Desktop Assistant
#  gui/widgets.py - Reusable UI components
#
#  DESIGN NOTE (read before adding markdown/async rendering back):
#  This file deliberately uses simple, SYNCHRONOUS CTkLabel rendering
#  for message content. An earlier version used a tk.Text-based
#  MarkdownMessage widget that resized itself asynchronously over
#  several Tk idle cycles. That created a whole class of race
#  conditions with chat_panel.py's auto-scroll (cut-off top messages,
#  gaps between text and action buttons) because the scroll logic
#  could run before/after the async height was actually final, with
#  no reliable way to know which.
#
#  CTkLabel with wraplength computes its final size synchronously
#  within the same layout pass, so there is no "settling" period and
#  no race to have. If rich markdown rendering is wanted back, it
#  should be re-added carefully, with its own explicit, testable
#  "done resizing" signal -- not layered in silently.
# ============================================================

import re
import tkinter as tk
import customtkinter as ctk
from datetime import datetime
from typing import Optional, Callable

from gui.theme import Colors, Fonts, Sizing, Spacing, Icons
from utils.logger import logger


# =============================================================
#  INTERACTION HELPERS
# =============================================================

def add_press_feedback(button: ctk.CTkButton, base_color: str, press_color: str):
    """Give a CTkButton a subtle 'pressed' color dip."""
    def _press(_e=None):
        try:
            button.configure(fg_color=press_color)
        except Exception:
            pass

    def _release(_e=None):
        try:
            button.configure(fg_color=base_color)
        except Exception:
            pass

    button.bind("<ButtonPress-1>", _press, add="+")
    button.bind("<ButtonRelease-1>", _release, add="+")
    return button


def _mini_action_button(parent, glyph, cmd):
    return ctk.CTkButton(
        parent,
        text=glyph,
        width=28,
        height=28,
        font=ctk.CTkFont(family=Fonts.ICON, size=13),
        fg_color="transparent",
        hover_color=Colors.BG_OVERLAY,
        text_color=Colors.TEXT_MUTED,
        corner_radius=Sizing.RADIUS_SM,
        command=cmd,
    )


# =============================================================
#  MESSAGE BUBBLE
# =============================================================

class MessageBubble(ctk.CTkFrame):
    """
    Single chat message. User bubbles are right-aligned in the accent
    color; assistant messages render as plain wrapped text on the chat
    background (no bubble), with copy/regenerate actions below.

    Uses pack() internally for the assistant path so action buttons
    always sit directly under the text with zero gap, regardless of
    how many lines the text wraps to.
    """

    def __init__(
        self,
        parent,
        role: str,
        content: str,
        timestamp: Optional[str] = None,
        provider: Optional[str] = None,
        on_regenerate: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.role          = role
        self.content       = content
        self.timestamp     = timestamp or datetime.now().strftime("%I:%M %p")
        self.provider      = provider
        self.on_regenerate = on_regenerate

        if role == "user":
            self.bubble_color = Colors.USER_BG
            self.text_color   = Colors.USER_TEXT
            self.border_color = Colors.USER_BORDER
        else:
            self.bubble_color = Colors.DREX_BG
            self.text_color   = Colors.DREX_TEXT
            self.border_color = Colors.DREX_BORDER

        self._copy_action = None
        self._build()

    # -----------------------------------------------------

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew")
        row.grid_columnconfigure(1, weight=1)

        if self.role == "assistant":
            self._build_avatar(row, column=0)
            content_col = ctk.CTkFrame(row, fg_color="transparent")
            content_col.grid(row=0, column=1, sticky="ew", padx=(10, 60))
            self._build_content(content_col, side="w")
        else:
            content_col = ctk.CTkFrame(row, fg_color="transparent")
            content_col.grid(row=0, column=1, sticky="ew", padx=(60, 10))
            self._build_content(content_col, side="e")
            self._build_avatar(row, column=2)

    def _build_avatar(self, parent, column: int):
        if self.role == "assistant":
            bg, fg, char, sz = Colors.ACCENT, Colors.TEXT_INVERSE, Icons.SPARKLE, 15
        else:
            bg, fg, char, sz = Colors.BG_OVERLAY, Colors.TEXT_SECONDARY, Icons.USER, 14

        avatar = ctk.CTkLabel(
            parent,
            text=char,
            width=Sizing.CHAT_AVATAR_SIZE,
            height=Sizing.CHAT_AVATAR_SIZE,
            fg_color=bg,
            text_color=fg,
            font=ctk.CTkFont(family=Fonts.ICON, size=sz),
            corner_radius=Sizing.RADIUS_PILL,
        )
        avatar.grid(row=0, column=column, sticky="n", pady=1)

    def _build_content(self, parent, side: str):
        # Meta row: name + timestamp + provider
        meta = ctk.CTkFrame(parent, fg_color="transparent")
        meta.pack(fill="x", pady=(0, 4), anchor="w" if side == "w" else "e")

        name = "DREX" if self.role == "assistant" else "You"
        name_lbl = ctk.CTkLabel(
            meta,
            text=name,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        )
        ts_lbl = ctk.CTkLabel(
            meta,
            text=self.timestamp,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
        )

        if side == "w":
            name_lbl.pack(side="left")
            ts_lbl.pack(side="left", padx=(8, 0))
            if self.provider:
                ctk.CTkLabel(
                    meta,
                    text=f"· {self.provider}",
                    font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                    text_color=Colors.ACCENT_DIM,
                ).pack(side="left", padx=(6, 0))
        else:
            name_lbl.pack(side="right")
            ts_lbl.pack(side="right", padx=(0, 8))

        # Content
        if "```" in self.content:
            self._render_mixed(parent, side)
        else:
            self._render_content(parent, self.content, side)

        # Action row (assistant only) -- packed directly after the text,
        # so there is no possible gap regardless of wrap height.
        if self.role == "assistant":
            self._build_actions(parent)

    def _render_content(self, parent, text: str, side: str):
        """Render text directly -- no bubble frame for assistant."""
        if self.role == "assistant":
            lbl = ctk.CTkLabel(
                parent,
                text=text,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD),
                text_color=self.text_color,
                wraplength=Sizing.CHAT_MSG_MAX_W,
                justify="left",
                anchor="w",
            )
            lbl.pack(fill="x", anchor="w")
        else:
            bubble = ctk.CTkFrame(
                parent,
                fg_color=self.bubble_color,
                corner_radius=Sizing.RADIUS_LG,
                border_width=1,
                border_color=self.border_color,
            )
            bubble.pack(anchor="e" if side == "e" else "w")

            ctk.CTkLabel(
                bubble,
                text=text,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD),
                text_color=self.text_color,
                wraplength=Sizing.CHAT_MSG_MAX_W - 2 * Sizing.CHAT_MSG_PADDING,
                justify="left",
                anchor="w",
            ).pack(padx=Sizing.CHAT_MSG_PADDING,
                   pady=(Spacing.MD, Spacing.MD), fill="x")

    def _render_mixed(self, parent, side: str):
        parts = re.split(r"```(?:\w+)?\n?(.*?)```", self.content, flags=re.DOTALL)
        for i, part in enumerate(parts):
            if not part.strip():
                continue
            if i % 2 == 0:
                self._render_content(parent, part.strip(), side)
            else:
                block = CodeBlock(parent, code=part.strip())
                block.pack(fill="x", pady=(4, 0))

    def _build_actions(self, parent):
        strip = ctk.CTkFrame(parent, fg_color="transparent")
        strip.pack(fill="x", anchor="w", pady=(Spacing.SM, 0))

        def _regenerate():
            if self.on_regenerate:
                self.on_regenerate(self.content)

        self._copy_action = _mini_action_button(strip, Icons.COPY, self._copy)
        self._copy_action.pack(side="left", padx=(0, 2))
        _mini_action_button(strip, Icons.REFRESH, _regenerate).pack(side="left", padx=(0, 2))

    def _copy(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.content)
            if self._copy_action is not None:
                self._copy_action.configure(text=Icons.CHECK, text_color=Colors.SUCCESS)
                self.after(1400, lambda: self._copy_action.configure(
                    text=Icons.COPY, text_color=Colors.TEXT_MUTED))
        except Exception:
            pass


# =============================================================
#  STREAMING LABEL
# =============================================================

class StreamingLabel(ctk.CTkFrame):
    """Live-updating assistant message for token streaming.

    Renders as plain text on the chat background (no bubble).
    Sizing is synchronous (CTkLabel + wraplength), so
    on_height_settled fires immediately/reliably on every append and
    on finalize -- no async settling period to race against.
    """

    def __init__(
        self,
        parent,
        on_regenerate: Optional[Callable[[str], None]] = None,
        on_height_settled: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.on_regenerate     = on_regenerate
        self.on_height_settled = on_height_settled

        self._full_text = ""
        self._finalized = False
        self._copy_action = None

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        row.grid_columnconfigure(1, weight=1)

        avatar = ctk.CTkLabel(
            row,
            text=Icons.SPARKLE,
            width=Sizing.CHAT_AVATAR_SIZE,
            height=Sizing.CHAT_AVATAR_SIZE,
            fg_color=Colors.ACCENT,
            text_color=Colors.TEXT_INVERSE,
            font=ctk.CTkFont(family=Fonts.ICON, size=15),
            corner_radius=Sizing.RADIUS_PILL,
        )
        avatar.grid(row=0, column=0, sticky="n", pady=1)

        self._content = ctk.CTkFrame(row, fg_color="transparent")
        self._content.grid(row=0, column=1, sticky="ew", padx=(10, 60))
        self._content.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._content,
            text="DREX",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 4))

        self._label = ctk.CTkLabel(
            self._content,
            text="",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD),
            text_color=Colors.TEXT_PRIMARY,
            wraplength=Sizing.CHAT_MSG_MAX_W,
            justify="left",
            anchor="w",
        )
        self._label.pack(fill="x", anchor="w")

        self._alive = True
        self._caret_on = True
        self._blink()

    def _render(self):
        try:
            caret = "▏" if self._caret_on else " "
            self._label.configure(text=self._full_text + caret)
            if self.on_height_settled:
                self.on_height_settled()
        except Exception:
            pass

    def _blink(self):
        if not self._alive:
            return
        self._caret_on = not self._caret_on
        self._render()
        self.after(530, self._blink)

    def append(self, token: str):
        self._full_text += token
        self._render()

    def get_text(self) -> str:
        return self._full_text

    def start(self):
        pass

    def stop(self):
        self._alive = False
        try:
            self._label.configure(text=self._full_text)
        except Exception:
            pass

    def finalize(self, provider: Optional[str] = None, final_text: str = ""):
        """Convert streaming label to a static message with action buttons."""
        if self._finalized:
            return
        self._finalized = True
        self._alive = False

        if final_text and not self._full_text:
            self._full_text = final_text

        try:
            self._label.configure(text=self._full_text)
        except Exception:
            pass

        strip = ctk.CTkFrame(self._content, fg_color="transparent")
        strip.pack(fill="x", anchor="w", pady=(Spacing.SM, 0))

        def _copy():
            try:
                self.clipboard_clear()
                self.clipboard_append(self._full_text)
                self._copy_action.configure(text=Icons.CHECK, text_color=Colors.SUCCESS)
                self.after(1400, lambda: self._copy_action.configure(
                    text=Icons.COPY, text_color=Colors.TEXT_MUTED))
            except Exception:
                pass

        def _regenerate():
            if self.on_regenerate:
                self.on_regenerate(self._full_text)

        self._copy_action = _mini_action_button(strip, Icons.COPY, _copy)
        self._copy_action.pack(side="left", padx=(0, 2))
        _mini_action_button(strip, Icons.REFRESH, _regenerate).pack(side="left", padx=(0, 2))

        if self.on_height_settled:
            try:
                self.on_height_settled()
            except Exception:
                pass

    def destroy(self):
        self._alive = False
        return super().destroy()


# =============================================================
#  CODE BLOCK
# =============================================================

class CodeBlock(ctk.CTkFrame):
    """Monospace code snippet with a copy button."""

    def __init__(self, parent, code: str, language: str = "", **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_BASE,
            corner_radius=Sizing.RADIUS_MD,
            border_width=1,
            border_color=Colors.BORDER,
            **kwargs,
        )
        self.code = code

        header = ctk.CTkFrame(self, fg_color=Colors.BG_SURFACE, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text=(language or "code").lower(),
            font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
        ).pack(side="left", padx=10, pady=4)

        self._copy_btn = ctk.CTkButton(
            header,
            text="Copy",
            width=58,
            height=24,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            fg_color="transparent",
            hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=Sizing.RADIUS_SM,
            command=self._copy,
        )
        self._copy_btn.pack(side="right", padx=6, pady=4)

        text_widget = tk.Text(
            self,
            font=(Fonts.MONO, Fonts.SM),
            bg=Colors.BG_BASE,
            fg=Colors.TEXT_PRIMARY,
            insertbackground=Colors.ACCENT,
            selectbackground=Colors.ACCENT_DIM,
            selectforeground=Colors.TEXT_INVERSE,
            relief="flat",
            padx=12,
            pady=8,
            wrap="none",
            height=min(code.count("\n") + 2, 20),
            cursor="arrow",
            bd=0,
            highlightthickness=0,
        )
        text_widget.insert("1.0", code)
        text_widget.configure(state="disabled")
        text_widget.pack(fill="both", expand=True)

    def _copy(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.code)
            self._copy_btn.configure(text="Copied", text_color=Colors.SUCCESS)
            self.after(1500, lambda: self._copy_btn.configure(
                text="Copy", text_color=Colors.TEXT_SECONDARY))
        except Exception:
            pass


# =============================================================
#  TYPING INDICATOR
# =============================================================

class TypingIndicator(ctk.CTkFrame):
    """'DREX is thinking' with three animated dots."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._alive = True
        self._step  = 0
        self._dots  = []

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")

        avatar = ctk.CTkLabel(
            row,
            text=Icons.SPARKLE,
            width=Sizing.CHAT_AVATAR_SIZE,
            height=Sizing.CHAT_AVATAR_SIZE,
            fg_color=Colors.ACCENT,
            text_color=Colors.TEXT_INVERSE,
            font=ctk.CTkFont(family=Fonts.ICON, size=15),
            corner_radius=Sizing.RADIUS_PILL,
        )
        avatar.pack(side="left", padx=(0, 10))

        bubble = ctk.CTkFrame(
            row,
            fg_color=Colors.DREX_BG,
            corner_radius=Sizing.RADIUS_LG,
            border_width=1,
            border_color=Colors.DREX_BORDER,
        )
        bubble.pack(side="left")

        inner = ctk.CTkFrame(bubble, fg_color="transparent")
        inner.pack(padx=Sizing.CHAT_MSG_PADDING, pady=Sizing.CHAT_MSG_PADDING)

        for _ in range(3):
            dot = ctk.CTkLabel(
                inner,
                text="●",
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=9),
                text_color=Colors.TEXT_FAINT,
            )
            dot.pack(side="left", padx=3)
            self._dots.append(dot)

        self._ramp = [Colors.TEXT_FAINT, Colors.TEXT_MUTED,
                      Colors.TEXT_SECONDARY, Colors.ACCENT_LIGHT]
        self._animate()

    def _animate(self):
        if not self._alive:
            return
        n = len(self._ramp) - 1
        for i, dot in enumerate(self._dots):
            level = (self._step - i) % (n + 1)
            try:
                dot.configure(text_color=self._ramp[level])
            except Exception:
                return
        self._step = (self._step + 1) % (n + 1)
        self.after(180, self._animate)

    def start(self):
        pass

    def stop(self):
        self._alive = False

    def destroy(self):
        self._alive = False
        return super().destroy()


# =============================================================
#  BUTTONS
# =============================================================

class PrimaryButton(ctk.CTkButton):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.ACCENT,
            hover_color=Colors.ACCENT_HOVER,
            text_color=Colors.TEXT_INVERSE,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            corner_radius=Sizing.RADIUS_MD,
            height=Sizing.BTN_HEIGHT,
            **kwargs,
        )
        add_press_feedback(self, Colors.ACCENT_HOVER, Colors.ACCENT_PRESS)


class SecondaryButton(ctk.CTkButton):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_ELEVATED,
            hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_PRIMARY,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            corner_radius=Sizing.RADIUS_MD,
            height=Sizing.BTN_HEIGHT,
            border_width=1,
            border_color=Colors.BORDER,
            **kwargs,
        )
        add_press_feedback(self, Colors.BG_OVERLAY, Colors.BG_PRESSED)


class DangerButton(ctk.CTkButton):
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.ERROR,
            hover_color=Colors.BTN_DANGER_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            corner_radius=Sizing.RADIUS_MD,
            height=Sizing.BTN_HEIGHT,
            **kwargs,
        )
        add_press_feedback(self, Colors.BTN_DANGER_HOVER, "#B91C1C")


class SidebarButton(ctk.CTkButton):
    def __init__(self, parent, icon: str, label: str, active: bool = False, **kwargs):
        self._active = active
        fg = Colors.BG_OVERLAY if active else "transparent"
        text_color = Colors.ACCENT if active else Colors.TEXT_SECONDARY
        super().__init__(
            parent,
            text=f"  {icon}  {label}",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM,
                             weight="bold" if active else "normal"),
            fg_color=fg,
            hover_color=Colors.BG_OVERLAY,
            text_color=text_color,
            corner_radius=Sizing.RADIUS_MD,
            height=Sizing.BTN_HEIGHT,
            anchor="w",
            border_width=0,
            **kwargs,
        )

    def set_active(self, active: bool):
        self._active = active
        self.configure(
            fg_color=Colors.BG_OVERLAY if active else "transparent",
            text_color=Colors.ACCENT if active else Colors.TEXT_SECONDARY,
        )


# =============================================================
#  SECTION HEADER
# =============================================================

class SectionHeader(ctk.CTkLabel):
    def __init__(self, parent, text: str, **kwargs):
        super().__init__(
            parent,
            text=text.upper(),
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS, weight="bold"),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
            **kwargs,
        )


# =============================================================
#  TOAST
# =============================================================

class Toast(ctk.CTkToplevel):
    COLORS = {
        "success": Colors.SUCCESS,
        "error":   Colors.ERROR,
        "warning": Colors.WARNING,
        "info":    Colors.ACCENT,
    }

    def __init__(self, parent, message: str, kind: str = "info", duration_ms: int = 3000):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=Colors.BG_ELEVATED)

        color = self.COLORS.get(kind, Colors.ACCENT)

        frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_ELEVATED,
            corner_radius=Sizing.RADIUS_MD,
            border_width=1,
            border_color=color,
        )
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        icon = {"success": "✓", "error": "✕",
                "warning": "!", "info": "i"}.get(kind, "•")

        ctk.CTkLabel(
            frame,
            text=icon,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD, weight="bold"),
            text_color=color,
        ).pack(side="left", padx=(14, 6), pady=12)

        ctk.CTkLabel(
            frame,
            text=message,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 16), pady=12)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = max(280, self.winfo_reqwidth() + 4)
        h = self.winfo_reqheight() + 4
        x = sw - w - 24
        y = sh - h - 60
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.after(duration_ms, self.destroy)