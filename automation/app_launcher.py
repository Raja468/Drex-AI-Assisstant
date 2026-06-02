# ============================================================
#  DREX - AI Desktop Assistant
#  automation/app_launcher.py  —  Application Launcher
# ============================================================

import subprocess
import os
import time
import psutil
from typing import Optional
from utils.logger import logger
from utils.error_handler import AutomationError, safe_execute


APP_DATABASE = {
    # ── Browsers ──────────────────────────────────────────────
    "chrome":               ("chrome.exe",              "start chrome"),
    "google chrome":        ("chrome.exe",              "start chrome"),
    "firefox":              ("firefox.exe",             "start firefox"),
    "edge":                 ("msedge.exe",              "start msedge"),
    "microsoft edge":       ("msedge.exe",              "start msedge"),
    "brave":                ("brave.exe",               "start brave"),
    "opera":                ("opera.exe",               "start opera"),

    # ── Websites (open in default browser) ───────────────────
    "youtube":              ("",    "start https://www.youtube.com"),
    "google":               ("",    "start https://www.google.com"),
    "gmail":                ("",    "start https://mail.google.com"),
    "github":               ("",    "start https://www.github.com"),
    "facebook":             ("",    "start https://www.facebook.com"),
    "instagram":            ("",    "start https://www.instagram.com"),
    "twitter":              ("",    "start https://www.twitter.com"),
    "whatsapp web":         ("",    "start https://web.whatsapp.com"),
    "linkedin":             ("",    "start https://www.linkedin.com"),
    "reddit":               ("",    "start https://www.reddit.com"),
    "netflix":              ("",    "start https://www.netflix.com"),
    "chatgpt":              ("",    "start https://chat.openai.com"),
    "claude":               ("",    "start https://claude.ai"),
    "stackoverflow":        ("",    "start https://stackoverflow.com"),
    "amazon":               ("",    "start https://www.amazon.com"),
    "wikipedia":            ("",    "start https://www.wikipedia.org"),

    # ── Microsoft Office ──────────────────────────────────────
    "word":                 ("WINWORD.EXE",             "start winword"),
    "excel":                ("EXCEL.EXE",               "start excel"),
    "powerpoint":           ("POWERPNT.EXE",            "start powerpnt"),
    "outlook":              ("OUTLOOK.EXE",             "start outlook"),
    "teams":                ("Teams.exe",               "start teams"),
    "onenote":              ("ONENOTE.EXE",             "start onenote"),

    # ── Development ───────────────────────────────────────────
    "vs code":              ("Code.exe",                "code"),
    "vscode":               ("Code.exe",                "code"),
    "visual studio code":   ("Code.exe",                "code"),
    "cursor":               ("cursor.exe",              "start cursor"),
    "cursor ai":            ("cursor.exe",              "start cursor"),
    "pycharm":              ("pycharm64.exe",           "start pycharm64"),
    "terminal":             ("wt.exe",                  "start wt"),
    "windows terminal":     ("wt.exe",                  "start wt"),
    "cmd":                  ("cmd.exe",                 "start cmd"),
    "command prompt":       ("cmd.exe",                 "start cmd"),
    "powershell":           ("powershell.exe",          "start powershell"),
    "git bash":             ("bash.exe",                'start "" "C:\\Program Files\\Git\\bin\\bash.exe"'),
    "jupyter":              ("jupyter-notebook.exe",    "jupyter notebook"),
    "anaconda":             ("Anaconda Navigator.exe",  "start anaconda-navigator"),
    "postman":              ("Postman.exe",             "start postman"),

    # ── Media & Communication ─────────────────────────────────
    "spotify":              ("Spotify.exe",             "start spotify"),
    "discord":              ("Discord.exe",             "start discord"),
    "telegram":             ("Telegram.exe",            "start telegram"),
    "whatsapp":             ("WhatsApp.exe",            "start whatsapp"),
    "zoom":                 ("Zoom.exe",                "start zoom"),
    "vlc":                  ("vlc.exe",                 "start vlc"),
    "media player":         ("wmplayer.exe",            "start wmplayer"),
    "obs":                  ("obs64.exe",               "start obs64"),

    # ── System Tools ──────────────────────────────────────────
    "calculator":           ("CalculatorApp.exe",       "start calc"),
    "calc":                 ("CalculatorApp.exe",       "start calc"),
    "notepad":              ("notepad.exe",             "start notepad"),
    "paint":                ("mspaint.exe",             "start mspaint"),
    "task manager":         ("Taskmgr.exe",             "start taskmgr"),
    "settings":             ("SystemSettings.exe",      "start ms-settings:"),
    "control panel":        ("control.exe",             "start control"),
    "file explorer":        ("explorer.exe",            "start explorer"),
    "explorer":             ("explorer.exe",            "start explorer"),
    "registry editor":      ("regedit.exe",             "start regedit"),
    "snipping tool":        ("SnippingTool.exe",        "start snippingtool"),
    "clock":                ("TimeDate.CPL",            "start ms-clock:"),

    # ── Gaming ────────────────────────────────────────────────
    "steam":                ("steam.exe",               "start steam"),
    "epic games":           ("EpicGamesLauncher.exe",   "start epicgameslauncher"),

    # ── Utilities ─────────────────────────────────────────────
    "7zip":                 ("7zFM.exe",                "start 7zfm"),
    "winrar":               ("WinRAR.exe",              "start winrar"),
    "adobe reader":         ("Acrobat.exe",             "start acrobat"),
    "pdf reader":           ("Acrobat.exe",             "start acrobat"),
}


