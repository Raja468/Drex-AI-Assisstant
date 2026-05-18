# ============================================================
#  DREX - AI Desktop Assistant
#  automation/browser_control.py  —  Web & Browser Controller
#
#  WHAT IT DOES:
#  Controls web browsing:
#    - Search Google / YouTube / specific sites
#    - Open any URL
#    - Quick-access popular websites
#    - Weather, news, maps via browser
# ============================================================

import webbrowser
import urllib.parse
import subprocess
from typing import Optional
from utils.logger import logger


# ─────────────────────────────────────────────────────────────
#  QUICK ACCESS SITES  — "open youtube" → opens youtube.com
# ─────────────────────────────────────────────────────────────

QUICK_SITES = {
    "youtube":      "https://www.youtube.com",
    "google":       "https://www.google.com",
    "gmail":        "https://mail.google.com",
    "github":       "https://www.github.com",
    "stackoverflow": "https://stackoverflow.com",
    "reddit":       "https://www.reddit.com",
    "twitter":      "https://www.twitter.com",
    "x":            "https://www.x.com",
    "facebook":     "https://www.facebook.com",
    "instagram":    "https://www.instagram.com",
    "linkedin":     "https://www.linkedin.com",
    "netflix":      "https://www.netflix.com",
    "amazon":       "https://www.amazon.com",
    "wikipedia":    "https://www.wikipedia.org",
    "maps":         "https://maps.google.com",
    "google maps":  "https://maps.google.com",
    "translate":    "https://translate.google.com",
    "chatgpt":      "https://chat.openai.com",
    "claude":       "https://claude.ai",
    "gemini":       "https://gemini.google.com",
    "weather":      "https://weather.com",
    "news":         "https://news.google.com",
    "drive":        "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "docs":         "https://docs.google.com",
    "sheets":       "https://sheets.google.com",
    "meet":         "https://meet.google.com",
    "calendar":     "https://calendar.google.com",
    "pypi":         "https://pypi.org",
    "huggingface":  "https://huggingface.co",
}

# Search engine templates
SEARCH_ENGINES = {
    "google":    "https://www.google.com/search?q={}",
    "youtube":   "https://www.youtube.com/results?search_query={}",
    "bing":      "https://www.bing.com/search?q={}",
    "duckduckgo":"https://duckduckgo.com/?q={}",
    "github":    "https://github.com/search?q={}",
    "wikipedia": "https://en.wikipedia.org/wiki/Special:Search?search={}",
    "amazon":    "https://www.amazon.com/s?k={}",
    "reddit":    "https://www.reddit.com/search/?q={}",
    "stackoverflow": "https://stackoverflow.com/search?q={}",
}


class BrowserControl:
    """
    Handles all web and browser operations for Drex.
    """

    def __init__(self, default_engine: str = "google"):
        self.default_engine = default_engine
        logger.info("✅ BrowserControl initialized")

    # ──────────────────────────────────────────────────────────
    #  SEARCH
    # ──────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        engine: str = "google"
    ) -> tuple[bool, str]:
        """
        Search the web for a query.

        Args:
            query:  What to search for
            engine: Which search engine ("google", "youtube", "bing", etc.)

        Returns:
            (success, message)
        """
        engine = engine.lower()
        if engine not in SEARCH_ENGINES:
            engine = self.default_engine

        encoded_query = urllib.parse.quote(query)
        url = SEARCH_ENGINES[engine].format(encoded_query)

        logger.info(f"🔍 Searching [{engine}]: '{query}'")
        return self.open_url(url)

    def youtube_search(self, query: str) -> tuple[bool, str]:
        """Search YouTube specifically."""
        return self.search(query, engine="youtube")

    def google_maps(self, location: str) -> tuple[bool, str]:
        """Open Google Maps for a location."""
        encoded = urllib.parse.quote(location)
        url = f"https://maps.google.com/maps?q={encoded}"
        logger.info(f"🗺️ Opening maps for: '{location}'")
        return self.open_url(url)

    def translate(self, text: str, target_lang: str = "en") -> tuple[bool, str]:
        """Open Google Translate."""
        encoded = urllib.parse.quote(text)
        url = f"https://translate.google.com/?text={encoded}&tl={target_lang}"
        return self.open_url(url)

    # ──────────────────────────────────────────────────────────
    #  URL & SITE OPENER
    # ──────────────────────────────────────────────────────────

    def open_url(self, url: str) -> tuple[bool, str]:
        """
        Open any URL in the default browser.

        Args:
            url: Full URL to open (must include http/https)

        Returns:
            (success, message)
        """
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            webbrowser.open(url)
            logger.info(f"🌐 Opened URL: {url}")
            return True, f"Opening {url}."
        except Exception as e:
            logger.error(f"Failed to open URL '{url}': {e}")
            return False, f"Couldn't open that URL."

    def open_site(self, site_name: str) -> tuple[bool, str]:
        """
        Open a popular website by name.
        Falls back to Google search if not in the quick list.

        Args:
            site_name: Name like "youtube", "github", "reddit"

        Returns:
            (success, message)
        """
        site_lower = site_name.lower().strip()

        if site_lower in QUICK_SITES:
            url = QUICK_SITES[site_lower]
            logger.info(f"🌐 Opening site: {site_name} → {url}")
            return self.open_url(url)

        # Not in the list — try searching for it
        logger.info(f"Site '{site_name}' not in database, searching Google...")
        return self.search(site_name)

    # ──────────────────────────────────────────────────────────
    #  WEATHER / NEWS (browser-based)
    # ──────────────────────────────────────────────────────────

    def get_weather(self, location: str = "") -> tuple[bool, str]:
        """Open weather for a location."""
        if location:
            return self.search(f"weather in {location}")
        else:
            return self.open_url("https://weather.com")

    def get_news(self, topic: str = "") -> tuple[bool, str]:
        """Open news, optionally for a specific topic."""
        if topic:
            return self.search(f"{topic} news today")
        else:
            return self.open_url("https://news.google.com")


# ─────────────────────────────────────────────────────────────
#  QUICK TEST
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from utils.logger import setup_logger
    setup_logger()

    browser = BrowserControl()
    ok, msg = browser.search("Python tutorials for beginners")
    print(msg)
