# ============================================================
#  DREX - AI Desktop Assistant
#  gui/plugin_list.py  —  Sidebar Plugin List
#
#  WHAT IT DOES:
#  Displays available plugins in the sidebar.
#  Each plugin can be enabled/disabled.
#
#  DESIGN: Flat design, toggle switches
# ============================================================

import customtkinter as ctk
from gui.theme import Colors, Fonts, Sizing, Spacing


class PluginItem(ctk.CTkFrame):
    """
    Single plugin item with toggle switch.
    """

    def __init__(self, parent, plugin_id: str, name: str,
                 description: str = "", enabled: bool = False,
                 on_toggle=None, **kwargs):
        super().__init__(
            parent,
            fg_color="transparent",
            corner_radius=Sizing.RADIUS_MD,
            border_width=0,
            **kwargs
        )
        
        self.plugin_id = plugin_id
        self.on_toggle = on_toggle
        self._enabled = enabled
        
        self.grid_columnconfigure(0, weight=1)
        self._build(name, description, enabled)

    def _build(self, name: str, description: str, enabled: bool):
        """Build plugin item layout."""
        # Plugin info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=0, sticky="ew", padx=Spacing.MD, pady=Spacing.SM)
        info_frame.grid_columnconfigure(0, weight=1)
        
        name_label = ctk.CTkLabel(
            info_frame,
            text=name,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
        )
        name_label.grid(row=0, column=0, sticky="w")
        
        if description:
            desc_label = ctk.CTkLabel(
                info_frame,
                text=description[:30] + ("..." if len(description) > 30 else ""),
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            )
            desc_label.grid(row=1, column=0, sticky="w")
        
        # Toggle switch
        self._toggle_btn = ctk.CTkButton(
            self,
            text="●" if enabled else "○",
            width=36,
            height=20,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            fg_color=Colors.ACCENT if enabled else Colors.BG_ELEVATED,
            hover_color=Colors.ACCENT_HOVER if enabled else Colors.BG_OVERLAY,
            text_color=Colors.TEXT_INVERSE if enabled else Colors.TEXT_MUTED,
            corner_radius=Sizing.RADIUS_PILL,
            command=lambda: self._on_toggle_click(),
        )
        self._toggle_btn.grid(row=0, column=1, sticky="e", padx=Spacing.MD, pady=Spacing.SM)

    def _on_toggle_click(self):
        """Handle toggle click."""
        self._enabled = not self._enabled
        self._toggle_btn.configure(
            text="●" if self._enabled else "○",
            fg_color=Colors.ACCENT if self._enabled else Colors.BG_ELEVATED,
            text_color=Colors.TEXT_INVERSE if self._enabled else Colors.TEXT_MUTED,
        )
        if self.on_toggle:
            self.on_toggle(self.plugin_id, self._enabled)


class PluginList(ctk.CTkFrame):
    """
    Container for plugin items.
    """

    def __init__(self, parent, on_plugin_toggle=None, **kwargs):
        super().__init__(
            parent,
            fg_color="transparent",
            **kwargs
        )
        
        self.on_plugin_toggle = on_plugin_toggle
        self._plugins = {}
        
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        """Build plugin list layout."""
        # Section header
        header = ctk.CTkFrame(self, fg_color="transparent", height=24)
        header.grid(row=0, column=0, sticky="ew", padx=Spacing.MD, pady=Spacing.SM)
        
        title = ctk.CTkLabel(
            header,
            text="PLUGINS",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS, weight="bold"),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        )
        title.pack(side="left")
        
        # Plugins container
        self._plugins_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._plugins_frame.grid(row=1, column=0, sticky="ew")

    def add_plugin(self, plugin_id: str, name: str,
                   description: str = "", enabled: bool = False):
        """Add a plugin to the list."""
        if plugin_id in self._plugins:
            return
        
        item = PluginItem(
            self._plugins_frame,
            plugin_id=plugin_id,
            name=name,
            description=description,
            enabled=enabled,
            on_toggle=lambda pid, state: self._on_plugin_toggle(pid, state),
        )
        item.pack(fill="x", pady=1)
        self._plugins[plugin_id] = item

    def _on_plugin_toggle(self, plugin_id: str, enabled: bool):
        """Handle plugin toggle."""
        if self.on_plugin_toggle:
            self.on_plugin_toggle(plugin_id, enabled)

    def clear(self):
        """Remove all plugins."""
        for plugin in self._plugins.values():
            plugin.destroy()
        self._plugins.clear()