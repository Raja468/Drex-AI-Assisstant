# ============================================================
#  DREX - AI Desktop Assistant
#  gui/provider_selector.py  —  AI Provider Selector
#
#  WHAT IT DOES:
#  UI for selecting AI provider and model.
#  Supports dynamic provider configuration.
#
#  DESIGN: Flat design, dropdown selectors
# ============================================================

import customtkinter as ctk
from gui.theme import Colors, Fonts, Sizing, Spacing


class ProviderSelector(ctk.CTkFrame):
    """
    Provider and model selector component.
    Allows switching between AI providers and their models.
    """

    def __init__(self, parent, providers: dict = None,
                 on_provider_change=None, on_model_change=None, **kwargs):
        """
        Args:
            parent: Parent widget
            providers: Dict of {provider_name: {"models": [...], "enabled": bool}}
            on_provider_change: Callback when provider changes
            on_model_change: Callback when model changes
        """
        super().__init__(
            parent,
            fg_color="transparent",
            **kwargs
        )
        
        self.providers = providers or {}
        self.on_provider_change = on_provider_change
        self.on_model_change = on_model_change
        self._current_provider = ""
        self._current_model = ""
        
        self.grid_columnconfigure(1, weight=1)
        self._build()

    def _build(self):
        """Build provider selector layout."""
        # Provider dropdown
        provider_label = ctk.CTkLabel(
            self,
            text="Provider:",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_SECONDARY,
            width=70,
        )
        provider_label.grid(row=0, column=0, sticky="w", padx=(0, Spacing.SM))
        
        self._provider_menu = ctk.CTkOptionMenu(
            self,
            values=[],
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_ELEVATED,
            button_hover_color=Colors.BG_OVERLAY,
            dropdown_fg_color=Colors.BG_SURFACE,
            dropdown_hover_color=Colors.BG_ELEVATED,
            text_color=Colors.TEXT_PRIMARY,
            command=self._on_provider_selected,
        )
        self._provider_menu.grid(row=0, column=1, sticky="ew", padx=(0, Spacing.MD))
        
        # Model dropdown
        model_label = ctk.CTkLabel(
            self,
            text="Model:",
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            text_color=Colors.TEXT_SECONDARY,
            width=50,
        )
        model_label.grid(row=0, column=2, sticky="w", padx=(0, Spacing.SM))
        
        self._model_menu = ctk.CTkOptionMenu(
            self,
            values=[],
            font=ctk.CTkFont(family=Fonts.PRIMARY, size=Fonts.SM),
            fg_color=Colors.BG_ELEVATED,
            button_color=Colors.BG_ELEVATED,
            button_hover_color=Colors.BG_OVERLAY,
            dropdown_fg_color=Colors.BG_SURFACE,
            dropdown_hover_color=Colors.BG_ELEVATED,
            text_color=Colors.TEXT_PRIMARY,
            command=self._on_model_selected,
        )
        self._model_menu.grid(row=0, column=3, sticky="ew")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(3, weight=1)

    def set_providers(self, providers: dict):
        """
        Update available providers.
        
        Args:
            providers: Dict of {provider_name: {"models": [...], "enabled": bool}}
        """
        self.providers = providers
        provider_names = [p for p, info in providers.items() if info.get("enabled", True)]
        
        self._provider_menu.configure(values=provider_names)
        
        if provider_names:
            # Select first enabled provider
            self._provider_menu.set(provider_names[0])
            self._update_models(provider_names[0])

    def _on_provider_selected(self, provider: str):
        """Handle provider selection."""
        self._current_provider = provider
        self._update_models(provider)
        
        if self.on_provider_change:
            self.on_provider_change(provider)

    def _update_models(self, provider: str):
        """Update model list for selected provider."""
        if provider in self.providers:
            models = self.providers[provider].get("models", [])
            if models:
                self._model_menu.configure(values=models)
                self._model_menu.set(models[0])
                self._current_model = models[0]
            else:
                self._model_menu.configure(values=[])
                self._model_menu.set("")
                self._current_model = ""

    def _on_model_selected(self, model: str):
        """Handle model selection."""
        self._current_model = model
        
        if self.on_model_change:
            self.on_model_change(model)

    def get_selection(self) -> tuple:
        """
        Get current provider and model selection.
        
        Returns:
            Tuple of (provider, model)
        """
        return self._current_provider, self._current_model

    def set_selection(self, provider: str, model: str = ""):
        """
        Set provider and model selection programmatically.
        
        Args:
            provider: Provider name
            model: Model name (optional)
        """
        if provider and provider in self.providers:
            self._provider_menu.set(provider)
            self._current_provider = provider
            self._update_models(provider)
            
            if model and model in self.providers[provider].get("models", []):
                self._model_menu.set(model)
                self._current_model = model