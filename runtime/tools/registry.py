from __future__ import annotations
import threading
from typing import Any, Optional
from loguru import logger
from runtime.tools.base_tool import BaseTool
from runtime.tools.models import ToolRequest, ToolResult

class ToolRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._tools: dict[str, BaseTool] = {}
        self._tool_count = 0
    def register_tool(self, tool: BaseTool, capability_registry=None) -> None:
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Expected BaseTool, got {type(tool).__name__}")
        meta = tool.metadata()
        name = meta.name
        if not name: raise ValueError("Empty tool name")
        with self._lock:
            if name in self._tools: raise ValueError(f"Tool already registered: {name}")
            self._tools[name] = tool
            self._tool_count += 1
        if capability_registry is not None:
            try:
                capability_registry.register(f"tool.{name}", available=True, description=meta.description, metadata={"category": meta.category, "risk": meta.risk_level.value})
            except Exception as e: logger.warning("Capability update failed: {}", e)
    def unregister_tool(self, name: str) -> bool:
        with self._lock:
            if name in self._tools: del self._tools[name]; self._tool_count -= 1; return True
            return False
    def get_tool(self, name: str) -> Optional[BaseTool]:
        with self._lock: return self._tools.get(name)
    def list_tools(self, category: str = None, risk_level: str = None) -> list[dict]:
        with self._lock: tools = list(self._tools.values())
        results = []
        for tool in tools:
            meta = tool.metadata()
            if category and meta.category != category: continue
            if risk_level and meta.risk_level.value != risk_level: continue
            results.append(meta.to_dict())
        return results
    def count(self) -> int:
        with self._lock: return self._tool_count
    def execute_tool(self, request: ToolRequest) -> Optional[ToolResult]:
        tool = self.get_tool(request.tool_name)
        if tool is None: return None
        errors = tool.validate(request)
        if errors: return ToolResult(success=False, error=f"Validation failed: {'; '.join(errors)}")
        return tool.execute(request)
    def validate_tool(self, request: ToolRequest) -> list[str]:
        tool = self.get_tool(request.tool_name)
        if tool is None: return [f"Tool not found: {request.tool_name}"]
        return tool.validate(request)
    def get_status(self) -> dict[str, Any]:
        return {"tool_count": self.count(), "tools": [t["name"] for t in self.list_tools()]}

__all__ = ["ToolRegistry"]
