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
