# ============================================================
#  DREX - AI Desktop Assistant
#  gui/widgets.py  —  Reusable Custom UI Components
#
#  Custom widgets built on top of CustomTkinter.
#  Every panel uses these so the UI stays consistent.
#
#  Components:
#  - MessageBubble   — Chat message with avatar and timestamp
#  - StreamingLabel  — Live-updating label for realtime tokens
#  - StatusDot       — Animated pulsing status indicator
#  - SidebarButton   — Navigation button with icon + label
#  - AnimatedButton  — Button with hover/press color animation
#  - CodeBlock       — Monospace code block in chat
#  - TypingIndicator — Animated "..." dots while AI is thinking
#  - Toast           — Floating notification
# ============================================================

import tkinter as tk
import customtkinter as ctk
from datetime import datetime
from gui.theme import Colors, Fonts, Sizing, Spacing, Anim


# ─────────────────────────────────────────────────────────────
#  MESSAGE BUBBLE
#  Renders one chat message (user or AI)
# ─────────────────────────────────────────────────────────────

class MessageBubble(ctk.CTkFrame):
    """
    A single chat message displayed in the chat panel.
    Supports user messages (right-aligned) and AI responses (left-aligned).
    Automatically detects and highlights code blocks.
    """

    def __init__(self, parent, role: str, content: str, timestamp: str = None, provider: str = None, **kwargs):
        """
        Args:
            parent:    Parent container widget
            role:      "user" | "assistant"
            content:   Message text
            timestamp: Time string to display
            provider:  Provider name for AI messages
        """
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now().strftime("%I:%M %p")
        self.provider = provider

        # Style based on role
        if role == "user":
            self.bubble_color  = Colors.USER_BG
            self.border_color  = Colors.USER_BORDER
            self.text_color    = Colors.TEXT_PRIMARY
            self.label_color   = Colors.ACCENT
            self.label_text    = "You"
            self.anchor        = "e"  # Right-aligned
            self.padx_config   = (80, 0)
        else:
            self.bubble_color  = Colors.AI_BG
            self.border_color  = Colors.AI_BORDER
            self.text_color    = Colors.TEXT_PRIMARY
            self.label_color   = Colors.TEXT_SECONDARY
            self.label_text    = "Drex"
            self.anchor        = "w"  # Left-aligned
            self.padx_config   = (0, 80)

        self._build()

    def _build(self):
        # Outer row: avatar + bubble (or bubble + avatar for user)
        self.grid_columnconfigure(0, weight=1)

        # ── Main bubble container ─────────────────────────────
        bubble_outer = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        bubble_outer.pack(
            fill="x",
            padx=(self.padx_config[0], self.padx_config[1]),
            pady=(2, 2)
        )

        # Role label + timestamp + provider row
        meta_frame = ctk.CTkFrame(bubble_outer, fg_color="transparent")
        meta_frame.pack(fill="x", padx=4, pady=(0, 2))

        ctk.CTkLabel(
            meta_frame,
            text=self.label_text,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS, weight="bold"),
            text_color=self.label_color,
            anchor=self.anchor,
        ).pack(side="left" if self.role == "assistant" else "right")

        if self.provider and self.role == "assistant":
            ctk.CTkLabel(
                meta_frame,
                text=f"via {self.provider}",
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.ACCENT_DIM,
            ).pack(side="left" if self.role == "assistant" else "right", padx=(6, 0))

        ctk.CTkLabel(
            meta_frame,
            text=self.timestamp,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
        ).pack(side="right" if self.role == "assistant" else "left", padx=(8, 0))

        # Detect if content has code blocks
        has_code = "```" in self.content

        if has_code:
            self._render_mixed_content(bubble_outer)
        else:
            self._render_text_bubble(bubble_outer, self.content)

    def _render_text_bubble(self, parent, text: str):
        """Render a plain text bubble."""
        bubble = ctk.CTkFrame(
            parent,
            fg_color=self.bubble_color,
            corner_radius=Sizing.RADIUS_LG,
            border_width=1,
            border_color=self.border_color,
        )
        bubble.pack(fill="x", anchor=self.anchor)

        ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.BASE),
            text_color=self.text_color,
            wraplength=Sizing.CHAT_MSG_MAX_W,
            justify="left",
            anchor="w",
        ).pack(
            padx=Sizing.CHAT_MSG_PADDING,
            pady=Sizing.CHAT_MSG_PADDING,
            fill="x"
        )

    def _render_mixed_content(self, parent):
        """Render message with interspersed text and code blocks."""
        import re
        parts = re.split(r'```(?:\w+)?\n?(.*?)```', self.content, flags=re.DOTALL)

        # parts alternates: [text, code, text, code, ...]
        for i, part in enumerate(parts):
            if not part.strip():
                continue
            if i % 2 == 0:
                # Regular text
                self._render_text_bubble(parent, part.strip())
            else:
                # Code block
                CodeBlock(parent, code=part.strip()).pack(fill="x", pady=(4, 0))


