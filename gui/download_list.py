# ============================================================
#  DREX - AI Desktop Assistant
#  gui/download_list.py  —  Sidebar Download List
#
#  WHAT IT DOES:
#  Displays download history in the sidebar.
#  Shows files, screenshots, and exports.
#
#  DESIGN: Flat design, minimal list
# ============================================================

import customtkinter as ctk
from datetime import datetime
from gui.theme import Colors, Fonts, Sizing, Spacing


class DownloadItem(ctk.CTkFrame):
    """
    Single download item.
    Shows filename, size, and timestamp.
    """

    def __init__(self, parent, download_id: str, filename: str,
                 size: str = "", timestamp: datetime = None,
                 on_click=None, **kwargs):
        super().__init__(
            parent,
            fg_color="transparent",
            corner_radius=Sizing.RADIUS_MD,
            border_width=0,
            **kwargs
        )
        
        self.download_id = download_id
        self.on_click = on_click
        
        self.grid_columnconfigure(0, weight=1)
        self._build(filename, size, timestamp)

    def _build(self, filename: str, size: str, timestamp: datetime):
        """Build download item layout."""
        padx = Spacing.MD
        pady = Spacing.SM
        
        # Filename
        name_label = ctk.CTkLabel(
            self,
            text=filename[:35] + ("..." if len(filename) > 35 else ""),
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
        )
        name_label.grid(row=0, column=0, sticky="ew", padx=padx, pady=(pady, 0))
        
        # Size and time
        meta_parts = []
        if size:
            meta_parts.append(size)
        if timestamp:
            time_str = timestamp.strftime("%H:%M") if timestamp.date() == datetime.now().date() else timestamp.strftime("%b %d")
            meta_parts.append(time_str)
        
        if meta_parts:
            meta_label = ctk.CTkLabel(
                self,
                text="  ·  ".join(meta_parts),
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            )
            meta_label.grid(row=1, column=0, sticky="w", padx=padx, pady=(0, pady))


class DownloadList(ctk.CTkFrame):
    """
    Container for download items.
    """

    def __init__(self, parent, on_download_click=None, **kwargs):
        super().__init__(
            parent,
            fg_color="transparent",
            **kwargs
        )
        
        self.on_download_click = on_download_click
        self._downloads = {}
        
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        """Build download list layout."""
        # Section header
        header = ctk.CTkFrame(self, fg_color="transparent", height=24)
        header.grid(row=0, column=0, sticky="ew", padx=Spacing.MD, pady=Spacing.SM)
        
        title = ctk.CTkLabel(
            header,
            text="DOWNLOADS",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS, weight="bold"),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        )
        title.pack(side="left")
        
        # Downloads container
        self._downloads_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._downloads_frame.grid(row=1, column=0, sticky="ew")

    def add_download(self, download_id: str, filename: str,
                     size: str = "", timestamp: datetime = None):
        """Add a download to the list."""
        if download_id in self._downloads:
            # Remove existing and add to top
            existing = self._downloads[download_id]
            existing.destroy()
        
        item = DownloadItem(
            self._downloads_frame,
            download_id=download_id,
            filename=filename,
            size=size,
            timestamp=timestamp,
            on_click=lambda did=download_id: self._on_download_click(did),
        )
        item.pack(fill="x", pady=1)
        
        # Insert at top
        if hasattr(item, 'pack_info'):
            self._downloads_frame.update_idletasks()
        
        self._downloads[download_id] = item

    def _on_download_click(self, download_id: str):
        """Handle download selection."""
        if self.on_download_click:
            self.on_download_click(download_id)

    def clear(self):
        """Remove all downloads."""
        for download in self._downloads.values():
            download.destroy()
        self._downloads.clear()