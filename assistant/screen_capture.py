"""
DREX - AI Desktop Assistant
assistant/screen_capture.py — Screen Capture Module

Full implementation using mss for screen capture with PIL Image output.
Supports full screen, region, and window-specific captures.

Exports:
    ScreenCapture: Main class for screen capture operations
"""

__all__ = ["ScreenCapture"]

import mss
import mss.tools
from PIL import Image
from loguru import logger
from pathlib import Path
import io
import time
from typing import Optional, Tuple

# Try to import pygetwindow for window capture
try:
    import pygetwindow as gw
    GW_AVAILABLE = True
except ImportError:
    GW_AVAILABLE = False


class ScreenCapture:
    """Handles all screen capture operations for DREX."""

    def __init__(self):
        self.sct = mss.mss()
        self.available = True
        logger.info("ScreenCapture initialized")

    def get_screen_size(self) -> tuple[int, int]:
        """Returns (width, height) of primary monitor."""
        try:
            monitor = self.sct.monitors[1]  # Primary monitor
            return (monitor["width"], monitor["height"])
        except Exception as e:
            logger.error("get_screen_size failed: {}", e)
            return (0, 0)

    def capture_full(self) -> Image.Image:
        """Captures full primary screen. Returns PIL Image."""
        try:
            monitor = self.sct.monitors[1]  # Primary monitor
            screenshot = self.sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            logger.debug("Full screen captured | {}x{}", img.width, img.height)
            return img
        except Exception as e:
            logger.error("capture_full failed: {}", e)
            # Return a small blank image as fallback
            return Image.new("RGB", (320, 240), (0, 0, 0))

    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """Captures a specific screen region. Returns PIL Image."""
        try:
            monitor = {"left": x, "top": y, "width": width, "height": height}
            screenshot = self.sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            logger.debug("Region captured | ({},{},{},{})", x, y, width, height)
            return img
        except Exception as e:
            logger.error("capture_region failed: {}", e)
            return Image.new("RGB", (320, 240), (0, 0, 0))

    def capture_window(self, window_title: str) -> Optional[Image.Image]:
        """
        Captures a specific window by title using pygetwindow.
        Falls back to full screen capture if window not found.
        Returns PIL Image or None on failure.

        Args:
            window_title: Title of the window to capture (partial match).
        """
        try:
            if not GW_AVAILABLE:
                logger.warning("capture_window: pygetwindow not installed, falling back to full screen")
                return self.capture_full()

            windows = gw.getWindowsWithTitle(window_title)
            if not windows:
                logger.warning("capture_window: No window found matching '{}'", window_title)
                return None

            win = windows[0]
            if not win.visible:
                logger.warning("capture_window: Window '{}' is not visible", window_title)
                return None

            # Restore if minimized
            if win.isMinimized:
                win.restore()
                time.sleep(0.2)  # Brief wait for window to restore

            # Capture the window bounding box
            return self.capture_region(win.left, win.top, win.width, win.height)

        except Exception as e:
            logger.error("capture_window failed for '{}': {}", window_title, e)
            return None

    def save_screenshot(self, path: str = None) -> str:
        """
        Saves a full screenshot to disk.
        If path is None, saves to D:\\drex\\data\\screenshots\\ with timestamp.
        Returns the saved file path as string.

        Args:
            path: Optional explicit file path.

        Returns:
            The saved file path, or empty string on failure.
        """
        img = self.capture_full()
        try:
            if path is None:
                screenshots_dir = Path(__file__).parent.parent / "data" / "screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                path = str(screenshots_dir / f"screenshot_{timestamp}.png")

            img.save(path)
            logger.info("Screenshot saved to '{}'", path)
            return path
        except Exception as e:
            logger.error("save_screenshot failed: {}", e)
            return ""

    def capture_to_base64(self) -> str:
        """
        Captures full screen and returns as base64 string.
        Used for sending to vision AI APIs.
        Returns JPEG base64 (compressed to reduce token cost).

        Returns:
            Base64-encoded JPEG string, or empty string on failure.
        """
        img = self.capture_full()
        try:
            buffer = io.BytesIO()
            # Save as JPEG with quality 85 to reduce size
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            import base64
            b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            logger.debug("capture_to_base64: {} bytes encoded", len(b64_str))
            return b64_str
        except Exception as e:
            logger.error("capture_to_base64 failed: {}", e)
            return ""

    def close(self):
        """Clean up mss resources."""
        try:
            self.sct.close()
            logger.debug("ScreenCapture resources released")
        except Exception as e:
            logger.error("ScreenCapture close error: {}", e)