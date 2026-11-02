# ============================================================
#  DREX - AI Desktop Assistant
#  gui/sidebar.py - Premium Left Sidebar
#
#  Structure:
#    Top     -> logo, New Chat, search
#    Middle  -> pinned / recent / projects / downloads / plugins
#    Bottom  -> user profile, version
# ============================================================

import customtkinter as ctk
from typing import Callable, Optional

from gui.theme import Colors, Fonts, Sizing, Spacing, Icons
from gui.chat_list import ChatList
from gui.project_list import ProjectList
from gui.plugin_list import PluginList
from gui.download_list import DownloadList


class Sidebar(ctk.CTkFrame):
    """Fixed-width sidebar with a modern, minimal look."""

    def __init__(
        self,
        parent,
        on_nav_change: Optional[Callable[[str], None]] = None,
        on_chat_select: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(
            parent,
            fg_color=Colors.BG_SIDEBAR,
            corner_radius=0,
            width=Sizing.SIDEBAR_W,
            border_width=0,
            **kwargs,
        )
        self.grid_propagate(False)

        self.on_nav_change = on_nav_change
        self.on_chat_select = on_chat_select
        self._build()

    # -----------------------------------------------------
    #  Layout
    # -----------------------------------------------------

    def _build(self):
        # Right hairline separator
        sep = ctk.CTkFrame(self, fg_color=Colors.BORDER, width=1, corner_radius=0)
        sep.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")

        # rows: 0 header, 1 new chat + search, 2 scrollable body (grows), 3 footer
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ----- Header (mini logo) -----
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew",
                    padx=Spacing.LG, pady=(Spacing.LG, Spacing.MD))

        ctk.CTkLabel(
            header,
            text=Icons.SPARKLE,
            width=30,
            height=30,
            font=ctk.CTkFont(family=Fonts.ICON, size=15),
            fg_color=Colors.ACCENT,
            text_color=Colors.TEXT_INVERSE,
            corner_radius=Sizing.RADIUS_MD,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            header,
            text="DREX",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.LG, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(side="left")

        # ----- New chat + search -----
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew",
                     padx=Spacing.MD, pady=(0, Spacing.MD))
        actions.grid_columnconfigure(0, weight=1)

        self._new_chat_btn = ctk.CTkButton(
            actions,
            text="+   New chat",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            fg_color=Colors.ACCENT,
            hover_color=Colors.ACCENT_HOVER,
            text_color=Colors.TEXT_INVERSE,
            corner_radius=Sizing.RADIUS_MD,
            height=40,
            command=self._on_new_chat,
        )
        self._new_chat_btn.grid(row=0, column=0, sticky="ew", pady=(0, Spacing.SM))

        # Search field: a bordered wrapper holding a leading glyph + borderless entry.
        self._search_wrap = ctk.CTkFrame(
            actions,
            fg_color=Colors.BG_ELEVATED,
            border_width=1,
            border_color=Colors.BORDER,
            corner_radius=Sizing.RADIUS_MD,
            height=36,
        )
        self._search_wrap.grid(row=1, column=0, sticky="ew")
        self._search_wrap.grid_propagate(False)
        self._search_wrap.grid_columnconfigure(1, weight=1)
        self._search_wrap.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(
            self._search_wrap,
            text=Icons.SEARCH,
            width=16,
            font=ctk.CTkFont(family=Fonts.ICON, size=13),
            text_color=Colors.TEXT_MUTED,
            fg_color="transparent",
        ).grid(row=0, column=0, padx=(Spacing.MD, Spacing.SM))

        self._search_entry = ctk.CTkEntry(
            self._search_wrap,
            placeholder_text="Search chats",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            fg_color="transparent",
            border_width=0,
            text_color=Colors.TEXT_PRIMARY,
            placeholder_text_color=Colors.TEXT_MUTED,
            height=32,
        )
        self._search_entry.grid(row=0, column=1, sticky="ew", padx=(0, Spacing.SM))
        self._search_entry.bind("<KeyRelease>", self._on_search)

        # Focus ring: brighten the wrapper border while the field is active.
        self._search_entry.bind(
            "<FocusIn>",
            lambda _e: self._search_wrap.configure(border_color=Colors.BORDER_FOCUS))
        self._search_entry.bind(
            "<FocusOut>",
            lambda _e: self._search_wrap.configure(border_color=Colors.BORDER))

        # ----- Scrollable body -----
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=Colors.BG_OVERLAY,
            scrollbar_button_hover_color=Colors.BORDER_LIGHT,
        )
        self._scroll.grid(row=2, column=0, sticky="nsew",
                          padx=(Spacing.SM, 4), pady=(0, Spacing.SM))
        self._scroll.grid_columnconfigure(0, weight=1)

        self._chat_list = ChatList(self._scroll, on_chat_select=self.on_chat_select)
        self._chat_list.grid(row=0, column=0, sticky="ew")

        self._project_list = ProjectList(self._scroll)
        self._project_list.grid(row=1, column=0, sticky="ew",
                                pady=(Spacing.MD, 0))

        self._download_list = DownloadList(self._scroll)
        self._download_list.grid(row=2, column=0, sticky="ew",
                                 pady=(Spacing.MD, 0))

        self._plugin_list = PluginList(self._scroll)
        self._plugin_list.grid(row=3, column=0, sticky="ew",
                               pady=(Spacing.MD, 0))

        # ----- Footer (user profile + version) -----
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew",
                    padx=Spacing.MD, pady=(Spacing.SM, Spacing.MD))
        footer.grid_columnconfigure(0, weight=1)

        # Divider above footer
        divider = ctk.CTkFrame(footer, fg_color=Colors.BORDER, height=1)
        divider.grid(row=0, column=0, columnspan=2, sticky="ew",
                     pady=(0, Spacing.SM))

        # User row
        user_row = ctk.CTkFrame(footer, fg_color="transparent")
        user_row.grid(row=1, column=0, columnspan=2, sticky="ew")
        user_row.grid_columnconfigure(1, weight=1)

        avatar = ctk.CTkLabel(
            user_row,
            text=Icons.USER,
            width=32,
            height=32,
            font=ctk.CTkFont(family=Fonts.ICON, size=14),
            fg_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=Sizing.RADIUS_PILL,
        )
        avatar.grid(row=0, column=0, padx=(2, 8), pady=4)

        name_col = ctk.CTkFrame(user_row, fg_color="transparent")
        name_col.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            name_col,
            text="User",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            name_col,
            text="DREX v1.0.0",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        self._settings_btn = ctk.CTkButton(
            user_row,
            text=Icons.SETTINGS,
            width=32,
            height=32,
            font=ctk.CTkFont(family=Fonts.ICON, size=15),
            fg_color="transparent",
            hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=Sizing.RADIUS_MD,
            command=self._on_settings_click,
        )
        self._settings_btn.grid(row=0, column=2, padx=(4, 0))

    # -----------------------------------------------------
    #  Handlers
    # -----------------------------------------------------

    def _on_new_chat(self):
        if self.on_nav_change:
            self.on_nav_change("new_chat")

    def _on_search(self, event):
        query = self._search_entry.get().strip().lower()
        try:
            self._chat_list.filter(query)
        except AttributeError:
            pass

    def _on_settings_click(self):
        if self.on_nav_change:
            self.on_nav_change("settings")

    # -----------------------------------------------------
    #  Public API (kept compatible with app.py)
    # -----------------------------------------------------

    def add_chat(self, chat_id, title, preview="", timestamp=None,
                 pinned=False, active=False):
        self._chat_list.add_chat(chat_id, title, preview, timestamp, pinned, active)

    def add_project(self, project_id, name, chat_count=0):
        self._project_list.add_project(project_id, name, chat_count)

    def add_plugin(self, plugin_id, name, description="", enabled=False):
        self._plugin_list.add_plugin(plugin_id, name, description, enabled)

    def add_download(self, download_id, filename, size="", timestamp=None):
        self._download_list.add_download(download_id, filename, size, timestamp)

    def clear_chats(self):
        self._chat_list.clear()

    def set_active_chat(self, chat_id):
        self._chat_list.set_active(chat_id)