# ─────────────────────────────────────────────────────────────
#  STREAMING LABEL
#  Live-updating label for realtime token rendering
# ─────────────────────────────────────────────────────────────

class StreamingLabel(ctk.CTkFrame):
    """
    A label that can be incrementally updated with streaming tokens.
    Displays tokens as they arrive for a realtime typing effect.

    Usage:
        label = StreamingLabel(parent, provider="Gemini")
        label.pack(...)
        label.append("Hello ")
        label.append("world!")
        full_text = label.get_text()  # "Hello world!"
        label.stop()
    """

    def __init__(self, parent, provider: str = "", **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._full_text = ""

        # Container bubble (AI-style)
        bubble = ctk.CTkFrame(
            self,
            fg_color=Colors.AI_BG,
            corner_radius=Sizing.RADIUS_LG,
            border_width=1,
            border_color=Colors.AI_BORDER,
        )
        bubble.pack(anchor="w", fill="x", padx=(0, 80))

        # Provider badge
        if provider:
            badge_frame = ctk.CTkFrame(bubble, fg_color="transparent")
            badge_frame.pack(fill="x", padx=14, pady=(8, 0))

            ctk.CTkLabel(
                badge_frame,
                text=provider,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS, weight="bold"),
                text_color=Colors.ACCENT,
                anchor="w",
            ).pack(fill="x")

        # Streaming text label
        self._label = ctk.CTkLabel(
            bubble,
            text="",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.BASE),
            text_color=Colors.TEXT_PRIMARY,
            wraplength=Sizing.CHAT_MSG_MAX_W,
            justify="left",
            anchor="w",
        )
        self._label.pack(
            fill="x",
            padx=Spacing.LG,
            pady=Spacing.MD,
        )

        # Blinking cursor indicator
        self._cursor = ctk.CTkLabel(
            bubble,
            text="▍",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.BASE),
            text_color=Colors.ACCENT,
        )
        self._cursor.pack(side="right", padx=(0, 14), pady=(0, 12))
        self._blink_cursor()

    def _blink_cursor(self):
        """Blink the cursor indicator while streaming."""
        if not hasattr(self, '_cursor') or not self._cursor:
            return
        current = self._cursor.cget("text_color")
        new_color = Colors.ACCENT if current == Colors.TEXT_MUTED else Colors.TEXT_MUTED
        try:
            self._cursor.configure(text_color=new_color)
        except Exception:
            pass
        self.after(500, self._blink_cursor)

    def append(self, token: str) -> None:
        """
        Append a token to the streaming text.

        Args:
            token: Text token to append.
        """
        self._full_text += token
        try:
            self._label.configure(text=self._full_text)
        except Exception:
            pass

    def get_text(self) -> str:
        """Get the full accumulated text."""
        return self._full_text

    def start(self):
        """Start the streaming label (show cursor)."""
        pass  # Cursor starts automatically

    def stop(self):
        """Stop the streaming label and remove cursor."""
        if hasattr(self, '_cursor') and self._cursor:
            try:
                self._cursor.destroy()
            except Exception:
                pass
            self._cursor = None


# ─────────────────────────────────────────────────────────────
#  CODE BLOCK
#  Dark monospace code display for AI code responses
# ─────────────────────────────────────────────────────────────

