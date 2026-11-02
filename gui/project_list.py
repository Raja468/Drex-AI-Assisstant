# ============================================================
#  DREX - AI Desktop Assistant
#  gui/project_list.py  —  Sidebar Project List
#
#  WHAT IT DOES:
#  Displays projects in the sidebar.
#  Each project can contain multiple chats.
#
#  DESIGN: Flat design, expandable items
# ============================================================

import customtkinter as ctk
from gui.theme import Colors, Fonts, Sizing, Spacing


class ProjectItem(ctk.CTkFrame):
    """
    Single project item.
    Expandable to show project chats.
    """

    def __init__(self, parent, project_id: str, name: str,
                 chat_count: int = 0, on_click=None, **kwargs):
        super().__init__(
            parent,
            fg_color="transparent",
            corner_radius=Sizing.RADIUS_MD,
            border_width=0,
            **kwargs
        )
        
        self.project_id = project_id
        self.on_click = on_click
        self._chat_count = chat_count
        self._expanded = False
        
        self.grid_columnconfigure(0, weight=1)
        self._build(name, chat_count)

    def _build(self, name: str, chat_count: int):
        """Build project item layout."""
        # Expand/collapse button
        self._expand_btn = ctk.CTkButton(
            self,
            text="▶",
            width=20,
            height=20,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
            fg_color="transparent",
            hover_color=Colors.BG_ELEVATED,
            text_color=Colors.TEXT_MUTED,
            corner_radius=0,
            command=self._toggle_expand,
        )
        self._expand_btn.grid(row=0, column=0, sticky="w", padx=(Spacing.SM, 4), pady=Spacing.SM)
        
        # Project name
        self._name_label = ctk.CTkLabel(
            self,
            text=name,
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
        )
        self._name_label.grid(row=0, column=1, sticky="ew", padx=(0, Spacing.SM), pady=Spacing.SM)
        
        # Chat count badge
        if chat_count > 0:
            count_label = ctk.CTkLabel(
                self,
                text=str(chat_count),
                font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS),
                text_color=Colors.TEXT_MUTED,
                width=20,
            )
            count_label.grid(row=0, column=2, sticky="e", padx=Spacing.SM, pady=Spacing.SM)

    def _toggle_expand(self):
        """Toggle expand/collapse."""
        self._expanded = not self._expanded
        self._expand_btn.configure(text="▼" if self._expanded else "▶")
        # TODO: Show/hide child chats when implemented


class ProjectList(ctk.CTkFrame):
    """
    Container for project items.
    """

    def __init__(self, parent, on_project_select=None, **kwargs):
        super().__init__(
            parent,
            fg_color="transparent",
            **kwargs
        )
        
        self.on_project_select = on_project_select
        self._projects = {}
        
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        """Build project list layout."""
        # Section header
        header = ctk.CTkFrame(self, fg_color="transparent", height=24)
        header.grid(row=0, column=0, sticky="ew", padx=Spacing.MD, pady=Spacing.SM)
        
        title = ctk.CTkLabel(
            header,
            text="PROJECTS",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.XS, weight="bold"),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        )
        title.pack(side="left")
        
        # Projects container
        self._projects_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._projects_frame.grid(row=1, column=0, sticky="ew")

    def add_project(self, project_id: str, name: str, chat_count: int = 0):
        """Add a project to the list."""
        if project_id in self._projects:
            return
        
        item = ProjectItem(
            self._projects_frame,
            project_id=project_id,
            name=name,
            chat_count=chat_count,
            on_click=lambda pid=project_id: self._on_project_click(pid),
        )
        item.pack(fill="x", pady=1)
        self._projects[project_id] = item

    def _on_project_click(self, project_id: str):
        """Handle project selection."""
        if self.on_project_select:
            self.on_project_select(project_id)

    def clear(self):
        """Remove all projects."""
        for project in self._projects.values():
            project.destroy()
        self._projects.clear()