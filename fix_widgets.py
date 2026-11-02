# Fix widgets.py - replace MessageBubble render and StreamingLabel
import re

with open('gui/widgets.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace MessageBubble._build_content comment + _render_bubble + _render_mixed
old_bubble = '''        # Bubble
        if "```" in self.content:
            self._render_mixed(parent, side)
        else:
            self._render_bubble(parent, self.content, side)

        # Action row (assistant only)
        if self.role == "assistant":
            self._build_actions(parent)

    def _render_bubble(self, parent, text: str, side: str):
        bubble = ctk.CTkFrame(
            parent,
            fg_color=self.bubble_color,
            corner_radius=Sizing.RADIUS_LG,
            border_width=1,
            border_color=self.border_color,
        )
        bubble.grid(row=len(parent.grid_slaves()), column=0,
                    sticky="e" if side == "e" else "w")

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
                self._render_bubble(parent, part.strip(), side)
            else:
                block = CodeBlock(parent, code=part.strip())
                block.grid(row=len(parent.grid_slaves()), column=0,
                           sticky="ew", pady=(4, 0))'''

new_content = '''        # Content - no bubble for assistant, plain text on background
        if "```" in self.content:
            self._render_mixed(parent, side)
        else:
            self._render_content(parent, self.content, side)

        # Action row (assistant only)
        if self.role == "assistant":
            self._build_actions(parent)

    def _render_content(self, parent, text: str, side: str):
        """Render text directly - no bubble frame for assistant."""
        if self.role == "assistant":
            # Plain text on chat background, no bubble
            lbl = ctk.CTkLabel(
                parent,
                text=text,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD),
                text_color=self.text_color,
                wraplength=Sizing.CHAT_MSG_MAX_W,
                justify="left",
                anchor="w",
            )
            lbl.grid(row=len(parent.grid_slaves()), column=0, sticky="ew")
        else:
            # User messages keep their bubble
            bubble = ctk.CTkFrame(
                parent,
                fg_color=self.bubble_color,
                corner_radius=Sizing.RADIUS_LG,
                border_width=1,
                border_color=self.border_color,
            )
            bubble.grid(row=len(parent.grid_slaves()), column=0,
                        sticky="e" if side == "e" else "w")

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
                block.grid(row=len(parent.grid_slaves()), column=0,
                           sticky="ew", pady=(4, 0))'''

if old_bubble in content:
    content = content.replace(old_bubble, new_content, 1)
    print("MessageBubble: REPLACED")
else:
    print("MessageBubble: NOT FOUND - checking if already updated")
    if '_render_content' in content:
        print("  (already has _render_content)")
    else:
        print("  (ERROR: pattern not found)")

# 2. Replace StreamingLabel class
old_streaming = '''class StreamingLabel(ctk.CTkFrame):
    \"\"\"Live-updating assistant bubble for token streaming.\"\"\"

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._full_text = ""

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

        content = ctk.CTkFrame(row, fg_color="transparent")
        content.grid(row=0, column=1, sticky="ew", padx=(10, 60))
        content.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            content,
            text="DREX",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self._bubble = ctk.CTkFrame(
            content,
            fg_color=Colors.DREX_BG,
            corner_radius=Sizing.RADIUS_LG,
            border_width=1,
            border_color=Colors.DREX_BORDER,
        )
        self._bubble.grid(row=1, column=0, sticky="ew")

        self._label = ctk.CTkLabel(
            self._bubble,
            text="",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD),
            text_color=Colors.TEXT_PRIMARY,
            wraplength=Sizing.CHAT_MSG_MAX_W - 2 * Sizing.CHAT_MSG_PADDING,
            justify="left",
            anchor="w",
        )
        self._label.pack(padx=Sizing.CHAT_MSG_PADDING,
                         pady=(Spacing.MD, Spacing.MD), fill="x")

        self._alive = True
        self._caret_on = True
        self._blink()

    def _render(self):
        \"\"\"Redraw text with the caret appended only while blinking on.\"\"\"
        try:
            caret = "\u258f" if self._caret_on else "\u2007"  # figure space keeps width
            self._label.configure(text=self._full_text + caret)
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

    def destroy(self):
        self._alive = False
        return super().destroy()'''

new_streaming = '''class StreamingLabel(ctk.CTkFrame):
    \"\"\"Live-updating assistant message for token streaming.

    Renders as plain text on the chat background (no bubble).
    Can be finalized in-place to become a static message with action buttons.
    \"\"\"

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._full_text = ""
        self._finalized = False

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

        content = ctk.CTkFrame(row, fg_color="transparent")
        content.grid(row=0, column=1, sticky="ew", padx=(10, 60))
        content.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            content,
            text="DREX",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        # No bubble - render label directly on the chat background
        self._label = ctk.CTkLabel(
            content,
            text="",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD),
            text_color=Colors.TEXT_PRIMARY,
            wraplength=Sizing.CHAT_MSG_MAX_W,
            justify="left",
            anchor="w",
        )
        self._label.grid(row=1, column=0, sticky="ew")

        self._alive = True
        self._caret_on = True
        self._blink()

    def _render(self):
        \"\"\"Redraw text with the caret appended only while blinking on.\"\"\"
        try:
            caret = "\u258f" if self._caret_on else "\u2007"  # figure space keeps width
            self._label.configure(text=self._full_text + caret)
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
        \"\"\"Stop the caret blink and show final text without caret.\"\"\"
        self._alive = False
        try:
            self._label.configure(text=self._full_text)
        except Exception:
            pass

    def finalize(self, provider: Optional[str] = None, final_text: str = ""):
        \"\"\"Convert streaming label to a static message with action buttons.

        Called in-place - no destroy + recreate cycle.
        If *final_text* is provided and no tokens were streamed, use it.
        \"\"\"
        if self._finalized:
            return
        self._finalized = True
        self._alive = False

        # Use final_text if nothing was streamed
        if final_text and not self._full_text:
            self._full_text = final_text

        try:
            self._label.configure(text=self._full_text)
        except Exception:
            pass

        # Add action buttons below the text
        content = self._label.master  # the content frame
        strip = ctk.CTkFrame(content, fg_color="transparent")
        strip.grid(row=2, column=0, sticky="w", pady=(Spacing.SM, 0))

        def _mini_btn(glyph, cmd):
            return ctk.CTkButton(
                strip,
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

        def _copy():
            try:
                self.clipboard_clear()
                self.clipboard_append(self._full_text)
                btn.configure(text=Icons.CHECK, text_color=Colors.SUCCESS)
                self.after(1400, lambda: btn.configure(
                    text=Icons.COPY, text_color=Colors.TEXT_MUTED))
            except Exception:
                pass

        btn = _mini_btn(Icons.COPY, _copy)
        btn.pack(side="left", padx=(0, 2))
        _mini_btn(Icons.REFRESH, lambda: None).pack(side="left", padx=(0, 2))

    def destroy(self):
        self._alive = False
        return super().destroy()'''

if old_streaming in content:
    content = content.replace(old_streaming, new_streaming, 1)
    print("StreamingLabel: REPLACED")
else:
    print("StreamingLabel: NOT FOUND - checking if already updated")
    if 'def finalize' in content:
        print("  (already has finalize)")
    else:
        print("  (ERROR: pattern not found)")

with open('gui/widgets.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
import ast
try:
    ast.parse(content)
    print("SYNTAX: OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")

print(f"File length: {len(content)}")
print(f"_render_content: {'_render_content' in content}")
print(f"finalize: {'def finalize' in content}")