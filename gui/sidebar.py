# ============================================================
#  DREX - AI Desktop Assistant
#  gui/sidebar.py  —  Left Navigation Sidebar
#
#  WHAT IT DOES:
#  The left panel of the main window containing:
#  - Drex logo/title
#  - Navigation: Chat, Skills, Memory, Settings
#  - AI provider status indicators
#  - Session statistics
#  - Listening toggle button
# ============================================================

import customtkinter as ctk
from gui.theme import Colors, Fonts, Sizing, Spacing
from gui.widgets import SidebarButton, SectionHeader, StatusDot
from utils.logger import logger


class Sidebar(ctk.CTkFrame):
    """
    Left sidebar with navigation and system status.
    """

    def __init__(self, parent, orchestrator=None, on_nav_change=None, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_PANEL,
            corner_radius=0,
            width=Sizing.SIDEBAR_W,
            border_width=1,
            border_color=Colors.BG_BORDER,
            **kwargs
        )
        self.grid_propagate(False)  # Keep fixed width

        self.orchestrator   = orchestrator
        self.on_nav_change  = on_nav_change
        self._active_section = "chat"
        self._nav_buttons   = {}

        self._build()
        logger.debug("Sidebar initialized")

    def _build(self):
        self.grid_rowconfigure(4, weight=1)  # Spacer row
        self.grid_columnconfigure(0, weight=1)

        self._build_logo()
        self._build_nav()
        self._build_spacer()
        self._build_ai_status()
        self._build_footer()

    # ── Logo / Header ─────────────────────────────────────────

    def _build_logo(self):
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 16))

        # Glowing icon
        ctk.CTkLabel(
            logo_frame,
            text="◈",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=28),
            text_color=Colors.ACCENT,
        ).pack(side="left")

        title_col = ctk.CTkFrame(logo_frame, fg_color="transparent")
        title_col.pack(side="left", padx=8)

        ctk.CTkLabel(
            title_col,
            text="Drex",
            font=ctk.CTkFont(family=Fonts.DISPLAY, size=Fonts.XL, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            title_col,
            text="AI Assistant",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")

        # Divider
        ctk.CTkFrame(
            self, height=1, fg_color=Colors.BG_BORDER
        ).grid(row=1, column=0, sticky="ew", padx=0)

    # ── Navigation ────────────────────────────────────────────

    def _build_nav(self):
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(12, 0))

        SectionHeader(nav_frame, "Navigation").pack(
            fill="x", padx=8, pady=(0, 6)
        )

        nav_items = [
            ("chat",     "💬",  "Chat"),
            ("memory",   "🧠",  "Memory"),
            ("settings", "⚙️", "Settings"),
            ("help",     "❓",  "Help"),
        ]

        for key, icon, label in nav_items:
            btn = SidebarButton(
                nav_frame,
                icon=icon,
                label=label,
                active=(key == self._active_section),
                command=lambda k=key: self._on_nav_click(k)
            )
            btn.pack(fill="x", pady=2)
            self._nav_buttons[key] = btn

    def _on_nav_click(self, key: str):
        """Handle navigation button click."""
        self._active_section = key
        for k, btn in self._nav_buttons.items():
            btn.set_active(k == key)
        if self.on_nav_change:
            self.on_nav_change(key)

    # ── Spacer ────────────────────────────────────────────────

    def _build_spacer(self):
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.grid(row=4, column=0, sticky="nsew")

    # ── AI Provider Status ────────────────────────────────────

    def _build_ai_status(self):
        ctk.CTkFrame(
            self, height=1, fg_color=Colors.BG_BORDER
        ).grid(row=5, column=0, sticky="ew")

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=6, column=0, sticky="ew", padx=16, pady=12)

        SectionHeader(status_frame, "AI Providers").pack(fill="x", pady=(0, 8))

        self._provider_rows = {}
        providers = [
            ("gemini",     "Gemini",     "⚡"),
            ("groq",       "Groq",       "🚀"),
            ("openrouter", "OpenRouter", "🌐"),
        ]

        for key, label, icon in providers:
            row = ctk.CTkFrame(status_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row,
                text=f"{icon} {label}",
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.TEXT_SECONDARY,
                anchor="w",
            ).pack(side="left")

            dot = StatusDot(row)
            dot.pack(side="right")
            dot.set_state(Colors.TEXT_MUTED)  # Default: unknown
            self._provider_rows[key] = dot

        # Update from orchestrator if available
        self.after(500, self._update_ai_status)

    def _update_ai_status(self):
        """Check which AI APIs are online and update the dots."""
        if not self.orchestrator:
            return
        try:
            router = self.orchestrator._ai_router
            if router:
                for key, dot in self._provider_rows.items():
                    available = router._api_health.get(key, False)
                    dot.set_state(Colors.SUCCESS if available else Colors.ERROR)
        except Exception as e:
            logger.debug(f"Could not update AI status: {e}")

    # ── Footer ────────────────────────────────────────────────

    def _build_footer(self):
        ctk.CTkFrame(
            self, height=1, fg_color=Colors.BG_BORDER
        ).grid(row=7, column=0, sticky="ew")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=8, column=0, sticky="ew", padx=16, pady=10)

        ctk.CTkLabel(
            footer,
            text="Drex v1.0.0",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            text_color=Colors.TEXT_MUTED,
        ).pack(side="left")

    # ── Public Methods ────────────────────────────────────────

    def refresh_status(self):
        """Force-refresh AI provider status indicators."""
        self._update_ai_status()