class AppLauncher:
    """
    Handles opening and closing applications on Windows.
    Supports both desktop apps and websites.
    """

    def __init__(self):
        logger.info("✅ AppLauncher initialized")

    def open_app(self, app_name: str) -> tuple[bool, str]:
        app_name = app_name.lower().strip()

        # Clean common extra words from voice input
        for phrase in ["for me", "please", "the ", "app", "application", "website"]:
            app_name = app_name.replace(phrase, "").strip()

        logger.info("🚀 Opening app: '{}'", app_name)

        # Strategy 1: Look up in known app database
        if app_name in APP_DATABASE:
            exe_name, launch_cmd = APP_DATABASE[app_name]
            success, msg = self._launch_command(launch_cmd, app_name)
            if success:
                return True, f"Opening {app_name}."
            logger.warning("DB launch failed for '{}', trying fallback...", app_name)

        # Strategy 2: Partial match — find closest key in database
        for key in APP_DATABASE:
            if app_name in key or key in app_name:
                exe_name, launch_cmd = APP_DATABASE[key]
                success, msg = self._launch_command(launch_cmd, key)
                if success:
                    return True, f"Opening {key}."

        # Strategy 3: Try 'start <name>' directly
        success, msg = self._launch_command(f"start {app_name}", app_name)
        if success:
            return True, f"Opening {app_name}."

        # Strategy 4: Try as direct executable
        try:
            subprocess.Popen(
                app_name, shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(0.5)
            return True, f"Attempting to open {app_name}."
        except Exception as e:
            logger.error("All strategies failed for '{}': {}", app_name, e)
            return False, f"I couldn't find or open '{app_name}'. Is it installed?"

    def _launch_command(self, command: str, app_name: str) -> tuple[bool, str]:
        try:
            subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            time.sleep(0.3)
            logger.debug("Launch command succeeded: '{}'", command)
            return True, "OK"
        except Exception as e:
            logger.debug("Launch command failed: '{}' → {}", command, e)
            return False, str(e)

    def close_app(self, app_name: str) -> tuple[bool, str]:
        app_name_lower = app_name.lower().strip()
        logger.info("🛑 Closing app: '{}'", app_name)

        exe_name = None
        if app_name_lower in APP_DATABASE:
            exe_name = APP_DATABASE[app_name_lower][0]

        if not exe_name:
            exe_name = app_name_lower if app_name_lower.endswith(".exe") else f"{app_name_lower}.exe"

        killed = self._taskkill(exe_name)
        if killed:
            return True, f"Closed {app_name}."

        killed = self._kill_by_process_name(app_name_lower)
        if killed:
            return True, f"Closed {app_name}."

        return False, f"'{app_name}' doesn't appear to be running."

    def _taskkill(self, exe_name: str) -> bool:
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
        killed = False
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if app_name in proc.info['name'].lower():
                    proc.kill()
                    killed = True
                    logger.info("Killed process: {} (PID {})",
                                proc.info['name'], proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return killed

    def list_running_apps(self) -> list[str]:
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
        app_name_lower = app_name.lower()
        for proc in psutil.process_iter(['name']):
            try:
                if app_name_lower in proc.info['name'].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False