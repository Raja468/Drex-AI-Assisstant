from __future__ import annotations
import threading
from enum import Enum
from typing import Callable, Optional

class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

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
        approved = threading.Event()
        result = [False]
        def approve():
            result[0] = True
            approved.set()
        def deny():
            result[0] = False
            approved.set()
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
