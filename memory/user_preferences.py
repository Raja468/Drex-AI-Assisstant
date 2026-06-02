"""
memory/user_preferences.py — User Preferences Management for DREX

Manages user preferences, settings, and personalization data.
Provides a typed interface on top of the raw preference storage.

Features:
  - Get/set preferences with type coercion
  - Preference change tracking
  - Preference categories and defaults
  - Preference export/import support
  - Cross-session preference persistence
"""

from datetime import datetime
from typing import Any, Optional
from loguru import logger
from config import get_config


# Preference key constants
PREF_USER_NAME = "user_name"
PREF_PERSONALITY = "personality_mode"
PREF_VOICE_MODE = "voice_enabled"
PREF_TTS_ENGINE = "tts_engine"
PREF_THEME = "theme"
PREF_WAKE_WORD = "wake_word"
PREF_LAST_SESSION = "last_session_time"


class UserPreferences:
    """
    User preferences manager with typed access.

    Provides a clean interface for reading and writing user
    preferences with proper type handling and change tracking.
    """

    def __init__(self, db_manager=None):
        self.db = db_manager
        self.cfg = get_config()
        self._changed_keys: set = set()
        logger.info("✅ UserPreferences initialized")

    # ── Typed accessors ───────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Get a preference value with a default fallback."""
        if not self.db:
            return default
        return self.db.get_preference(key, default)

    def set(self, key: str, value: Any):
        """Set a preference value and track the change."""
        if not self.db:
            return
        old_value = self.get(key)
        self.db.set_preference(key, value)
        if old_value != value:
            self._changed_keys.add(key)
            logger.debug("Preference '{}' changed: {} -> {}", key, old_value, value)

    def delete(self, key: str):
        """Delete a preference by setting it to None."""
        self.set(key, None)

    # ── Named preference accessors ────────────────────────

    @property
    def user_name(self) -> str:
        return self.get(PREF_USER_NAME, "User")

    @user_name.setter
    def user_name(self, name: str):
        self.set(PREF_USER_NAME, name)

    @property
    def personality(self) -> str:
        return self.get(PREF_PERSONALITY, "jarvis")

    @personality.setter
    def personality(self, mode: str):
        self.set(PREF_PERSONALITY, mode)

    @property
    def voice_enabled(self) -> bool:
        return bool(self.get(PREF_VOICE_MODE, True))

    @voice_enabled.setter
    def voice_enabled(self, enabled: bool):
        self.set(PREF_VOICE_MODE, enabled)

    @property
    def tts_engine(self) -> str:
        return self.get(PREF_TTS_ENGINE, "pyttsx3")

    @tts_engine.setter
    def tts_engine(self, engine: str):
        self.set(PREF_TTS_ENGINE, engine)

    @property
    def theme(self) -> str:
        return self.get(PREF_THEME, "dark")

    @theme.setter
    def theme(self, theme: str):
        self.set(PREF_THEME, theme)

    # ── Bulk operations ───────────────────────────────────

    def get_all(self) -> dict:
        """Get all preferences as a dictionary."""
        if not self.db:
            return {}
        return self.db.get_all_preferences()

    def set_multiple(self, prefs: dict):
        """Set multiple preferences at once."""
        for key, value in prefs.items():
            self.set(key, value)

    def export(self) -> dict:
        """Export all preferences for backup/sharing."""
        return {
            "version": 1,
            "exported_at": datetime.now().isoformat(),
            "preferences": self.get_all(),
        }

    def import_prefs(self, data: dict):
        """Import preferences from an export dict."""
        prefs = data.get("preferences", {})
        if prefs:
            self.set_multiple(prefs)
            logger.info("Imported {} preferences", len(prefs))

    # ── Change tracking ───────────────────────────────────

    @property
    def changed_keys(self) -> set:
        """Get the set of keys changed since last reset."""
        return self._changed_keys.copy()

    def reset_tracking(self):
        """Reset the change tracking set."""
        self._changed_keys.clear()

    def shutdown(self):
        """Clean up resources."""
        logger.info("UserPreferences shutdown")