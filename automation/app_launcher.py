# ============================================================
#  DREX - AI Desktop Assistant
#  automation/app_launcher.py  —  Application Launcher
#
#  WHAT IT DOES:
#  Opens, closes, and manages Windows applications.
#  Knows about common apps and can also try unknown ones.
#
#  USAGE:
#    from automation.app_launcher import AppLauncher
#    launcher = AppLauncher()
#    launcher.open_app("chrome")
#    launcher.close_app("notepad")
#    launcher.list_running_apps()
# ============================================================

import subprocess
import os
import time
import psutil
from typing import Optional
from utils.logger import logger
from utils.error_handler import AutomationError, safe_execute


# ─────────────────────────────────────────────────────────────
#  APP DATABASE — spoken name → (executable, search_strategy)
# ─────────────────────────────────────────────────────────────

APP_DATABASE = {
    # ── Browsers ──────────────────────────────────────────────
    "chrome":           ("chrome.exe",          "start chrome"),
    "google chrome":    ("chrome.exe",          "start chrome"),
    "firefox":          ("firefox.exe",         "start firefox"),
    "edge":             ("msedge.exe",          "start msedge"),
    "microsoft edge":   ("msedge.exe",          "start msedge"),
    "brave":            ("brave.exe",           "start brave"),
    "opera":            ("opera.exe",           "start opera"),

    # ── Microsoft Office ──────────────────────────────────────
    "word":             ("WINWORD.EXE",         "start winword"),
    "excel":            ("EXCEL.EXE",           "start excel"),
    "powerpoint":       ("POWERPNT.EXE",        "start powerpnt"),
    "outlook":          ("OUTLOOK.EXE",         "start outlook"),
    "teams":            ("Teams.exe",           "start teams"),
    "onenote":          ("ONENOTE.EXE",         "start onenote"),

    # ── Development ───────────────────────────────────────────
    "vs code":          ("Code.exe",            "code"),
    "vscode":           ("Code.exe",            "code"),
    "visual studio code": ("Code.exe",          "code"),
    "pycharm":          ("pycharm64.exe",       "start pycharm64"),
    "terminal":         ("wt.exe",              "start wt"),
    "windows terminal": ("wt.exe",              "start wt"),
    "cmd":              ("cmd.exe",             "start cmd"),
    "command prompt":   ("cmd.exe",             "start cmd"),
    "powershell":       ("powershell.exe",      "start powershell"),
    "git bash":         ("bash.exe",            'start "" "C:\\Program Files\\Git\\bin\\bash.exe"'),
    "jupyter":          ("jupyter-notebook.exe","jupyter notebook"),
    "anaconda":         ("Anaconda Navigator.exe", "start anaconda-navigator"),

    # ── Media & Communication ─────────────────────────────────
    "spotify":          ("Spotify.exe",         "start spotify"),
    "discord":          ("Discord.exe",         "start discord"),
    "telegram":         ("Telegram.exe",        "start telegram"),
    "whatsapp":         ("WhatsApp.exe",        "start whatsapp"),
    "zoom":             ("Zoom.exe",            "start zoom"),
    "vlc":              ("vlc.exe",             "start vlc"),
    "media player":     ("wmplayer.exe",        "start wmplayer"),
    "netflix":          ("netflix.exe",         "start ms-windows-store:"),
    "obs":              ("obs64.exe",           "start obs64"),

    # ── System Tools ──────────────────────────────────────────
    "calculator":       ("CalculatorApp.exe",   "start calc"),
    "calc":             ("CalculatorApp.exe",   "start calc"),
    "notepad":          ("notepad.exe",         "start notepad"),
    "paint":            ("mspaint.exe",         "start mspaint"),
    "task manager":     ("Taskmgr.exe",         "start taskmgr"),
    "settings":         ("SystemSettings.exe",  "start ms-settings:"),
    "control panel":    ("control.exe",         "start control"),
    "file explorer":    ("explorer.exe",        "start explorer"),
    "explorer":         ("explorer.exe",        "start explorer"),
    "registry editor":  ("regedit.exe",         "start regedit"),
    "snipping tool":    ("SnippingTool.exe",    "start snippingtool"),
    "clock":            ("TimeDate.CPL",        "start ms-clock:"),

    # ── Gaming ────────────────────────────────────────────────
    "steam":            ("steam.exe",           "start steam"),
    "epic games":       ("EpicGamesLauncher.exe","start epicgameslauncher"),

    # ── Utilities ─────────────────────────────────────────────
    "7zip":             ("7zFM.exe",            "start 7zfm"),
    "winrar":           ("WinRAR.exe",          "start winrar"),
    "adobe reader":     ("Acrobat.exe",         "start acrobat"),
    "pdf reader":       ("Acrobat.exe",         "start acrobat"),
}


