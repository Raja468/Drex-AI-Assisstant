"""
core/fast_router.py — Pre-AI Fast Command Router for DREX

Intercepts simple commands before they hit the AI.
Resolves in < 100ms for matched commands.
Uses existing automation modules — no duplicate logic.
"""

import re
import time
from datetime import datetime
from loguru import logger
from automation.app_launcher import AppLauncher
from automation.system_control import SystemControl


class FastRouter:
    """
    Intercepts simple commands and executes them instantly
    without calling any AI provider.
    Target: < 100ms for matched commands.
    """

    INSTANT_COMMANDS = {
        # ── Time/Date ──────────────────────────────────────────
        r"what(?:'s| is) the time": "_get_time",
        r"what(?:'s| is) (today's )?date": "_get_date",
        r"what day is it": "_get_date",

        # ── App launching ──────────────────────────────────────
        r"open (chrome|browser)": "_open_chrome",
        r"open (vs ?code|visual studio code)": "_open_vscode",
        r"open (notepad)": "_open_notepad",
        r"open (calculator|calc)": "_open_calculator",
        r"open (spotify)": "_open_spotify",
        r"open (discord)": "_open_discord",
        r"open (whatsapp)": "_open_whatsapp",
        r"open (gmail)": "_open_gmail",
        r"open (github)": "_open_github",
        r"open (youtube)": "_open_youtube",

        # ── System ─────────────────────────────────────────────
        # NOTE (safety fix): screenshot was removed from the instant
        # commands on purpose. FastRouter runs before any permission
        # check, so a screenshot here bypassed the DANGEROUS
        # classification in core/permission.py. Screenshots now fall
        # through to the gated automation/intent path, which asks for
        # confirmation. Do not re-add it here without a permission gate.
        r"what(?:'s| is) (my )?(battery|battery level)": "_get_battery",
        r"(what(?:'s| is)|show) (my )?ip( address)?": "_get_ip",
        r"(increase|turn up) volume": "_volume_up",
        r"(decrease|turn down|lower) volume": "_volume_down",
        r"mute( volume)?": "_volume_mute",
    }

    def __init__(self):
        self._app_launcher = AppLauncher()
        self._sys_ctrl = SystemControl()
        self._patterns: list[tuple[re.Pattern, str]] = [
            (re.compile(pattern, re.IGNORECASE), method)
            for pattern, method in self.INSTANT_COMMANDS.items()
        ]
        logger.info("FastRouter ready ({} patterns)", len(self._patterns))

    def match(self, user_input: str) -> tuple[str | None, tuple]:
        """
        Returns (method_name, match_groups) if command matched, (None, ()) otherwise.

        Args:
            user_input: The raw text from the user.

        Returns:
            Tuple of (method_name or None, matched groups as tuple).
        """
        user_input = user_input.strip()
        for pattern, method in self._patterns:
            m = pattern.search(user_input)
            if m:
                logger.debug("FastRouter matched '{}' → {}", user_input, method)
                return method, m.groups()
        return None, ()

    def execute(self, method_name: str, match_groups: tuple) -> str:
        """
        Executes the matched command and returns response string.

        Args:
            method_name: The handler method name (e.g. '_get_time').
            match_groups: The regex match groups tuple.

        Returns:
            A plain string response (no AI calls).
        """
        # Fail-closed: even a direct execute() call must not take a
        # screenshot from the permission-free fast path.
        if method_name == "_take_screenshot":
            return "Screenshot is not available as an instant command — it needs confirmation through the gated automation path."
        handler = getattr(self, method_name, None)
        if handler is None:
            logger.warning("FastRouter: no handler for '{}'", method_name)
            return "I don't know how to handle that yet."
        return handler(match_groups)

    # ── Time/Date handlers ───────────────────────────────────

    def _get_time(self, _groups: tuple) -> str:
        return f"It's {datetime.now().strftime('%I:%M %p')}."

    def _get_date(self, _groups: tuple) -> str:
        return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

    # ── App launch handlers ──────────────────────────────────

    def _open_chrome(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("chrome")
        return msg

    def _open_vscode(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("vs code")
        return msg

    def _open_notepad(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("notepad")
        return msg

    def _open_calculator(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("calculator")
        return msg

    def _open_spotify(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("spotify")
        return msg

    def _open_discord(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("discord")
        return msg

    def _open_whatsapp(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("whatsapp")
        return msg

    def _open_gmail(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("gmail")
        return msg

    def _open_github(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("github")
        return msg

    def _open_youtube(self, groups: tuple) -> str:
        success, msg = self._app_launcher.open_app("youtube")
        return msg

    # ── System handlers ──────────────────────────────────────

    def _take_screenshot(self, _groups: tuple) -> str:
        success, msg = self._sys_ctrl.take_screenshot()
        return msg

    def _get_battery(self, _groups: tuple) -> str:
        info = self._sys_ctrl.get_system_info()
        if info.get("battery_percent") is not None:
            plugged = "plugged in" if info["battery_plugged"] else "on battery"
            return f"Your battery is at {info['battery_percent']}%, {plugged}."
        return "I don't see a battery on this system — it may be a desktop."

    def _get_ip(self, _groups: tuple) -> str:
        import socket
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return f"Your IP address is {ip}."
        except Exception:
            return "I couldn't determine your IP address."

    def _volume_up(self, _groups: tuple) -> str:
        success, msg = self._sys_ctrl.volume_up()
        return msg

    def _volume_down(self, _groups: tuple) -> str:
        success, msg = self._sys_ctrl.volume_down()
        return msg

    def _volume_mute(self, _groups: tuple) -> str:
        success, msg = self._sys_ctrl.mute()
        return msg