class CodeBlock(ctk.CTkFrame):
    """Displays a code snippet with copy button."""

    def __init__(self, parent, code: str, language: str = "", **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_DARKEST,
            corner_radius=Sizing.RADIUS_MD,
            border_width=1,
            border_color=Colors.BG_BORDER,
            **kwargs
        )
        self.code = code

        # Header bar
        header = ctk.CTkFrame(self, fg_color=Colors.BG_PANEL, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text=language or "code",
            font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
        ).pack(side="left", padx=10, pady=4)

        # Copy button
        copy_btn = ctk.CTkButton(
            header,
            text="Copy",
            width=50,
            height=22,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            fg_color=Colors.BG_ELEVATED,
            hover_color=Colors.BG_BORDER,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=4,
            command=self._copy_code,
        )
        copy_btn.pack(side="right", padx=6, pady=4)
        self._copy_btn = copy_btn

        # Code content
        text_widget = tk.Text(
            self,
            font=(Fonts.MONO, Fonts.SM),
            bg=Colors.BG_DARKEST,
            fg=Colors.ACCENT,
            insertbackground=Colors.ACCENT,
            selectbackground=Colors.ACCENT_DARK,
            relief="flat",
            padx=12,
            pady=8,
            wrap="none",
            state="normal",
            height=min(code.count('\n') + 2, 20),
            cursor="arrow",
        )
        text_widget.insert("1.0", code)
        text_widget.configure(state="disabled")
        text_widget.pack(fill="both", expand=True)

    def _copy_code(self):
        """Copy code to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self.code)
        self._copy_btn.configure(text="✓ Copied!")
        self.after(2000, lambda: self._copy_btn.configure(text="Copy"))


# ─────────────────────────────────────────────────────────────
#  STATUS DOT
#  Animated pulsing dot for status bar
# ─────────────────────────────────────────────────────────────

class StatusDot(ctk.CTkLabel):
    """
    Animated colored dot for showing current state.
    Pulses when in listening or processing mode.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            text="●",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=14),
            text_color=Colors.TEXT_SECONDARY,
            **kwargs
        )
        self._is_pulsing = False
        self._pulse_step = 0
        self._pulse_colors = []

    def set_state(self, color: str, pulse: bool = False):
        """
        Update dot color and optionally start pulsing.

        Args:
            color: Hex color string
            pulse: Whether to animate the pulse
        """
        self._is_pulsing = False  # Stop any existing pulse
        self.configure(text_color=color)

        if pulse:
            self._start_pulse(color)

    def _start_pulse(self, color: str):
        """Animate the dot between bright and dim."""
        self._is_pulsing = True
        self._pulse_step = 0

        def pulse_step():
            if not self._is_pulsing:
                return
            # Alternate between bright and dim every 500ms
            self._pulse_step += 1
            show_bright = (self._pulse_step % 2 == 0)
            self.configure(text_color=color if show_bright else Colors.TEXT_MUTED)
            self.after(500, pulse_step)

        pulse_step()

    def stop_pulse(self):
        self._is_pulsing = False


# ─────────────────────────────────────────────────────────────
#  TYPING INDICATOR
#  Animated dots shown while Drex is thinking
# ─────────────────────────────────────────────────────────────

