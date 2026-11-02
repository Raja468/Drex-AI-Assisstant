# ============================================================
#  DREX - AI Desktop Assistant
#  gui/top_bar.py - Premium Top Bar
#
#  Layout (left -> center -> right):
#    [ ◈ DREX / AI Desktop Assistant ]   [ Chat title ]   [ provider | model | theme | settings ]
# ============================================================

import customtkinter as ctk
from typing import Callable, Optional

from gui.theme import Colors, Fonts, Sizing, Spacing, Icons


class TopBar(ctk.CTkFrame):
    """
    Slim top bar. Logo left, conversation title in the center,
    context controls (provider, model, theme toggle, settings) on the right.
    """

    def __init__(
        self,
        parent,
        on_title_change: Optional[Callable[[str], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
        on_theme_toggle: Optional[Callable[[], None]] = None,
        on_provider_click: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(
            parent,
            fg_color=Colors.BG_SURFACE,
            corner_radius=0,
            height=Sizing.TOPBAR_H,
            border_width=0,
            **kwargs,
        )
        self.grid_propagate(False)

        self.on_title_change   = on_title_change
        self.on_settings       = on_settings
        self.on_theme_toggle   = on_theme_toggle
        self.on_provider_click = on_provider_click

        self._current_provider = ""
        self._current_model    = ""

        self._build()

    def _build(self):
        # Bottom hairline separator
        sep = ctk.CTkFrame(self, fg_color=Colors.BORDER, height=1, corner_radius=0)
        sep.place(relx=0, rely=1.0, relwidth=1.0, anchor="sw")

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)  # title stretches
        self.grid_columnconfigure(2, weight=0)

        # ----- Left: logo + brand -----
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=(Spacing.LG, 0), pady=0)

        ctk.CTkLabel(
            left,
            text=Icons.SPARKLE,
            width=34,
            height=34,
            font=ctk.CTkFont(family=Fonts.ICON, size=17),
            fg_color=Colors.ACCENT,
            text_color=Colors.TEXT_INVERSE,
            corner_radius=Sizing.RADIUS_MD,
        ).pack(side="left", padx=(0, 10))

        brand_col = ctk.CTkFrame(left, fg_color="transparent")
        brand_col.pack(side="left")

        ctk.CTkLabel(
            brand_col,
            text="DREX",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand_col,
            text="AI Desktop Assistant",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        # ----- Center: chat title -----
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=1, sticky="ew", padx=Spacing.XL, pady=0)
        center.grid_columnconfigure(0, weight=1)

        self._title_entry = ctk.CTkEntry(
            center,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.MD, weight="bold"),
            fg_color="transparent",
            border_width=0,
            text_color=Colors.TEXT_PRIMARY,
            placeholder_text_color=Colors.TEXT_MUTED,
            placeholder_text="Chat title",
            justify="center",
        )
        self._title_entry.insert(0, "New Chat")
        self._title_entry.grid(row=0, column=0, sticky="ew")
        self._title_entry.bind("<FocusOut>", self._on_title_changed)
        self._title_entry.bind("<Return>", self._on_title_changed)

        # ----- Right: provider + model + theme + settings -----
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(0, Spacing.LG), pady=0)

        # Provider pill
        self._provider_pill = ctk.CTkButton(
            right,
            text="No Provider",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            fg_color=Colors.BG_ELEVATED,
            hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=Sizing.RADIUS_PILL,
            height=30,
            border_width=1,
            border_color=Colors.BORDER,
            command=self._on_provider_click,
        )
        self._provider_pill.pack(side="left", padx=(0, 6))

        # Model label
        self._model_label = ctk.CTkLabel(
            right,
            text="",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_SECONDARY,
        )
        self._model_label.pack(side="left", padx=(0, 10))

        # Theme toggle
        self._theme_btn = self._icon_button(right, Icons.THEME, self._on_theme_click)
        self._theme_btn.pack(side="left", padx=(0, 4))

        # Settings icon
        self._settings_btn = self._icon_button(right, Icons.SETTINGS, self._on_settings_click)
        self._settings_btn.pack(side="left")

    def _icon_button(self, parent, glyph: str, command: Callable[[], None]):
        return ctk.CTkButton(
            parent,
            text=glyph,
            width=32,
            height=32,
            font=ctk.CTkFont(family=Fonts.ICON, size=15),
            fg_color="transparent",
            hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=Sizing.RADIUS_MD,
            command=command,
        )

    # -------------------------------------------------------------
    #  Public API
    # -------------------------------------------------------------

    def set_provider(self, provider: str, model: str = ""):
        self._current_provider = provider or ""
        self._current_model    = model or ""

        if provider:
            self._provider_pill.configure(
                text=provider,
                text_color=Colors.ACCENT,
                border_color=Colors.ACCENT_DIM,
            )
        else:
            self._provider_pill.configure(
                text="No Provider",
                text_color=Colors.TEXT_SECONDARY,
                border_color=Colors.BORDER,
            )

        self._model_label.configure(text=model or "")

    def set_title(self, title: str):
        self._title_entry.delete(0, "end")
        self._title_entry.insert(0, title)

    @property
    def title(self) -> str:
        return self._title_entry.get().strip()

    # -------------------------------------------------------------
    #  Handlers
    # -------------------------------------------------------------

    def _on_title_changed(self, event=None):
        if self.on_title_change:
            t = self._title_entry.get().strip()
            if t:
                self.on_title_change(t)
                self.focus_set()

    def _on_settings_click(self):
        if self.on_settings:
            self.on_settings()

    def _on_theme_click(self):
        if self.on_theme_toggle:
            self.on_theme_toggle()

    def _on_provider_click(self):
        if self.on_provider_click:
            self.on_provider_click()
