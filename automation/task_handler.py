# ============================================================
#  DREX - AI Desktop Assistant
#  automation/task_handler.py  —  Automation Task Dispatcher
#
#  WHAT IT DOES:
#  Central hub for all automation. The Orchestrator calls this,
#  and it routes to the correct automation module.
#  Also handles natural language entity extraction for tasks
#  that need context (e.g., "search YouTube for lo-fi music").
# ============================================================

import re
from datetime import datetime
from typing import Optional

from utils.logger import logger
from utils.error_handler import safe_execute
from automation.app_launcher import AppLauncher
from automation.system_control import SystemControl
from automation.browser_control import BrowserControl, QUICK_SITES
from automation.file_manager import FileManager
from core.intent_parser import Intent


class TaskHandler:
    """
    Routes automation intents to the correct handler.
    Instantiated once and shared across the app.
    """

    def execute(self, intent: Intent) -> str:
        """Alias for handle() to maintain compatibility with Orchestrator."""
        return self.handle(intent)

    def __init__(self):
        self.launcher = AppLauncher()
        self.system   = SystemControl()
        self.browser  = BrowserControl()
        self.files     = FileManager()
        logger.info("✅ TaskHandler initialized (all automation modules ready)")

    # ──────────────────────────────────────────────────────────
    #  MAIN DISPATCH METHOD
    # ──────────────────────────────────────────────────────────

    def handle(self, intent: Intent) -> str:
        """
        Main entry point. Routes an automation intent to handler.

        Args:
            intent: Parsed Intent from IntentParser

        Returns:
            Response string for the user
        """
        t = intent.type
        a = intent.action

        if t == "open_app":
            return self._handle_open_app(intent)
        elif t == "close_app":
            return self._handle_close_app(intent)
        elif t == "browser":
            if a == "open_url":
                return self._handle_open_site(intent)
            else:
                return self._handle_web_search(intent)
        elif t == "time_date":
            if a == "current_time":
                return self._handle_get_time(intent)
            elif a == "current_date":
                return self._handle_get_date(intent)
        elif t == "file_manager":
            return self._handle_file_operation(intent)
        elif t == "system_control":
            return self.handle_system_action(a, intent)

        # Smart fallback — try to figure out automation from raw text
        return self._smart_fallback(intent)

    # ──────────────────────────────────────────────────────────
    #  INDIVIDUAL HANDLERS
    # ──────────────────────────────────────────────────────────

    def _handle_open_app(self, intent: Intent) -> str:
        app = intent.target or self._extract_app_from_text(intent.raw)
        if not app:
            return "Which application would you like me to open?"
        ok, msg = self.launcher.open_app(app)
        return msg

    def _handle_close_app(self, intent: Intent) -> str:
        app = intent.target or self._extract_app_from_text(intent.raw)
        if not app:
            return "Which application should I close?"
        ok, msg = self.launcher.close_app(app)
        return msg

    def _handle_web_search(self, intent: Intent) -> str:
        text = intent.raw.lower()

        # YouTube search
        if "youtube" in text:
            query = self._extract_search_query(text, remove_words=["youtube"])
            ok, msg = self.browser.youtube_search(query)
            return f"Searching YouTube for '{query}'."

        # Google Maps
        if "map" in text or "directions" in text or "navigate" in text:
            location = self._extract_location(text)
            ok, msg = self.browser.google_maps(location)
            return f"Opening maps for {location}."

        # Translate
        if "translate" in text:
            query = self._extract_search_query(text, remove_words=["translate"])
            ok, msg = self.browser.translate(query)
            return f"Opening translation for '{query}'."

        # Weather
        if "weather" in text:
            location = self._extract_location(text)
            ok, msg = self.browser.get_weather(location)
            return f"Checking weather{' for ' + location if location else ''}."

        # News
        if "news" in text:
            query = self._extract_search_query(text, remove_words=["news", "latest"])
            ok, msg = self.browser.get_news(query)
            return f"Opening news{' about ' + query if query else ''}."

        # General Google search
        query = intent.target or self._extract_search_query(text)
        if not query:
            return "What would you like me to search for?"
        ok, msg = self.browser.search(query)
        return f"Searching for '{query}'."

    def _handle_open_site(self, intent: Intent) -> str:
        site = intent.target or self._extract_site_from_text(intent.raw)
        if not site:
            return "Which website would you like to open?"
        ok, msg = self.browser.open_site(site)
        return msg

    def _handle_get_time(self, intent: Intent) -> str:
        now = datetime.now()
        return f"The current time is {now.strftime('%I:%M %p')}."

    def _handle_get_date(self, intent: Intent) -> str:
        now = datetime.now()
        return f"Today is {now.strftime('%A, %B %d, %Y')}."

    def _handle_file_operation(self, intent: Intent) -> str:
        text = intent.raw.lower()

        if "downloads" in text:
            ok, msg = self.files.open_downloads()
            return msg
        if "desktop" in text:
            ok, msg = self.files.open_desktop()
            return msg
        if "documents" in text:
            ok, msg = self.files.open_documents()
            return msg

        # Try to find a specific file
        query = self._extract_search_query(text, remove_words=["file", "find", "open", "show"])
        if query:
            results = self.files.find_file(query)
            if results:
                ok, msg = self.files.open_file(str(results[0]))
                return f"Found and {msg}"
            return f"I couldn't find a file named '{query}'."

        return "What file or folder would you like me to open?"

    def _handle_system_info(self, intent: Intent) -> str:
        return self.system.format_system_info()

    # ──────────────────────────────────────────────────────────
    #  SYSTEM ACTIONS (volume, screenshot, power)
    # ──────────────────────────────────────────────────────────

    def handle_system_action(self, sub_type: str, intent: Intent) -> str:
        """
        Handle system control actions from orchestrator.
        Called directly by the orchestrator for system intents.
        """
        text = intent.raw.lower()

        if sub_type == "volume_up":
            # Check for specific level: "set volume to 70"
            level = self._extract_number(text)
            if level is not None and "set" in text:
                ok, msg = self.system.set_volume(level)
            else:
                ok, msg = self.system.volume_up()
            return msg

        if sub_type == "volume_down":
            ok, msg = self.system.volume_down()
            return msg

        if sub_type == "mute":
            ok, msg = self.system.mute()
            return msg

        if sub_type == "screenshot":
            ok, msg = self.system.take_screenshot()
            return msg

        if sub_type == "lock":
            ok, msg = self.system.lock_screen()
            return msg

        if sub_type == "sleep":
            ok, msg = self.system.sleep()
            return msg

        if sub_type == "restart":
            ok, msg = self.system.restart()
            return msg

        if sub_type == "shutdown":
            return (
                "Are you sure you want to shut down? "
                "Say 'yes confirm shutdown' to proceed."
            )

        if sub_type == "confirm_shutdown":
            ok, msg = self.system.shutdown()
            return msg

        if sub_type == "cancel_shutdown":
            ok, msg = self.system.cancel_shutdown()
            return msg

        if sub_type == "system_info":
            return self.system.format_system_info()

        if sub_type == "clipboard_read":
            content = self.system.get_clipboard()
            if content:
                return f"Your clipboard contains: {content[:200]}"
            return "Clipboard is empty."

        return f"System action '{sub_type}' is not implemented yet."

    # ──────────────────────────────────────────────────────────
    #  SMART FALLBACK — Parse raw text for automation cues
    # ──────────────────────────────────────────────────────────

    def _smart_fallback(self, intent: Intent) -> str:
        """
        Last resort — scan raw text for any automation we can do.
        Tries common patterns not caught by intent parser.
        """
        text = intent.raw.lower()

        # Direct URL
        if "http" in text or ".com" in text or ".org" in text:
            url_match = re.search(r'(https?://\S+|[\w.-]+\.(com|org|net|io|dev)\S*)', text)
            if url_match:
                ok, msg = self.browser.open_url(url_match.group(0))
                return msg

        # "open [site name]" pattern for websites
        for site_name in QUICK_SITES:
            if site_name in text:
                ok, msg = self.browser.open_site(site_name)
                return msg

        return "I understood that as an automation task but I'm not sure how to handle it. Could you be more specific?"

    # ──────────────────────────────────────────────────────────
    #  TEXT ENTITY EXTRACTORS
    # ──────────────────────────────────────────────────────────

    def _extract_app_from_text(self, text: str) -> Optional[str]:
        """Extract app name from phrases like 'open spotify please'."""
        patterns = [
            r"open\s+(.+?)(?:\s+for\s+me|\s+please|$)",
            r"launch\s+(.+?)(?:\s+please|$)",
            r"start\s+(.+?)(?:\s+please|$)",
            r"close\s+(.+?)(?:\s+please|$)",
            r"quit\s+(.+?)(?:\s+please|$)",
        ]
        text_lower = text.lower()
        for pattern in patterns:
            m = re.search(pattern, text_lower)
            if m:
                return m.group(1).strip()
        return None

    def _extract_search_query(self, text: str, remove_words: list = None) -> str:
        """Extract search query from common phrase patterns."""
        patterns = [
            r"search(?:\s+for)?\s+(.+)",
            r"look\s+up\s+(.+)",
            r"google\s+(.+)",
            r"find\s+(.+?)(?:\s+online)?$",
            r"what\s+is\s+(.+)",
            r"who\s+is\s+(.+)",
        ]
        text_lower = text.lower()
        for pattern in patterns:
            m = re.search(pattern, text_lower)
            if m:
                query = m.group(1).strip()
                if remove_words:
                    for word in remove_words:
                        query = query.replace(word, "").strip()
                return query
        return text  # fallback: use full text

    def _extract_location(self, text: str) -> str:
        """Extract location from phrases like 'weather in London'."""
        patterns = [
            r"(?:in|for|at|near)\s+([A-Za-z\s,]+?)(?:\s+weather|\s+map|$)",
            r"weather\s+in\s+(.+)",
            r"navigate\s+to\s+(.+)",
            r"directions\s+to\s+(.+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    def _extract_site_from_text(self, text: str) -> Optional[str]:
        """Extract website name from 'open youtube' type phrases."""
        patterns = [
            r"open\s+(.+?)(?:\s+website|\s+site|\s+page|$)",
            r"go\s+to\s+(.+)",
            r"visit\s+(.+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text.lower())
            if m:
                return m.group(1).strip()
        return None

    def _extract_number(self, text: str) -> Optional[int]:
        """Extract a number from text (for volume level, etc.)."""
        m = re.search(r'\b(\d+)\b', text)
        if m:
            return int(m.group(1))
        return None
