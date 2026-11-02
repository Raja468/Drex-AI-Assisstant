# ============================================================
#  DREX - AI Desktop Assistant
#  gui/settings_modal.py  —  Settings Dialog
#
#  A modal window for configuring:
#  - General settings
#  - Appearance
#  - AI Providers
#  - Voice
#  - Automation
#  - Downloads
#  - Plugins
#  - Memory
#  - Advanced
#  - About
#
#  DESIGN: Flat design, tabbed interface
# ============================================================

import customtkinter as ctk
from gui.theme import Colors, Fonts, Sizing, Spacing
from gui.widgets import PrimaryButton, SecondaryButton
from utils.logger import logger


class SettingsModal(ctk.CTkToplevel):
    """
    Modal settings window with tabbed interface.
    """

    def __init__(self, parent, memory=None, orchestrator=None, on_save=None):
        super().__init__(parent)
        self.memory       = memory
        self.orchestrator = orchestrator
        self.on_save      = on_save

        # Window setup
        self.title("Drex Settings")
        self.geometry("700x600")
        self.resizable(True, True)
        self.configure(fg_color=Colors.BG_SURFACE)
        self.grab_set()
        self.focus_set()

        # Center on parent
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - 700) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{px}+{py}")

        self._entries = {}
        self._build()

    def _build(self):
        """Build settings modal layout."""
        # Title
        title_frame = ctk.CTkFrame(self, fg_color=Colors.BG_BASE, corner_radius=0)
        title_frame.pack(fill="x", padx=0, pady=0)
        
        ctk.CTkLabel(
            title_frame,
            text="Settings",
            font=ctk.CTkFont(family=Fonts.DISPLAY, size=Fonts.XL, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(padx=Spacing.LG, pady=(Spacing.LG, Spacing.SM), anchor="w")
        
        ctk.CTkLabel(
            title_frame,
            text="Configure your preferences",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_SECONDARY,
        ).pack(padx=Spacing.LG, pady=(0, Spacing.MD), anchor="w")

        # Tabview
        self._tabview = ctk.CTkTabview(
            self,
            fg_color=Colors.BG_SURFACE,
            segmented_button_fg_color=Colors.BG_ELEVATED,
            segmented_button_selected_color=Colors.ACCENT,
            segmented_button_unselected_color=Colors.BG_ELEVATED,
            text_color=Colors.TEXT_SECONDARY,
            text_color_disabled=Colors.TEXT_MUTED,
            corner_radius=Sizing.RADIUS_MD,
            border_width=0,
        )
        self._tabview.pack(fill="both", expand=True, padx=Spacing.LG, pady=(0, Spacing.LG))

        # Create tabs
        self._create_general_tab()
        self._create_appearance_tab()
        self._create_providers_tab()
        self._create_voice_tab()
        self._create_about_tab()

        # Pre-populate fields with saved values
        self._load_current_values()

        # Action buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=Spacing.LG, pady=(0, Spacing.LG))

        SecondaryButton(
            btn_frame, text="Cancel", command=self.destroy
        ).pack(side="right", padx=(8, 0))

        PrimaryButton(
            btn_frame, text="Save Settings", command=self._save
        ).pack(side="right")

    def _create_general_tab(self):
        """Create General settings tab."""
        tab = self._tabview.add("General")
        
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=Spacing.MD, pady=Spacing.MD)
        
        # User profile section
        ctk.CTkLabel(
            scroll,
            text="Profile",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.BASE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", pady=(0, Spacing.SM))
        
        self._build_field(scroll, "user_name", "Your Name", "Drex will use this to greet you")
        
        # Language
        self._build_label(scroll, "Language")
        self._entries["language"] = ctk.CTkOptionMenu(
            scroll,
            values=["English", "Spanish", "French", "German", "Chinese", "Japanese"],
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_ELEVATED,
            button_hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_PRIMARY,
        )
        self._entries["language"].pack(fill="x", pady=(0, Spacing.MD))

    def _create_appearance_tab(self):
        """Create Appearance settings tab."""
        tab = self._tabview.add("Appearance")
        
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=Spacing.MD, pady=Spacing.MD)
        
        ctk.CTkLabel(
            scroll,
            text="Theme",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.BASE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", pady=(0, Spacing.SM))
        
        self._build_label(scroll, "Color Theme")
        self._entries["theme"] = ctk.CTkOptionMenu(
            scroll,
            values=["Dark", "Light", "System"],
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_ELEVATED,
            button_hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_PRIMARY,
        )
        self._entries["theme"].pack(fill="x", pady=(0, Spacing.MD))

    def _create_providers_tab(self):
        """Create AI Providers settings tab."""
        tab = self._tabview.add("Providers")
        
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=Spacing.MD, pady=Spacing.MD)
        
        ctk.CTkLabel(
            scroll,
            text="Default Provider",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.BASE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", pady=(0, Spacing.SM))
        
        self._build_label(scroll, "Preferred AI Provider")
        self._entries["default_ai"] = ctk.CTkOptionMenu(
            scroll,
            values=["Gemini (Recommended)", "Groq (Fastest)", "OpenRouter (Most Models)"],
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_ELEVATED,
            button_hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_PRIMARY,
        )
        self._entries["default_ai"].pack(fill="x", pady=(0, Spacing.MD))
        
        ctk.CTkLabel(
            scroll,
            text="API Keys are stored locally and never shared.",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
        ).pack(fill="x", pady=(0, Spacing.MD))

    def _create_voice_tab(self):
        """Create Voice settings tab."""
        tab = self._tabview.add("Voice")
        
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=Spacing.MD, pady=Spacing.MD)
        
        ctk.CTkLabel(
            scroll,
            text="Voice Settings",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.BASE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", pady=(0, Spacing.SM))
        
        self._build_label(scroll, "Text-to-Speech Engine")
        self._entries["tts_engine"] = ctk.CTkOptionMenu(
            scroll,
            values=["pyttsx3 (Offline)", "edge-tts (Online, Better Quality)"],
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_ELEVATED,
            button_hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_PRIMARY,
        )
        self._entries["tts_engine"].pack(fill="x", pady=(0, Spacing.MD))
        
        self._build_label(scroll, "Speech-to-Text Engine")
        self._entries["stt_engine"] = ctk.CTkOptionMenu(
            scroll,
            values=["google (Online, Free)", "whisper (Offline, Private)"],
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_ELEVATED,
            button_hover_color=Colors.BG_OVERLAY,
            text_color=Colors.TEXT_PRIMARY,
        )
        self._entries["stt_engine"].pack(fill="x", pady=(0, Spacing.MD))

    def _create_about_tab(self):
        """Create About tab."""
        from gui.about_tab import AboutTab
        
        tab = self._tabview.add("About")
        about = AboutTab(tab)
        about.pack(fill="both", expand=True)

    def _build_label(self, parent, text: str):
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x", pady=(Spacing.SM, Spacing.XS))

    def _build_field(self, parent, key: str, label: str, hint: str = "", secret: bool = False):
        self._build_label(parent, label)
        
        if hint:
            ctk.CTkLabel(
                parent,
                text=hint,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            ).pack(fill="x")
        
        entry = ctk.CTkEntry(
            parent,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            fg_color=Colors.BG_ELEVATED,
            border_color=Colors.BORDER,
            text_color=Colors.TEXT_PRIMARY,
            placeholder_text_color=Colors.TEXT_MUTED,
            show="•" if secret else "",
            height=36,
            corner_radius=Sizing.RADIUS_MD,
        )
        entry.pack(fill="x", pady=(0, Spacing.MD))
        self._entries[key] = entry

    def _load_current_values(self):
        """Pre-populate fields with current saved values."""
        if not self.memory:
            return
        try:
            prefs = self.memory.preferences
            
            if isinstance(self._entries.get("user_name"), ctk.CTkEntry):
                name = prefs.get("user_name", "")
                if name:
                    self._entries["user_name"].insert(0, name)
            
            speed = prefs.get("tts_speed", 165)
            if "tts_speed" in self._entries:
                self._entries["tts_speed"].set(int(speed))
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _save(self):
        """Save all settings."""
        try:
            if self.memory:
                prefs = self.memory.preferences

                # User name
                name_entry = self._entries.get("user_name")
                if isinstance(name_entry, ctk.CTkEntry):
                    name = name_entry.get().strip()
                    if name:
                        prefs.set("user_name", name)

                # Language (CTkOptionMenu)
                language_menu = self._entries.get("language")
                if isinstance(language_menu, ctk.CTkOptionMenu):
                    prefs.set("language", language_menu.get())

                # Theme (CTkOptionMenu)
                theme_menu = self._entries.get("theme")
                if isinstance(theme_menu, ctk.CTkOptionMenu):
                    prefs.set("theme", theme_menu.get())

                # Default AI provider (CTkOptionMenu)
                provider_menu = self._entries.get("default_ai")
                if isinstance(provider_menu, ctk.CTkOptionMenu):
                    prefs.set("default_ai", provider_menu.get())

                # TTS engine (CTkOptionMenu)
                tts_menu = self._entries.get("tts_engine")
                if isinstance(tts_menu, ctk.CTkOptionMenu):
                    prefs.set("tts_engine", tts_menu.get())

                # STT engine (CTkOptionMenu)
                stt_menu = self._entries.get("stt_engine")
                if isinstance(stt_menu, ctk.CTkOptionMenu):
                    prefs.set("stt_engine", stt_menu.get())

            if self.on_save:
                self.on_save()

            logger.info("Settings saved")
            self.destroy()

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")