class TypingIndicator(ctk.CTkFrame):
    """
    Shows an animated 'Drex is thinking...' indicator.
    Displays three dots that cycle through being highlighted.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._is_animating = False
        self._step = 0
        self._dots = []

        # Container bubble
        bubble = ctk.CTkFrame(
            self,
            fg_color=Colors.AI_BG,
            corner_radius=Sizing.RADIUS_LG,
            border_width=1,
            border_color=Colors.AI_BORDER,
        )
        bubble.pack(anchor="w", padx=(0, 80))

        inner = ctk.CTkFrame(bubble, fg_color="transparent")
        inner.pack(padx=16, pady=12)

        ctk.CTkLabel(
            inner,
            text="Drex is thinking",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_MUTED,
        ).pack(side="left")

        dots_frame = ctk.CTkFrame(inner, fg_color="transparent")
        dots_frame.pack(side="left", padx=(6, 0))

        for _ in range(3):
            dot = ctk.CTkLabel(
                dots_frame,
                text="●",
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=8),
                text_color=Colors.TEXT_MUTED,
            )
            dot.pack(side="left", padx=1)
            self._dots.append(dot)

    def start(self):
        """Begin the animation."""
        self._is_animating = True
        self._animate()

    def stop(self):
        """Stop the animation."""
        self._is_animating = False

    def _animate(self):
        if not self._is_animating:
            return
        for i, dot in enumerate(self._dots):
            dot.configure(
                text_color=Colors.ACCENT if i == self._step else Colors.TEXT_MUTED
            )
        self._step = (self._step + 1) % 3
        self.after(Anim.NORMAL + 100, self._animate)


# ─────────────────────────────────────────────────────────────
#  SIDEBAR BUTTON
#  Navigation button with icon and text label
# ─────────────────────────────────────────────────────────────

class SidebarButton(ctk.CTkButton):
    """Navigation button for the sidebar."""

    def __init__(self, parent, icon: str, label: str, active: bool = False, **kwargs):
        self._active = active
        fg = Colors.ACCENT_DARK if active else "transparent"
        text_color = Colors.ACCENT if active else Colors.TEXT_SECONDARY

        super().__init__(
            parent,
            text=f"  {icon}  {label}",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold" if active else "normal"),
            fg_color=fg,
            hover_color=Colors.BG_ELEVATED,
            text_color=text_color,
            corner_radius=Sizing.RADIUS_MD,
            height=Sizing.BTN_HEIGHT + 2,
            anchor="w",
            border_width=0,
            **kwargs
        )

    def set_active(self, active: bool):
        self._active = active
        self.configure(
            fg_color=Colors.ACCENT_DARK if active else "transparent",
            text_color=Colors.ACCENT if active else Colors.TEXT_SECONDARY,
        )


# ─────────────────────────────────────────────────────────────
#  ANIMATED BUTTON
#  Standard button with smooth color transitions on hover
# ─────────────────────────────────────────────────────────────

class PrimaryButton(ctk.CTkButton):
    """Cyan accent primary action button."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BTN_PRIMARY,
            hover_color=Colors.BTN_PRIMARY_HOVER,
            text_color=Colors.BG_DARK,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            corner_radius=Sizing.RADIUS_MD,
            height=Sizing.BTN_HEIGHT,
            **kwargs
        )


class SecondaryButton(ctk.CTkButton):
    """Subtle secondary action button."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BTN_SECONDARY,
            hover_color=Colors.BTN_SECONDARY_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            corner_radius=Sizing.RADIUS_MD,
            height=Sizing.BTN_HEIGHT,
            **kwargs
        )


class DangerButton(ctk.CTkButton):
    """Red danger/destructive action button."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BTN_DANGER,
            hover_color=Colors.BTN_DANGER_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            corner_radius=Sizing.RADIUS_MD,
            height=Sizing.BTN_HEIGHT,
            **kwargs
        )


# ─────────────────────────────────────────────────────────────
#  SECTION HEADER
#  Divider label for grouping content in panels
# ─────────────────────────────────────────────────────────────

class SectionHeader(ctk.CTkLabel):
    """Small all-caps section label."""

    def __init__(self, parent, text: str, **kwargs):
        super().__init__(
            parent,
            text=text.upper(),
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS, weight="bold"),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
            **kwargs
        )


# ─────────────────────────────────────────────────────────────
#  TOAST NOTIFICATION
#  Temporary popup message in a corner of the screen
# ─────────────────────────────────────────────────────────────

class Toast(ctk.CTkToplevel):
    """
    Floating notification that auto-dismisses.
    Shows in bottom-right corner of the screen.
    """

    COLORS = {
        "success": Colors.SUCCESS,
        "error":   Colors.ERROR,
        "warning": Colors.WARNING,
        "info":    Colors.ACCENT,
    }

    def __init__(self, parent, message: str, kind: str = "info", duration_ms: int = 3000):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)  # No title bar
        self.attributes("-topmost", True)
        self.configure(fg_color=Colors.BG_PANEL)

        color = self.COLORS.get(kind, Colors.ACCENT)

        # Content
        frame = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_PANEL,
            corner_radius=Sizing.RADIUS_MD,
            border_width=1,
            border_color=color,
        )
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        icon = {"success": "✓", "error": "✕", "warning": "⚠", "info": "ℹ"}.get(kind, "•")

        ctk.CTkLabel(
            frame,
            text=f" {icon} ",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD, weight="bold"),
            text_color=color,
        ).pack(side="left", padx=(12, 4), pady=12)

        ctk.CTkLabel(
            frame,
            text=message,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 16), pady=12)

        # Position bottom-right
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = max(280, self.winfo_reqwidth() + 4)
        h = self.winfo_reqheight() + 4
        x = sw - w - 24
        y = sh - h - 60
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()

        # Auto-dismiss
        self.after(duration_ms, self.destroy)