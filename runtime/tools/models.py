from __future__ import annotations
import time
import uuid
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
