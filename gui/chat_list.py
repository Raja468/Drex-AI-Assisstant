# ============================================================
#  DREX - AI Desktop Assistant
#  gui/chat_list.py  —  Sidebar Chat List
#
#  WHAT IT DOES:
#  Displays recent and pinned conversations in the sidebar.
#  Used inside the sidebar for navigation.
#
#  DESIGN: Flat design, clean list items
# ============================================================

import customtkinter as ctk
from datetime import datetime
from gui.theme import Colors, Fonts, Sizing, Spacing


class ChatItem(ctk.CTkFrame):
    """
    Single chat item in the list.
    Shows title, preview text, and timestamp.
    Can be pinned and selected.
    """

    def __init__(self, parent, chat_id: str, title: str, preview: str = "",
                 timestamp: datetime = None, pinned: bool = False,
                 on_click=None, on_pin=None, active: bool = False, **kwargs):
        super().__init__(
            parent,
            fg_color=Colors.BG_SURFACE if active else "transparent",
            corner_radius=Sizing.RADIUS_MD,
            border_width=0,
            **kwargs
        )
        
        self.chat_id = chat_id
        self.on_click = on_click
        self.on_pin = on_pin
        self._pinned = pinned
        self._active = active
        
        self.grid_columnconfigure(0, weight=1)
        self._build(title, preview, timestamp, pinned, active)
        
        # Hover effects
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click_handler)

    def _build(self, title: str, preview: str, timestamp: datetime, pinned: bool, active: bool):
        """Build the chat item layout."""
        padx = Spacing.MD
        pady = Spacing.SM
        
        # Title row: title + pin button
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=padx, pady=(pady, 0))
        title_row.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            title_row,
            text=title,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM, weight="bold"),
            text_color=Colors.TEXT_PRIMARY if active else Colors.TEXT_SECONDARY,
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="w")
        
        # Preview text
        preview_label = None
        if preview:
            preview_label = ctk.CTkLabel(
                self,
                text=preview[:40] + ("..." if len(preview) > 40 else ""),
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            )
            preview_label.grid(row=1, column=0, sticky="ew", padx=padx, pady=(0, 2))
        
        # Timestamp
        time_label = None
        if timestamp:
            time_str = timestamp.strftime("%H:%M") if timestamp.date() == datetime.now().date() else timestamp.strftime("%b %d")
            time_label = ctk.CTkLabel(
                self,
                text=time_str,
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            )
            time_label.grid(row=2, column=0, sticky="w", padx=padx, pady=(0, pady))

        # Bind click to all child widgets so CTkFrame's internal canvas
        # does not absorb the event.
        click_targets = [self, title_row, title_label]
        if preview_label is not None:
            click_targets.append(preview_label)
        if time_label is not None:
            click_targets.append(time_label)
        for w in click_targets:
            w.bind("<Button-1>", self._on_click_handler)

    def _on_enter(self, event):
        """Handle hover enter."""
        if not self._active:
            self.configure(fg_color=Colors.BG_ELEVATED)

    def _on_leave(self, event):
        """Handle hover leave."""
        if not self._active:
            self.configure(fg_color="transparent")

    def _on_click_handler(self, event):
        """Handle click."""
        if self.on_click:
            self.on_click(self.chat_id)


class ChatList(ctk.CTkFrame):
    """
    Container for chat items.
    Supports sections: Recent and Pinned.
    """

    def __init__(self, parent, on_chat_select=None, **kwargs):
        super().__init__(
            parent,
            fg_color="transparent",
            **kwargs
        )
        
        self.on_chat_select = on_chat_select
        self._chat_items = {}
        
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        """Build the chat list layout."""
        # Pinned chats section (collapsible)
        self._pinned_section = ctk.CTkFrame(self, fg_color="transparent")
        self._pinned_section.grid(row=0, column=0, sticky="ew")
        
        self._pinned_header = self._create_section_header(
            self._pinned_section,
            "Pinned",
            row=0
        )
        
        self._pinned_list = ctk.CTkFrame(self._pinned_section, fg_color="transparent")
        self._pinned_list.grid(row=1, column=0, sticky="ew")
        
        # Recent chats section
        self._recent_section = ctk.CTkFrame(self, fg_color="transparent")
        self._recent_section.grid(row=1, column=0, sticky="ew", pady=(Spacing.SM, 0))
        
        self._recent_header = self._create_section_header(
            self._recent_section,
            "Recent",
            row=0
        )
        
        self._recent_list = ctk.CTkFrame(self._recent_section, fg_color="transparent")
        self._recent_list.grid(row=1, column=0, sticky="ew")

    def _create_section_header(self, parent, text: str, row: int):
        """Create a collapsible section header."""
        header = ctk.CTkFrame(parent, fg_color="transparent", height=24)
        header.grid(row=row, column=0, sticky="ew", padx=Spacing.MD, pady=Spacing.SM)
        
        # Section title — uppercase label to match the design system.
        title = ctk.CTkLabel(
            header,
            text=text.upper(),
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS, weight="bold"),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        )
        title.pack(side="left")

        return header

    def add_chat(self, chat_id: str, title: str, preview: str = "",
                 timestamp: datetime = None, pinned: bool = False, active: bool = False):
        """Add a chat item to the list."""
        if chat_id in self._chat_items:
            # Remove existing
            existing = self._chat_items[chat_id]
            existing.destroy()
        
        parent = self._pinned_list if pinned else self._recent_list
        item = ChatItem(
            parent,
            chat_id=chat_id,
            title=title,
            preview=preview,
            timestamp=timestamp,
            pinned=pinned,
            active=active,
            on_click=self._on_chat_click,
        )
        item.pack(fill="x", pady=1)
        self._chat_items[chat_id] = item

    def _on_chat_click(self, chat_id: str):
        """Handle chat selection."""
        # Update active states
        for cid, item in self._chat_items.items():
            item._active = (cid == chat_id)
            if cid == chat_id:
                item.configure(fg_color=Colors.BG_SURFACE)
            else:
                item.configure(fg_color="transparent")
        
        if self.on_chat_select:
            self.on_chat_select(chat_id)

    def clear(self):
        """Remove all chat items."""
        for item in self._chat_items.values():
            item.destroy()
        self._chat_items.clear()

    def set_active(self, chat_id: str):
        """Set which chat is currently active."""
        self._on_chat_click(chat_id)