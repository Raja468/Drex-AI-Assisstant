#!/usr/bin/env python3
"""Write all Phase 4 core files with correct content using a helper script."""
import os

def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  OK: {path}")

# 1. IntentService
write(os.path.join('core', 'intent_service.py'), '''"""Structured intent classification service."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from loguru import logger
from core.intent_parser import IntentParser

@dataclass
class IntentResult:
    intent: str = "general_ai"
    confidence: float = 0.5
    entities: dict[str, Any] = field(default_factory=dict)
    tool_hint: Optional[str] = None
    raw: str = ""

INTENT_TOOL_MAP = {
    "browser": "browser", "browser_control": "browser",
    "open_app": "app_launcher", "app_launch": "app_launcher", "close_app": "app_launcher",
    "file_manager": "file", "file_operation": "file",
    "system_control": "system",
    "screen_query": "screenshot",
    "clipboard": "clipboard",
    "time_date": None, "small_talk": None, "personality": None,
    "memory": None, "weather": None, "media": None,
    "ai_query": None, "general_ai": None
}

class IntentService:
    def __init__(self, intent_parser: IntentParser):
        self._parser = intent_parser
    def classify(self, text: str) -> IntentResult:
        if not text or not text.strip():
            return IntentResult(intent="empty", confidence=0.0, raw=text)
        parsed = self._parser.parse(text)
        intent, tool_hint = self._map_intent(parsed.type)
        entities: dict[str, Any] = {}
        if parsed.target:
            if parsed.type in ("open_app","close_app","browser","media"):
                entities["app"] = parsed.target
            elif parsed.type == "file_manager":
                entities["path"] = parsed.target
            elif parsed.type == "system_control":
                entities["action"] = parsed.action
                if parsed.target: entities["value"] = parsed.target
            elif parsed.type == "screen_query":
                entities["action"] = parsed.action
            elif parsed.type == "memory":
                entities["query"] = parsed.target
            elif parsed.type == "personality":
                entities["mode"] = parsed.target
            elif parsed.type == "time_date":
                entities["action"] = parsed.action
            else:
                entities["target"] = parsed.target
        entities.update(parsed.params)
        confidence = 0.95 if (parsed.type != "ai_query" and parsed.target) else (0.80 if parsed.type != "ai_query" else 0.30)
        return IntentResult(intent=intent, confidence=confidence, entities=entities, tool_hint=tool_hint, raw=text)
    def _map_intent(self, pt: str):
        if pt in INTENT_TOOL_MAP:
            return pt, INTENT_TOOL_MAP[pt]
        m = {"open_app":("app_launch","app_launcher"),"close_app":("app_launch","app_launcher"),
             "browser":("browser_control","browser"),"file_manager":("file_operation","file"),
             "system_control":("system_control","system"),"screen_query":("screen_query","screenshot"),
             "time_date":("time_date",None),"small_talk":("small_talk",None),
             "ai_query":("general_ai",None),"weather":("general_ai",None),"media":("general_ai",None),
             "personality":("personality",None),"memory":("memory",None)}
        return m.get(pt, ("general_ai", None))
    def can_handle_tool(self, ir: IntentResult) -> bool:
        return ir.tool_hint is not None

__all__ = ["IntentResult", "IntentService"]
''')

# 2. ToolRouter
write(os.path.join('core', 'tool_router.py'), '''"""Routes intents to structured tool execution."""
from __future__ import annotations
from typing import Any, Optional
from loguru import logger
from core.intent_service import IntentResult
from runtime.tools.executor import ToolExecutor
from runtime.tools.models import ToolRequest, ToolResult
from runtime.tools.registry import ToolRegistry

class ToolRouter:
    def __init__(self, tool_registry: ToolRegistry, tool_executor: ToolExecutor, intent_service):
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
        request = ToolRequest(tool_name=tool_name, arguments=arguments, metadata={"source":"tool_router","intent":intent_result.intent})
        logger.info("ToolRouter routing | tool={} | intent={} | args={}", tool_name, intent_result.intent, arguments)
        return self._executor.execute(request)
    def _build_arguments(self, text: str, intent: IntentResult) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if intent.intent in ("open_app","app_launch","close_app"):
            args["action"] = "open" if "open" in intent.intent else "close"
            args["app_name"] = intent.entities.get("app", intent.raw)
        elif intent.intent in ("browser","browser_control"):
            tl = text.lower()
            if tl.startswith(("search","google","look up")):
                args["action"] = "search"; args["query"] = intent.entities.get("app", text)
            elif "youtube" in tl and "search" in tl:
                args["action"] = "youtube_search"; args["query"] = intent.entities.get("app", text)
            elif "maps" in tl:
                args["action"] = "maps"; args["query"] = intent.entities.get("app", text)
            elif "." in intent.entities.get("app", ""):
                args["action"] = "open_url"; args["query"] = intent.entities.get("app", "")
            else:
                args["action"] = "open_site"; args["query"] = intent.entities.get("app", text)
        elif intent.intent in ("file","file_operation"):
            args["action"] = intent.entities.get("action","find")
            args["path"] = intent.entities.get("path", intent.raw)
        elif intent.intent in ("system","system_control"):
            args["action"] = intent.entities.get("action","system_info")
            v = intent.entities.get("value","")
            if v and v.isdigit(): args["level"] = int(v)
        elif intent.intent == "screen_query":
            args["action"] = intent.entities.get("action","describe")
        elif intent.intent == "clipboard":
            args["action"] = intent.entities.get("action","read")
        return args

__all__ = ["ToolRouter"]
''')

# 3. ResponseService
write(os.path.join('core', 'response_service.py'), '''"""Formats responses from tools and AI into natural language strings."""
from __future__ import annotations
import re
from loguru import logger
from runtime.tools.models import ToolResult

class ResponseService:
    def __init__(self, voice_mode: bool = False):
        self._voice_mode = voice_mode
    def format_tool_result(self, result: ToolResult) -> str:
        return self._format_success(result) if result.success else self._format_failure(result)
    def _format_success(self, result: ToolResult) -> str:
        o = result.output.strip()
        if o and o[-1] in (".!?"):
            return o
        tn = result.metadata.get("tool_name","")
        m = {"browser":"Done.","clipboard":"Clipboard operation complete.","app_launcher":"Done.","screenshot":"Screenshot captured.","file":"File operation complete.","system":"Done."}
        return o or m.get(tn, "Done.")
    def _format_failure(self, result: ToolResult) -> str:
        e = result.error or "An unknown error occurred."
        if "not found" in e.lower() or "permission" in e.lower():
            return e
        return f"I couldn't do that. {e}"
    def format_ai_response(self, text: str) -> str:
        if not text: return ""
        return self._strip_markdown(text) if self._voice_mode else text.strip()
    def _strip_markdown(self, text: str) -> str:
        text = re.sub(r"\*+","",text)
        text = re.sub(r"#+\s*","",text)
        text = re.sub(r"`+","",text)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)",r"\1",text)
        text = re.sub(r"```[\s\S]*?```","",text)
        text = re.sub(r"---+\n?","",text)
        return text.strip()
    def format_error(self, error: Exception) -> str:
        return "Sorry, I ran into an unexpected issue. Please try again."
    def set_voice_mode(self, enabled: bool) -> None:
        self._voice_mode = enabled

__all__ = ["ResponseService"]
''')

print("\nAll 3 core files written successfully!")