"""Routes intents to structured tool execution."""
from __future__ import annotations
from typing import Any, Optional
from loguru import logger
from core.intent_service import IntentResult
from runtime.tools.executor import ToolExecutor
from runtime.tools.models import ToolRequest, ToolResult
from runtime.tools.registry import ToolRegistry

class ToolRouter:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        intent_service,
    ):
        self._registry = tool_registry
        self._executor = tool_executor
        self._intent_service = intent_service
    def can_handle(self, intent_result: IntentResult) -> bool:
        if intent_result.tool_hint is None:
            return False
        tool = self._registry.get_tool(intent_result.tool_hint)
        return tool is not None
    def route(self, text: str, intent_result: IntentResult) -> Optional[ToolResult]:
        if not self.can_handle(intent_result):
            return None
        tool_name = intent_result.tool_hint
        arguments = self._build_arguments(text, intent_result)
        request = ToolRequest(
            tool_name=tool_name,
            arguments=arguments,
            metadata={"source": "tool_router", "intent": intent_result.intent},
        )
        logger.info(
            "ToolRouter routing | tool={} | intent={} | args={}",
            tool_name, intent_result.intent, arguments,
        )
        return self._executor.execute(request)
    def _build_arguments(self, text: str, intent: IntentResult) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if intent.intent in ("open_app", "app_launch", "close_app"):
            args["action"] = "open" if "open" in intent.intent else "close"
            args["app_name"] = intent.entities.get("app", intent.raw)
        elif intent.intent in ("browser", "browser_control"):
            tl = text.lower()
            if tl.startswith(("search", "google", "look up")):
                args["action"] = "search"
                args["query"] = intent.entities.get("app", text)
            elif "youtube" in tl and "search" in tl:
                args["action"] = "youtube_search"
                args["query"] = intent.entities.get("app", text)
            elif "maps" in tl:
                args["action"] = "maps"
                args["query"] = intent.entities.get("app", text)
            elif "." in intent.entities.get("app", ""):
                args["action"] = "open_url"
                args["query"] = intent.entities.get("app", "")
            else:
                args["action"] = "open_site"
                args["query"] = intent.entities.get("app", text)
        elif intent.intent in ("file", "file_operation"):
            args["action"] = intent.entities.get("action", "find")
            args["path"] = intent.entities.get("path", intent.raw)
        elif intent.intent in ("system", "system_control"):
            args["action"] = intent.entities.get("action", "system_info")
            v = intent.entities.get("value", "")
            if v and v.isdigit():
                args["level"] = int(v)
        elif intent.intent == "screen_query":
            args["action"] = intent.entities.get("action", "describe")
        elif intent.intent == "clipboard":
            args["action"] = intent.entities.get("action", "read")
        else:
            args["action"] = "execute"
            args["query"] = text
        return args

__all__ = ["ToolRouter"]