# ============================================================
#  DREX - AI Desktop Assistant
#  gui/settings_modal.py  —  Settings Dialog
#
#  A modal window for configuring:
#  - API keys (Gemini, Groq, OpenRouter)
#  - Voice settings (speed, engine)
#  - Appearance preferences
#  - User profile (name)
# ============================================================

import customtkinter as ctk
from gui.theme import Colors, Fonts, Sizing
from gui.widgets import PrimaryButton, SecondaryButton, SectionHeader
from utils.logger import logger


class SettingsModal(ctk.CTkToplevel):
    """
    Modal settings window.
    Opens on top of the main window.
    """

    def __init__(self, parent, memory=None, orchestrator=None, on_save=None):
        super().__init__(parent)
        self.memory       = memory
        self.orchestrator = orchestrator
        self.on_save      = on_save

        # Window setup
        self.title("Drex Settings")
        self.geometry("600x580")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_DARK)
        self.grab_set()  # Modal — blocks main window
        self.focus_set()

        # Center on parent
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - 600) // 2
        py = parent.winfo_y() + (parent.winfo_height() - 580) // 2
        self.geometry(f"+{px}+{py}")

        self._entries = {}
        self._build()
        self._load_current_values()

    def _build(self):
        # Title
        ctk.CTkLabel(
            self,
            text="⚙️  Settings",
            font=ctk.CTkFont(family=Fonts.DISPLAY, size=Fonts.XL, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
        ).pack(padx=32, pady=(24, 0), anchor="w")

        ctk.CTkLabel(
            self,
            text="Configure your API keys and preferences",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_MUTED,
        ).pack(padx=32, pady=(4, 16), anchor="w")

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=Colors.BG_BORDER,
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=0)

        self._build_api_section(scroll)
        self._build_voice_section(scroll)
        self._build_profile_section(scroll)

        # Action buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=16)

        SecondaryButton(
            btn_frame, text="Cancel", command=self.destroy
        ).pack(side="right", padx=(8, 0))

        PrimaryButton(
            btn_frame, text="  Save Settings  ", command=self._save
        ).pack(side="right")

    def _build_api_section(self, parent):
        """API Keys section."""
        card = self._make_card(parent)

        SectionHeader(card, "🔑  API Keys").pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            card,
            text="These keys are stored locally and never shared.",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
        ).pack(fill="x", padx=16, pady=(0, 12))

        api_fields = [
            ("gemini_key",     "Gemini API Key",     "aistudio.google.com — Free",     True),
            ("groq_key",       "Groq API Key",       "console.groq.com — Free",        True),
            ("openrouter_key", "OpenRouter API Key", "openrouter.ai — Optional (Free)", True),
        ]

        for key, label, hint, secret in api_fields:
            self._build_field(card, key, label, hint, secret=secret)

    def _build_voice_section(self, parent):
        """Voice settings section."""
        card = self._make_card(parent)

        SectionHeader(card, "🎤  Voice Settings").pack(fill="x", padx=16, pady=(16, 12))

        # TTS Engine selector
        self._build_label(card, "Text-to-Speech Engine")
        self._entries["tts_engine"] = ctk.CTkOptionMenu(
            card,
            values=["pyttsx3 (Offline)", "edge-tts (Online, Better Quality)"],
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_BORDER,
            button_hover_color=Colors.ACCENT_DIM,
            text_color=Colors.TEXT_PRIMARY,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
        )
        self._entries["tts_engine"].pack(fill="x", padx=16, pady=(4, 12))

        # STT Engine
        self._build_label(card, "Speech-to-Text Engine")
        self._entries["stt_engine"] = ctk.CTkOptionMenu(
            card,
            values=["google (Online, Free)", "whisper (Offline, Private)"],
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_BORDER,
            button_hover_color=Colors.ACCENT_DIM,
            text_color=Colors.TEXT_PRIMARY,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
        )
        self._entries["stt_engine"].pack(fill="x", padx=16, pady=(4, 12))

        # Voice speed slider
        self._build_label(card, "Speaking Speed")
        speed_frame = ctk.CTkFrame(card, fg_color="transparent")
        speed_frame.pack(fill="x", padx=16, pady=(4, 16))

        self._speed_var = ctk.IntVar(value=165)
        self._speed_label = ctk.CTkLabel(
            speed_frame,
            text="165 WPM",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_SECONDARY,
            width=70,
        )
        self._speed_label.pack(side="right")

        slider = ctk.CTkSlider(
            speed_frame,
            from_=100, to=250,
            number_of_steps=30,
            variable=self._speed_var,
            button_color=Colors.ACCENT,
            button_hover_color=Colors.BTN_PRIMARY_HOVER,
            progress_color=Colors.ACCENT_DARK,
            command=lambda v: self._speed_label.configure(text=f"{int(v)} WPM"),
        )
        slider.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self._entries["tts_speed"] = slider

    def _build_profile_section(self, parent):
        """User profile section."""
        card = self._make_card(parent)

        SectionHeader(card, "👤  Your Profile").pack(fill="x", padx=16, pady=(16, 12))

        self._build_field(card, "user_name", "Your Name",
                          "Drex will use this to greet you", secret=False)

        # Default AI selector
        self._build_label(card, "Preferred AI Provider")
        self._entries["default_ai"] = ctk.CTkOptionMenu(
            card,
            values=["gemini (Recommended)", "groq (Fastest)", "openrouter (Most Models)"],
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_BORDER,
            button_hover_color=Colors.ACCENT_DIM,
            text_color=Colors.TEXT_PRIMARY,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
        )
        self._entries["default_ai"].pack(fill="x", padx=16, pady=(4, 16))

    # ── Helpers ───────────────────────────────────────────────

    def _make_card(self, parent) -> ctk.CTkFrame:
        """Create a settings card container."""
        card = ctk.CTkFrame(
            parent,
            fg_color=Colors.BG_CARD,
            corner_radius=Sizing.RADIUS_LG,
            border_width=1,
            border_color=Colors.BG_BORDER,
        )
        card.pack(fill="x", pady=(0, 12))
        return card

    def _build_label(self, parent, text: str):
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 2))

    def _build_field(self, parent, key: str, label: str, hint: str = "", secret: bool = False):
        """Build a labeled text entry field."""
        self._build_label(parent, label)

        if hint:
            ctk.CTkLabel(
                parent,
                text=hint,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            ).pack(fill="x", padx=16)

        entry = ctk.CTkEntry(
            parent,
            font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.SM),
            fg_color=Colors.BG_ELEVATED,
            border_color=Colors.BG_BORDER,
            text_color=Colors.TEXT_PRIMARY,
            placeholder_text_color=Colors.TEXT_MUTED,
            show="•" if secret else "",
            height=36,
        )
        entry.pack(fill="x", padx=16, pady=(4, 14))
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
            self._speed_var.set(int(speed))
            self._speed_label.configure(text=f"{int(speed)} WPM")

        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _save(self):
        """Save all settings."""
        try:
            if self.memory:
                prefs = self.memory.preferences

                # API Keys → save to .env (write to file)
                keys_to_save = {}
                for field_key, env_key in [
                    ("gemini_key",     "GEMINI_API_KEY"),
                    ("groq_key",       "GROQ_API_KEY"),
                    ("openrouter_key", "OPENROUTER_API_KEY"),
                ]:
                    entry = self._entries.get(field_key)
                    if isinstance(entry, ctk.CTkEntry):
                        val = entry.get().strip()
                        if val:
                            keys_to_save[env_key] = val

                if keys_to_save:
                    self._write_env_keys(keys_to_save)

                # User name
                name_entry = self._entries.get("user_name")
                if isinstance(name_entry, ctk.CTkEntry):
                    name = name_entry.get().strip()
                    if name:
                        prefs.set("user_name", name)

                # TTS speed
                prefs.set("tts_speed", self._speed_var.get())

            if self.on_save:
                self.on_save()

            logger.info("Settings saved")
            self.destroy()

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def _write_env_keys(self, keys: dict):
        """Write API keys to the .env file."""
        try:
            from pathlib import Path
            env_path = Path(".env")

            # Read existing content
            existing = {}
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if "=" in line and not line.startswith("#"):
                        k, _, v = line.partition("=")
                        existing[k.strip()] = v.strip()

            # Update with new keys
            existing.update(keys)

            # Write back
            lines = [f"{k}={v}" for k, v in existing.items()]
            env_path.write_text("\n".join(lines) + "\n")
            logger.info(f"API keys written to .env: {list(keys.keys())}")

        except Exception as e:
            logger.error(f"Failed to write .env: {e}")
