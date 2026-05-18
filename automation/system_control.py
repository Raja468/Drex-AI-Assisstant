# ============================================================
#  DREX - AI Desktop Assistant
#  automation/system_control.py  —  Windows System Controller
#
#  WHAT IT DOES:
#  Controls low-level Windows system functions:
#    - Volume (up, down, mute, set exact level)
#    - Screenshots (full screen, active window)
#    - Shutdown / Restart / Sleep / Lock
#    - Clipboard (copy, paste, read)
#    - System info (CPU, RAM, battery, uptime)
#
#  USAGE:
#    from automation.system_control import SystemControl
#    ctrl = SystemControl()
#    ctrl.volume_up()
#    ctrl.take_screenshot()
#    ctrl.get_system_info()
# ============================================================

import os
import time
import subprocess
import platform
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from utils.logger import logger
from utils.error_handler import AutomationError, safe_execute

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not installed. System info features limited.")

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort automation
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logger.warning("pyautogui not installed. Screenshot/automation limited.")


class SystemControl:
    """
    Controls Windows system-level functions.
    All methods return (success: bool, message: str).
    """

    SCREENSHOTS_DIR = Path("screenshots")

    def __init__(self):
        self.SCREENSHOTS_DIR.mkdir(exist_ok=True)
        logger.info("✅ SystemControl initialized")

    # ──────────────────────────────────────────────────────────
    #  VOLUME CONTROL
    # ──────────────────────────────────────────────────────────

    def volume_up(self, steps: int = 2) -> tuple[bool, str]:
        """Increase system volume."""
        if not PYAUTOGUI_AVAILABLE:
            return False, "pyautogui not installed."
        try:
            for _ in range(steps):
                pyautogui.press("volumeup")
            logger.info(f"Volume increased ({steps} steps)")
            return True, "Volume increased."
        except Exception as e:
            logger.error(f"volume_up failed: {e}")
            return False, "Couldn't change volume."

    def volume_down(self, steps: int = 2) -> tuple[bool, str]:
        """Decrease system volume."""
        if not PYAUTOGUI_AVAILABLE:
            return False, "pyautogui not installed."
        try:
            for _ in range(steps):
                pyautogui.press("volumedown")
            logger.info(f"Volume decreased ({steps} steps)")
            return True, "Volume decreased."
        except Exception as e:
            logger.error(f"volume_down failed: {e}")
            return False, "Couldn't change volume."

    def mute(self) -> tuple[bool, str]:
        """Toggle mute/unmute."""
        if not PYAUTOGUI_AVAILABLE:
            return False, "pyautogui not installed."
        try:
            pyautogui.press("volumemute")
            return True, "Muted."
        except Exception as e:
            return False, "Couldn't mute."

    def set_volume(self, level: int) -> tuple[bool, str]:
        """
        Set volume to an exact percentage (0-100).
        Uses PowerShell for precise control.
        """
        level = max(0, min(100, level))
        try:
            # PowerShell command to set exact volume level
            ps_cmd = (
                f"$obj = New-Object -ComObject WScript.Shell; "
                f"1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}; "
                f"1..{level // 2} | ForEach-Object {{ $obj.SendKeys([char]175) }}"
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logger.info(f"Volume set to {level}%")
            return True, f"Volume set to {level} percent."
        except Exception as e:
            logger.error(f"set_volume failed: {e}")
            return False, f"Couldn't set volume to {level}%."

    # ──────────────────────────────────────────────────────────
    #  SCREENSHOTS
    # ──────────────────────────────────────────────────────────

    def take_screenshot(self, filename: Optional[str] = None) -> tuple[bool, str]:
        """
        Capture the full screen and save it.

        Args:
            filename: Optional custom filename. Auto-generated if None.

        Returns:
            (success, message with filename)
        """
        if not PYAUTOGUI_AVAILABLE:
            return self._screenshot_powershell(filename)

        try:
            if not filename:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{ts}.png"

            filepath = self.SCREENSHOTS_DIR / filename
            screenshot = pyautogui.screenshot()
            screenshot.save(str(filepath))

            logger.info(f"📸 Screenshot saved: {filepath}")
            return True, f"Screenshot saved as {filename}."

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False, "Couldn't take screenshot."

    def _screenshot_powershell(self, filename: Optional[str] = None) -> tuple[bool, str]:
        """Fallback screenshot using PowerShell."""
        try:
            if not filename:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{ts}.png"
            filepath = self.SCREENSHOTS_DIR / filename

            ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms;
$screen = [System.Windows.Forms.Screen]::PrimaryScreen;
$bitmap = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height);
$graphics = [System.Drawing.Graphics]::FromImage($bitmap);
$graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size);
$bitmap.Save('{filepath}');
"""
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True, f"Screenshot saved as {filename}."
        except Exception as e:
            logger.error(f"PowerShell screenshot failed: {e}")
            return False, "Screenshot failed."

    # ──────────────────────────────────────────────────────────
    #  POWER MANAGEMENT
    # ──────────────────────────────────────────────────────────

    def shutdown(self, delay_seconds: int = 5) -> tuple[bool, str]:
        """Shut down Windows after a delay."""
        try:
            subprocess.run(
                f"shutdown /s /t {delay_seconds}",
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logger.info(f"Shutdown scheduled in {delay_seconds}s")
            return True, f"Shutting down in {delay_seconds} seconds."
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
            return False, "Shutdown failed."

    def cancel_shutdown(self) -> tuple[bool, str]:
        """Cancel a scheduled shutdown."""
        try:
            subprocess.run(
                "shutdown /a",
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True, "Shutdown cancelled."
        except Exception as e:
            return False, "Couldn't cancel shutdown."

    def restart(self, delay_seconds: int = 5) -> tuple[bool, str]:
        """Restart Windows after a delay."""
        try:
            subprocess.run(
                f"shutdown /r /t {delay_seconds}",
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True, f"Restarting in {delay_seconds} seconds."
        except Exception as e:
            return False, "Restart failed."

    def sleep(self) -> tuple[bool, str]:
        """Put computer to sleep."""
        try:
            subprocess.run(
                "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True, "Going to sleep."
        except Exception as e:
            return False, "Sleep failed."

    def lock_screen(self) -> tuple[bool, str]:
        """Lock the Windows screen."""
        try:
            subprocess.run(
                "rundll32.exe user32.dll,LockWorkStation",
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True, "Screen locked."
        except Exception as e:
            return False, "Couldn't lock screen."

    # ──────────────────────────────────────────────────────────
    #  CLIPBOARD
    # ──────────────────────────────────────────────────────────

    def get_clipboard(self) -> Optional[str]:
        """Read current clipboard content."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.stdout.strip()
        except Exception as e:
            logger.error(f"Clipboard read failed: {e}")
            return None

    def set_clipboard(self, text: str) -> tuple[bool, str]:
        """Copy text to clipboard."""
        try:
            subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{text}'"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True, "Copied to clipboard."
        except Exception as e:
            return False, "Clipboard copy failed."

    # ──────────────────────────────────────────────────────────
    #  SYSTEM INFORMATION
    # ──────────────────────────────────────────────────────────

    def get_system_info(self) -> dict:
        """
        Returns a dict of current system statistics.
        Useful for: "How's my PC doing?" type questions.
        """
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "cpu_percent": None,
            "ram_used_gb": None,
            "ram_total_gb": None,
            "ram_percent": None,
            "battery_percent": None,
            "battery_plugged": None,
            "uptime_hours": None,
            "disk_free_gb": None,
        }

        if not PSUTIL_AVAILABLE:
            return info

        try:
            info["cpu_percent"] = psutil.cpu_percent(interval=1)

            ram = psutil.virtual_memory()
            info["ram_used_gb"] = round(ram.used / (1024**3), 1)
            info["ram_total_gb"] = round(ram.total / (1024**3), 1)
            info["ram_percent"] = ram.percent

            # Battery (may not exist on desktops)
            battery = psutil.sensors_battery()
            if battery:
                info["battery_percent"] = round(battery.percent)
                info["battery_plugged"] = battery.power_plugged

            # Uptime
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            info["uptime_hours"] = round(uptime_seconds / 3600, 1)

            # Disk space (C drive)
            disk = psutil.disk_usage("C:\\" if os.name == "nt" else "/")
            info["disk_free_gb"] = round(disk.free / (1024**3), 1)

        except Exception as e:
            logger.error(f"System info error: {e}")

        return info

    def format_system_info(self) -> str:
        """Returns a human-readable system status string."""
        info = self.get_system_info()
        parts = []

        if info["cpu_percent"] is not None:
            parts.append(f"CPU is at {info['cpu_percent']}%")

        if info["ram_percent"] is not None:
            parts.append(
                f"RAM is {info['ram_percent']}% used "
                f"({info['ram_used_gb']}GB of {info['ram_total_gb']}GB)"
            )

        if info["battery_percent"] is not None:
            plugged = "plugged in" if info["battery_plugged"] else "on battery"
            parts.append(f"Battery is at {info['battery_percent']}%, {plugged}")

        if info["disk_free_gb"] is not None:
            parts.append(f"{info['disk_free_gb']}GB free on disk")

        if info["uptime_hours"] is not None:
            parts.append(f"System has been running for {info['uptime_hours']} hours")

        return ". ".join(parts) + "." if parts else "System info unavailable."

    # ──────────────────────────────────────────────────────────
    #  KEYBOARD SHORTCUTS
    # ──────────────────────────────────────────────────────────

    def press_key(self, key: str) -> tuple[bool, str]:
        """Press a keyboard key or shortcut."""
        if not PYAUTOGUI_AVAILABLE:
            return False, "pyautogui not installed."
        try:
            pyautogui.press(key)
            return True, f"Pressed {key}."
        except Exception as e:
            return False, f"Couldn't press {key}."

    def hotkey(self, *keys) -> tuple[bool, str]:
        """Press a keyboard combination (e.g., ctrl+c)."""
        if not PYAUTOGUI_AVAILABLE:
            return False, "pyautogui not installed."
        try:
            pyautogui.hotkey(*keys)
            return True, f"Pressed {'+'.join(keys)}."
        except Exception as e:
            return False, f"Hotkey failed: {e}"

    def type_text(self, text: str, interval: float = 0.02) -> tuple[bool, str]:
        """Type text using keyboard simulation."""
        if not PYAUTOGUI_AVAILABLE:
            return False, "pyautogui not installed."
        try:
            pyautogui.write(text, interval=interval)
            return True, "Text typed."
        except Exception as e:
            return False, f"Typing failed: {e}"


# ─────────────────────────────────────────────────────────────
#  QUICK TEST
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from utils.logger import setup_logger
    setup_logger()

    ctrl = SystemControl()

    print("📊 System Info:")
    print(ctrl.format_system_info())

    print("\n📸 Taking screenshot...")
    ok, msg = ctrl.take_screenshot()
    print(msg)
