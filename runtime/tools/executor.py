from __future__ import annotations
import time
from loguru import logger
from runtime.tools.models import ToolMetadata, ToolRequest, ToolResult
from runtime.tools.permissions import PermissionEvaluator
from runtime.tools.registry import ToolRegistry

class ToolExecutor:
    def __init__(self, registry: ToolRegistry, evaluator: PermissionEvaluator = None, event_bus=None):
        self._registry = registry
        self._evaluator = evaluator or PermissionEvaluator()
        self._event_bus = event_bus
    def execute(self, request: ToolRequest) -> ToolResult:
        tool = self._registry.get_tool(request.tool_name)
        if tool is None: return self._fail(request, f"Tool not found: {request.tool_name}")
        meta = tool.metadata()
        errors = tool.validate(request)
        if errors: return self._fail(request, f"Validation failed: {'; '.join(errors)}")
        self._publish("tool.started", request, meta)
        if not self._evaluator.check(request.tool_name, meta.risk_level, request.arguments):
            self._publish("tool.permission_required", request, meta)
            return ToolResult(success=False, error=f"Permission denied: {request.tool_name}")
        start = time.perf_counter()
        try:
            result = tool.execute(request)
            elapsed = time.perf_counter() - start
            result.execution_time = elapsed
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.exception("Tool failed | name={} | error={}", request.tool_name, exc)
            result = ToolResult(success=False, error=f"{type(exc).__name__}: {exc}", execution_time=elapsed)
        if result.success: self._publish("tool.completed", request, meta, result)
        else: self._publish("tool.failed", request, meta, result)
        return result
    def _fail(self, request: ToolRequest, error: str) -> ToolResult:
        logger.error("Tool aborted | name={} | error={}", request.tool_name, error)
        return ToolResult(success=False, error=error)
    def _publish(self, event_type: str, request: ToolRequest, meta: ToolMetadata, result: ToolResult = None) -> None:
        if self._event_bus is None: return
        try:
            from runtime.events import Event
            payload = {"tool_name": request.tool_name, "request_id": request.request_id, "category": meta.category, "risk_level": meta.risk_level.value}
            if result is not None: payload["success"] = result.success; payload["execution_time"] = result.execution_time
            self._event_bus.publish(Event(type=event_type, source="tool_executor", payload=payload))
        except Exception as e: logger.debug("Tool event publish error: {}", e)

__all__ = ["ToolExecutor"]
