# ============================================================
#  DREX - AI Desktop Assistant
#  gui/about_tab.py  —  About/Settings Tab
#
#  WHAT IT DOES:
#  Displays system information and app metadata.
#  Part of the Settings modal.
#
#  DESIGN: Flat design, clean info display
# ============================================================

import customtkinter as ctk
import platform
import psutil
from datetime import datetime
from gui.theme import Colors, Fonts, Sizing, Spacing


class AboutTab(ctk.CTkFrame):
    """
    About tab showing system info and app details.
    """

    def __init__(self, parent, version: str = "1.0.0", **kwargs):
        super().__init__(
            parent,
            fg_color="transparent",
            **kwargs
        )
        
        self.version = version
        self._build()

    def _build(self):
        """Build about tab layout."""
        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=Colors.BG_ELEVATED,
        )
        scroll.pack(fill="both", expand=True, padx=Spacing.LG, pady=Spacing.LG)
        
        # App info
        self._build_app_info(scroll)
        
        # System info
        self._build_system_info(scroll)
        
        # License
        self._build_license(scroll)

    def _build_app_info(self, parent):
        """Build app information section."""
        # Title
        title = ctk.CTkLabel(
            parent,
            text="DREX - AI Desktop Assistant",
            font=ctk.CTkFont(family=Fonts.DISPLAY, size=Fonts.XL, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        )
        title.pack(fill="x", pady=(0, Spacing.XS))
        
        # Version
        version_label = ctk.CTkLabel(
            parent,
            text=f"Version {self.version}",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
        )
        version_label.pack(fill="x", pady=(0, Spacing.LG))
        
        # Description
        desc = ctk.CTkLabel(
            parent,
            text="AI-powered desktop assistant with voice, automation, and memory.",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
            wraplength=500,
        )
        desc.pack(fill="x", pady=(0, Spacing.LG))

    def _build_system_info(self, parent):
        """Build system information section."""
        # Section title
        section_title = ctk.CTkLabel(
            parent,
            text="System Information",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.BASE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        )
        section_title.pack(fill="x", pady=(Spacing.LG, Spacing.MD))
        
        # System stats
        stats = self._get_system_stats()
        
        for key, value in stats.items():
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=Spacing.XS)
            
            key_label = ctk.CTkLabel(
                row,
                text=key,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
                text_color=Colors.TEXT_SECONDARY,
                width=120,
                anchor="w",
            )
            key_label.pack(side="left")
            
            value_label = ctk.CTkLabel(
                row,
                text=value,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
                text_color=Colors.TEXT_PRIMARY,
                anchor="w",
            )
            value_label.pack(side="left", padx=(Spacing.SM, 0))

    def _build_license(self, parent):
        """Build license section."""
        # Section title
        section_title = ctk.CTkLabel(
            parent,
            text="License",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.BASE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        )
        section_title.pack(fill="x", pady=(Spacing.LG, Spacing.MD))
        
        # License text
        license_text = (
            "DREX is proprietary software. All rights reserved.\n"
            "Unauthorized copying, modification, or distribution is prohibited."
        )
        
        license_label = ctk.CTkLabel(
            parent,
            text=license_text,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
            wraplength=500,
        )
        license_label.pack(fill="x", pady=(0, Spacing.LG))

    def _get_system_stats(self) -> dict:
        """Get system statistics."""
        stats = {}
        
        try:
            # OS
            stats["OS"] = f"{platform.system()} {platform.release()}"
            
            # CPU
            stats["CPU"] = platform.processor() or "Unknown"
            
            # RAM
            ram = psutil.virtual_memory()
            stats["RAM"] = f"{ram.total / (1024**3):.1f} GB"
            
            # Python
            stats["Python"] = platform.python_version()
            
            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            stats["Uptime"] = f"{uptime.days}d {hours}h {minutes}m"
            
        except Exception as e:
            stats["Error"] = f"Could not load system info: {e}"
        
        return stats