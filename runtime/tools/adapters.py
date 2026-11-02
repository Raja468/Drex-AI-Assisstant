"""Tool adapters wrapping existing automation modules."""

from __future__ import annotations

from runtime.tools.base_tool import BaseTool
from runtime.tools.models import ToolMetadata, ToolRequest, ToolResult
from runtime.tools.permissions import RiskLevel


class BrowserTool(BaseTool):
    def __init__(self):
        self._browser = None
    def _get_browser(self):
        if self._browser is None:
            from automation.browser_control import BrowserControl
            self._browser = BrowserControl()
        return self._browser
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(name="browser", description="Search the web, open URLs, and navigate to sites", category="web", risk_level=RiskLevel.LOW)
    def validate(self, request: ToolRequest) -> list[str]:
        errors = []
        action = request.arguments.get("action")
        if action not in ("search", "open_url", "open_site", "youtube_search", "maps"):
            errors.append(f"Unsupported action: {action}")
        if action in ("search", "open_url", "open_site") and not request.arguments.get("query", "").strip():
            errors.append("query required")
        return errors
    def execute(self, request: ToolRequest) -> ToolResult:
        action = request.arguments.get("action", "search")
        query = request.arguments.get("query", "")
        browser = self._get_browser()
        try:
            if action == "search":
                engine = request.arguments.get("engine", "google")
                ok, msg = browser.search(query, engine=engine)
            elif action == "open_url":
                ok, msg = browser.open_url(query)
            elif action == "open_site":
                ok, msg = browser.open_site(query)
            elif action == "youtube_search":
                ok, msg = browser.youtube_search(query)
            elif action == "maps":
                ok, msg = browser.google_maps(query)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
            return ToolResult(success=ok, output=msg)
        except Exception as e:
            return ToolResult(success=False, error=f"Browser error: {e}")


class ClipboardTool(BaseTool):
    def __init__(self):
        self._system = None
    def _get_system(self):
        if self._system is None:
            from automation.system_control import SystemControl
            self._system = SystemControl()
        return self._system
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(name="clipboard", description="Read from and write to system clipboard", category="system", risk_level=RiskLevel.SAFE)
    def validate(self, request: ToolRequest) -> list[str]:
        errors = []
        a = request.arguments.get("action")
        if a not in ("read", "write"):
            errors.append(f"Unsupported action: {a}")
        if a == "write" and not request.arguments.get("text", "").strip():
            errors.append("text required for write")
        return errors
    def execute(self, request: ToolRequest) -> ToolResult:
        a = request.arguments.get("action", "read")
        s = self._get_system()
        try:
            if a == "read":
                text = s.get_clipboard()
                return ToolResult(success=True, output=text or "")
            elif a == "write":
                ok, msg = s.set_clipboard(request.arguments.get("text", ""))
                return ToolResult(success=ok, output=msg)
            return ToolResult(success=False, error=f"Unknown action: {a}")
        except Exception as e:
            return ToolResult(success=False, error=f"Clipboard error: {e}")


class AppLauncherTool(BaseTool):
    def __init__(self):
        self._launcher = None
    def _get_launcher(self):
        if self._launcher is None:
            from automation.app_launcher import AppLauncher
            self._launcher = AppLauncher()
        return self._launcher
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(name="app_launcher", description="Open and close desktop applications", category="automation", risk_level=RiskLevel.MEDIUM)
    def validate(self, request: ToolRequest) -> list[str]:
        errors = []
        a = request.arguments.get("action")
        if a not in ("open", "close"):
            errors.append(f"Unsupported action: {a}")
        if not request.arguments.get("app_name", "").strip():
            errors.append("app_name required")
        return errors
    def execute(self, request: ToolRequest) -> ToolResult:
        a = request.arguments.get("action", "open")
        app = request.arguments.get("app_name", "")
        l = self._get_launcher()
        try:
            if a == "open":
                ok, msg = l.open_app(app)
            elif a == "close":
                ok, msg = l.close_app(app)
            else:
                return ToolResult(success=False, error=f"Unknown action: {a}")
            return ToolResult(success=ok, output=msg)
        except Exception as e:
            return ToolResult(success=False, error=f"App launcher error: {e}")


