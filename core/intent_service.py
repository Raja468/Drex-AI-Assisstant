"""Structured intent classification service."""
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

# Maps canonical intent names → tool hints (None = no tool)
INTENT_TOOL_MAP: dict[str, str | None] = {
    "app_launch": "app_launcher",
    "browser_control": "browser",
    "file_operation": "file",
    "system_control": "system",
    "screen_query": "screenshot",
    "clipboard": "clipboard",
    "time_date": None,
    "small_talk": None,
    "personality": None,
    "memory": None,
    "weather": None,
    "media": None,
    "general_ai": None,
}

# Maps raw IntentParser types → canonical intent names
INTENT_CANONICAL_MAP: dict[str, str] = {
    "open_app": "app_launch",
    "close_app": "app_launch",
    "browser": "browser_control",
    "browser_control": "browser_control",
    "file_manager": "file_operation",
    "file_operation": "file_operation",
    "system_control": "system_control",
    "screen_query": "screen_query",
    "clipboard": "clipboard",
    "time_date": "time_date",
    "small_talk": "small_talk",
    "personality": "personality",
    "memory": "memory",
    "ai_query": "general_ai",
    "weather": "general_ai",
    "media": "media",
    "general_ai": "general_ai",
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
        """Map raw parser type to canonical intent name + tool hint."""
        canonical = INTENT_CANONICAL_MAP.get(pt, "general_ai")
        tool_hint = INTENT_TOOL_MAP.get(canonical)
        return canonical, tool_hint
    def can_handle_tool(self, ir: IntentResult) -> bool:
        return ir.tool_hint is not None

__all__ = ["IntentResult", "IntentService"]