class AppLauncher:
    """
    Handles opening and closing applications on Windows.
    
    Uses multiple strategies to open apps:
    1. Direct database lookup (fastest)
    2. Shell 'start' command
    3. subprocess.Popen
    """

    def __init__(self):
        logger.info("✅ AppLauncher initialized")

    # ── Open Application ──────────────────────────────────────

    def open_app(self, app_name: str) -> tuple[bool, str]:
        """
        Open an application by name.

        Args:
            app_name: Name of the app (e.g., "chrome", "notepad")

        Returns:
            (success: bool, message: str)
        """
        app_name = app_name.lower().strip()
        logger.info(f"🚀 Opening app: '{app_name}'")

        # Strategy 1: Look up in known app database
        if app_name in APP_DATABASE:
            exe_name, launch_cmd = APP_DATABASE[app_name]
            success, msg = self._launch_command(launch_cmd, app_name)
            if success:
                return True, f"Opening {app_name}."
            logger.warning(f"DB launch failed for '{app_name}', trying fallback...")

        # Strategy 2: Try 'start <name>' directly (Windows shell)
        success, msg = self._launch_command(f"start {app_name}", app_name)
        if success:
            return True, f"Opening {app_name}."

        # Strategy 3: Try running it as a direct executable
        try:
            subprocess.Popen(app_name, shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            return True, f"Attempting to open {app_name}."
        except Exception as e:
            logger.error(f"All strategies failed for '{app_name}': {e}")
            return False, f"I couldn't find or open '{app_name}'. Is it installed?"

    def _launch_command(self, command: str, app_name: str) -> tuple[bool, str]:
        """Run a shell command to launch an app."""
        try:
            subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            time.sleep(0.3)  # Short pause to let it start
            logger.debug(f"Launch command succeeded: '{command}'")
            return True, "OK"
        except Exception as e:
            logger.debug(f"Launch command failed: '{command}' → {e}")
            return False, str(e)

    # ── Close Application ─────────────────────────────────────

    def close_app(self, app_name: str) -> tuple[bool, str]:
        """
        Close a running application by name.

        Args:
            app_name: Name or executable name of the app

        Returns:
            (success: bool, message: str)
        """
        app_name_lower = app_name.lower().strip()
        logger.info(f"🛑 Closing app: '{app_name}'")

        # Get executable name from database if known
        exe_name = None
        if app_name_lower in APP_DATABASE:
            exe_name = APP_DATABASE[app_name_lower][0]

        # If not in DB, guess the exe name
        if not exe_name:
            exe_name = app_name_lower if app_name_lower.endswith(".exe") else f"{app_name_lower}.exe"

        # Try taskkill first (cleanest method)
        killed = self._taskkill(exe_name)
        if killed:
            return True, f"Closed {app_name}."

        # Fallback: search all running processes by name
        killed = self._kill_by_process_name(app_name_lower)
        if killed:
            return True, f"Closed {app_name}."

        return False, f"'{app_name}' doesn't appear to be running."

    def _taskkill(self, exe_name: str) -> bool:
        """Use Windows taskkill command."""
        try:
            result = subprocess.run(
                f"taskkill /f /im {exe_name}",
                shell=True,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False

    def _kill_by_process_name(self, app_name: str) -> bool:
        """Search running processes and kill matching ones."""
        killed = False
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if app_name in proc.info['name'].lower():
                    proc.kill()
                    killed = True
                    logger.info(f"Killed process: {proc.info['name']} (PID {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return killed

    # ── Running App Info ──────────────────────────────────────

    def list_running_apps(self) -> list[str]:
        """
        Returns a list of currently running application names.
        Filters out system processes, shows only user apps.
        """
        SYSTEM_PROCESSES = {
            'system', 'svchost.exe', 'csrss.exe', 'wininit.exe',
            'services.exe', 'lsass.exe', 'smss.exe', 'registry',
            'memory compression', 'dwm.exe', 'winlogon.exe',
        }
        apps = set()
        for proc in psutil.process_iter(['name', 'status']):
            try:
                name = proc.info['name'].lower()
                if (proc.info['status'] == 'running' and
                        name not in SYSTEM_PROCESSES and
                        not name.startswith('runtime')):
                    apps.add(proc.info['name'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return sorted(list(apps))

    def is_app_running(self, app_name: str) -> bool:
        """Check if a specific app is currently running."""
        app_name_lower = app_name.lower()
        for proc in psutil.process_iter(['name']):
            try:
                if app_name_lower in proc.info['name'].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False


# ─────────────────────────────────────────────────────────────
#  QUICK TEST
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from utils.logger import setup_logger
    setup_logger()

    launcher = AppLauncher()

    print("Running apps:")
    for app in launcher.list_running_apps()[:10]:
        print(f"  • {app}")

    print("\nTesting: open notepad")
    ok, msg = launcher.open_app("notepad")
    print(f"Result: {msg}")
    time.sleep(2)

    print("Testing: close notepad")
    ok, msg = launcher.close_app("notepad")
    print(f"Result: {msg}")