class ScreenshotTool(BaseTool):
    def __init__(self):
        self._system = None
    def _get_system(self):
        if self._system is None:
            from automation.system_control import SystemControl
            self._system = SystemControl()
        return self._system
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(name="screenshot", description="Capture a screenshot of the current screen", category="system", risk_level=RiskLevel.HIGH)
    def validate(self, request: ToolRequest) -> list[str]:
        return []
    def execute(self, request: ToolRequest) -> ToolResult:
        s = self._get_system()
        try:
            ok, msg = s.take_screenshot(filename=request.arguments.get("filename"))
            return ToolResult(success=ok, output=msg)
        except Exception as e:
            return ToolResult(success=False, error=f"Screenshot error: {e}")


class FileTool(BaseTool):
    def __init__(self):
        self._fm = None
    def _get_fm(self):
        if self._fm is None:
            from automation.file_manager import FileManager
            self._fm = FileManager()
        return self._fm
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(name="file", description="Find, open, and inspect files", category="filesystem", risk_level=RiskLevel.MEDIUM)
    def validate(self, request: ToolRequest) -> list[str]:
        errors = []
        a = request.arguments.get("action")
        if a not in ("find", "open", "info", "list_dir"):
            errors.append(f"Unsupported action: {a}")
        if a in ("find", "open", "info") and not request.arguments.get("path", "").strip():
            errors.append("path required")
        return errors
    def execute(self, request: ToolRequest) -> ToolResult:
        a = request.arguments.get("action", "find")
        path = request.arguments.get("path", "")
        fm = self._get_fm()
        try:
            if a == "find":
                max_r = request.arguments.get("max_results", 5)
                results = fm.find_file(path, max_results=max_r)
                if results:
                    return ToolResult(success=True, output=f"Found {len(results)} file(s).", metadata={"paths": [str(p) for p in results]})
                return ToolResult(success=False, output=f"No files found: {path}")
            elif a == "open":
                ok, msg = fm.open_file(path)
                return ToolResult(success=ok, output=msg)
            elif a == "info":
                info = fm.get_file_info(path)
                if info: return ToolResult(success=True, metadata=info)
                return ToolResult(success=False, error=f"File not found: {path}")
            elif a == "list_dir":
                items = fm.list_directory(path)
                return ToolResult(success=True, metadata={"items": items, "count": len(items)})
            return ToolResult(success=False, error=f"Unknown action: {a}")
        except Exception as e:
            return ToolResult(success=False, error=f"File error: {e}")


class SystemTool(BaseTool):
    def __init__(self):
        self._system = None
    def _get_system(self):
        if self._system is None:
            from automation.system_control import SystemControl
            self._system = SystemControl()
        return self._system
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(name="system", description="Control system volume, power, and query info", category="system", risk_level=RiskLevel.SAFE)
    def validate(self, request: ToolRequest) -> list[str]:
        valid = {"volume_up","volume_down","mute","set_volume","shutdown","restart","sleep","lock","cancel_shutdown","system_info","press_key","hotkey","type_text"}
        a = request.arguments.get("action")
        if a not in valid:
            return [f"Unsupported action: {a}"]
        return []
    def execute(self, request: ToolRequest) -> ToolResult:
        a = request.arguments.get("action", "system_info")
        s = self._get_system()
        try:
            if a == "volume_up":
                ok, msg = s.volume_up(steps=request.arguments.get("steps", 2))
            elif a == "volume_down":
                ok, msg = s.volume_down(steps=request.arguments.get("steps", 2))
            elif a == "mute":
                ok, msg = s.mute()
            elif a == "set_volume":
                ok, msg = s.set_volume(request.arguments.get("level", 50))
            elif a == "shutdown":
                ok, msg = s.shutdown(delay_seconds=request.arguments.get("delay_seconds", 5))
            elif a == "restart":
                ok, msg = s.restart(delay_seconds=request.arguments.get("delay_seconds", 5))
            elif a == "sleep":
                ok, msg = s.sleep()
            elif a == "lock":
                ok, msg = s.lock_screen()
            elif a == "cancel_shutdown":
                ok, msg = s.cancel_shutdown()
            elif a == "system_info":
                return ToolResult(success=True, output=s.format_system_info(), metadata=s.get_system_info())
            elif a == "press_key":
                ok, msg = s.press_key(request.arguments.get("key", ""))
            elif a == "hotkey":
                ok, msg = s.hotkey(*request.arguments.get("keys", []))
            elif a == "type_text":
                ok, msg = s.type_text(request.arguments.get("text", ""))
            else:
                return ToolResult(success=False, error=f"Unknown action: {a}")
            return ToolResult(success=ok, output=msg)
        except Exception as e:
            return ToolResult(success=False, error=f"System error: {e}")


__all__ = ["AppLauncherTool", "BrowserTool", "ClipboardTool", "FileTool", "ScreenshotTool", "SystemTool"]