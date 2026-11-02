"""Build the runtime/tools package files cleanly."""
import os

FILES = {}

FILES["runtime/tools/__init__.py"] = '''"""
runtime/tools/ — Structured Tool Runtime for DREX.
"""

from runtime.tools.base_tool import BaseTool
from runtime.tools.events import ToolCompleted, ToolFailed, ToolPermissionRequired, ToolStarted
from runtime.tools.executor import ToolExecutor
from runtime.tools.models import ToolMetadata, ToolRequest, ToolResult
from runtime.tools.permissions import PermissionEvaluator, RiskLevel
from runtime.tools.registry import ToolRegistry

__all__ = [
    "BaseTool", "PermissionEvaluator", "RiskLevel",
    "ToolCompleted", "ToolExecutor", "ToolFailed",
    "ToolMetadata", "ToolPermissionRequired", "ToolRegistry",
    "ToolRequest", "ToolResult", "ToolStarted",
]
'''

FILES["runtime/tools/models.py"] = '''"""
runtime/tools/models.py — Tool data models.
"""
from __future__ import annotations
import time, uuid
from dataclasses import dataclass, field
from typing import Any
from runtime.tools.permissions import RiskLevel

@dataclass
class ToolMetadata:
    name: str
    description: str
    category: str = "general"
    risk_level: RiskLevel = RiskLevel.SAFE
    permissions_required: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "category": self.category, "risk_level": self.risk_level.value, "permissions_required": list(self.permissions_required), "version": self.version, "tags": list(self.tags)}

@dataclass
class ToolRequest:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return {"tool_name": self.tool_name, "arguments": dict(self.arguments), "request_id": self.request_id, "created_at": self.created_at, "metadata": dict(self.metadata)}

@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "output": self.output, "error": self.error, "execution_time": self.execution_time, "metadata": dict(self.metadata)}

__all__ = ["ToolMetadata", "ToolRequest", "ToolResult"]
'''

FILES["runtime/tools/permissions.py"] = '''"""
runtime/tools/permissions.py — Permission model.
"""
from __future__ import annotations
import threading
from enum import Enum
from typing import Callable, Optional

class RiskLevel(Enum):
    SAFE = "safe"; LOW = "low"; MEDIUM = "medium"; HIGH = "high"; CRITICAL = "critical"

class PermissionEvaluator:
    def __init__(self, auto_approve_safe: bool = True):
        self._auto_approve_safe = auto_approve_safe
        self._on_permission_required: Optional[Callable] = None
    def register_approval_handler(self, handler):
        self._on_permission_required = handler
    def check(self, tool_name: str, risk_level: RiskLevel, arguments: dict) -> bool:
        if self._auto_approve_safe and risk_level in (RiskLevel.SAFE, RiskLevel.LOW):
            return True
        if self._on_permission_required is None:
            return False
        approved = threading.Event(); result = [False]
        def approve(): result[0] = True; approved.set()
        def deny(): result[0] = False; approved.set()
        self._on_permission_required(tool_name=tool_name, risk=risk_level.value, arguments=str(arguments), approve_fn=approve, deny_fn=deny)
        approved.wait(timeout=30)
        return result[0]
    def risk_level_for_action(self, action: str) -> RiskLevel:
        a = action.lower().strip()
        if a in ("shutdown","restart","delete_file","empty_trash"): return RiskLevel.CRITICAL
        if a in ("close_app","kill","create_file","create_folder","screenshot"): return RiskLevel.HIGH
        if a in ("open_app","search","open_url","open_site"): return RiskLevel.LOW
        return RiskLevel.SAFE

__all__ = ["PermissionEvaluator", "RiskLevel"]
'''

FILES["runtime/tools/base_tool.py"] = '''"""
runtime/tools/base_tool.py — Abstract base class.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from runtime.tools.models import ToolMetadata, ToolRequest, ToolResult

class BaseTool(ABC):
    @abstractmethod
    def metadata(self) -> ToolMetadata: ...
    @abstractmethod
    def execute(self, request: ToolRequest) -> ToolResult: ...
    @abstractmethod
    def validate(self, request: ToolRequest) -> list[str]: ...
    @property
    def name(self) -> str: return self.metadata().name
    @property
    def category(self) -> str: return self.metadata().category
    @property
    def risk_level(self): return self.metadata().risk_level
    def __repr__(self) -> str: return f"<{type(self).__name__} name={self.name}>"

__all__ = ["BaseTool"]
'''

FILES["runtime/tools/registry.py"] = '''"""
runtime/tools/registry.py — Central tool registry.
"""
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
        meta = tool.metadata(); name = meta.name
        if not name: raise ValueError("Empty tool name")
        with self._lock:
            if name in self._tools: raise ValueError(f"Tool already registered: {name}")
            self._tools[name] = tool; self._tool_count += 1
        if capability_registry is not None:
            try:
                capability_registry.register(f"tool.{name}", available=True, description=meta.description, metadata={"category": meta.category, "risk": meta.risk_level.value})
            except Exception as e: logger.warning("Capability update failed for tool {}: {}", name, e)
    def unregister_tool(self, name: str) -> bool:
        with self._lock:
            if name in self._tools: del self._tools[name]; self._tool_count -= 1; return True
            return False
    def get_tool(self, name: str) -> Optional[BaseTool]:
        with self._lock: return self._tools.get(name)
    def list_tools(self, category: str | None = None, risk_level: str | None = None) -> list[dict]:
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
'''

FILES["runtime/tools/executor.py"] = '''"""
runtime/tools/executor.py — Execution engine.
"""
from __future__ import annotations
import time
from loguru import logger
from runtime.tools.models import ToolMetadata, ToolRequest, ToolResult
from runtime.tools.permissions import PermissionEvaluator
from runtime.tools.registry import ToolRegistry

class ToolExecutor:
    def __init__(self, registry: ToolRegistry, evaluator: PermissionEvaluator | None = None, event_bus=None):
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
    def _publish(self, event_type: str, request: ToolRequest, meta: ToolMetadata, result: ToolResult | None = None) -> None:
        if self._event_bus is None: return
        try:
            from runtime.events import Event
            payload = {"tool_name": request.tool_name, "request_id": request.request_id, "category": meta.category, "risk_level": meta.risk_level.value}
            if result is not None: payload["success"] = result.success; payload["execution_time"] = result.execution_time
            self._event_bus.publish(Event(type=event_type, source="tool_executor", payload=payload))
        except Exception as e: logger.debug("Tool event publish error: {}", e)

__all__ = ["ToolExecutor"]
'''

FILES["runtime/tools/events.py"] = '''"""Tool runtime event types."""
from runtime.events import RuntimeEvent
class ToolStarted(RuntimeEvent): EVENT_TYPE = "tool.started"
class ToolCompleted(RuntimeEvent): EVENT_TYPE = "tool.completed"
class ToolFailed(RuntimeEvent): EVENT_TYPE = "tool.failed"
class ToolPermissionRequired(RuntimeEvent): EVENT_TYPE = "tool.permission_required"
__all__ = ["ToolCompleted", "ToolFailed", "ToolPermissionRequired", "ToolStarted"]
'''

# Write all files
for path, content in FILES.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content.lstrip('\n'))
    print(f"  Created: {path}")

print("\nAll tool files created successfully!")