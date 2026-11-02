"""
Tests for Phase 3 — Structured Tool Runtime.

Tests cover:
  - ToolRequest, ToolResult, ToolMetadata models
  - RiskLevel and PermissionEvaluator
  - BaseTool abstract class contract
  - ToolRegistry (register, get, list, execute)
  - ToolExecutor (validation, permission, timing, events)
  - EventBus integration
  - CapabilityRegistry integration
  - Tool adapters (validation, execution, lazy-init)
"""

import sys
import time

from loguru import logger

# Silence logger for clean test output
logger.remove()

passed = 0
failed = 0
tests = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        mark = "✅"
    else:
        failed += 1
        mark = "❌"
    msg = f"  {mark} {name}"
    if detail:
        msg += f" — {detail}"
    tests.append(msg)


def print_header(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


# ─────────────────────────────────────────────────────────────────
print_header("TEST 1: Data models")
from runtime.tools.models import ToolRequest, ToolResult, ToolMetadata
from runtime.tools.permissions import RiskLevel

# ToolMetadata
meta = ToolMetadata(
    name="test_tool",
    description="A test tool",
    category="testing",
    risk_level=RiskLevel.SAFE,
    permissions_required=["perm1"],
    version="2.0.0",
    tags=["test"],
)
check("ToolMetadata.name", meta.name == "test_tool")
check("ToolMetadata.risk_level", meta.risk_level == RiskLevel.SAFE)
check("ToolMetadata.to_dict", meta.to_dict()["category"] == "testing")

# ToolRequest
req = ToolRequest(tool_name="test_tool", arguments={"key": "value"})
check("ToolRequest.tool_name", req.tool_name == "test_tool")
check("ToolRequest.has_request_id", bool(req.request_id))
check("ToolRequest.arguments", req.arguments["key"] == "value")

# ToolResult
res = ToolResult(success=True, output="done", execution_time=0.5)
check("ToolResult.success", res.success)
check("ToolResult.output", res.output == "done")
check("ToolResult.to_dict", res.to_dict()["execution_time"] == 0.5)


# ─────────────────────────────────────────────────────────────────
print_header("TEST 2: RiskLevel & PermissionEvaluator")
from runtime.tools.permissions import PermissionEvaluator

check("RiskLevel values", len(RiskLevel) == 5)
check("RiskLevel.CRITICAL", RiskLevel.CRITICAL.value == "critical")

evaluator = PermissionEvaluator(auto_approve_safe=True)
check("evaluator auto-approves SAFE", evaluator.check("safe_tool", RiskLevel.SAFE, {}))
check("evaluator auto-approves LOW", evaluator.check("low_tool", RiskLevel.LOW, {}))

# Without approval handler, MEDIUM+ should be blocked
check("evaluator blocks MEDIUM", not evaluator.check("med_tool", RiskLevel.MEDIUM, {}))
check("evaluator blocks HIGH", not evaluator.check("high_tool", RiskLevel.HIGH, {}))
check("evaluator blocks CRITICAL", not evaluator.check("crit_tool", RiskLevel.CRITICAL, {}))

# Test risk_level_for_action
check("risk_level_for(shutdown)", evaluator.risk_level_for_action("shutdown") == RiskLevel.CRITICAL)
check("risk_level_for(delete_file)", evaluator.risk_level_for_action("delete_file") == RiskLevel.CRITICAL)
check("risk_level_for(screenshot)", evaluator.risk_level_for_action("screenshot") == RiskLevel.HIGH)
check("risk_level_for(open_app)", evaluator.risk_level_for_action("open_app") == RiskLevel.LOW)
check("risk_level_for(volume_up)", evaluator.risk_level_for_action("volume_up") == RiskLevel.SAFE)


# ─────────────────────────────────────────────────────────────────
print_header("TEST 3: BaseTool contract")
from runtime.tools.base_tool import BaseTool

# Verify it's abstract
import inspect
check("BaseTool is abstract", inspect.isabstract(BaseTool))

# Create a minimal concrete implementation
class MinimalTool(BaseTool):
    def metadata(self):
        from runtime.tools.models import ToolMetadata
        return ToolMetadata(name="minimal", description="", category="test")
    def execute(self, request):
        from runtime.tools.models import ToolResult
        return ToolResult(success=True, output="ok")
    def validate(self, request):
        return []

tool = MinimalTool()
check("MinimalTool.metadata", tool.name == "minimal")
check("MinimalTool.execute", tool.execute(None).success)
check("MinimalTool.validate", tool.validate(None) == [])
check("MinimalTool.__repr__", "MinimalTool" in repr(tool))


# ─────────────────────────────────────────────────────────────────
print_header("TEST 4: ToolRegistry")
from runtime.tools.registry import ToolRegistry

reg = ToolRegistry()

reg.register_tool(MinimalTool())
check("register_tool", reg.count() == 1)

# Duplicate registration should raise
from runtime.tools.base_tool import BaseTool

try:
    reg.register_tool(MinimalTool())
    check("duplicate prevention", False)
except ValueError:
    check("duplicate prevention", True)

# get_tool
retrieved = reg.get_tool("minimal")
check("get_tool", retrieved is not None)

# get_tool (not found)
check("get_tool (missing)", reg.get_tool("nonexistent") is None)

# list_tools
all_tools = reg.list_tools()
check("list_tools count", len(all_tools) == 1)
check("list_tools name", all_tools[0]["name"] == "minimal")

# list_tools with filter
from runtime.tools.permissions import RiskLevel
check("list_tools filter category", len(reg.list_tools(category="test")) == 1)
check("list_tools filter mismatch", len(reg.list_tools(category="other")) == 0)

# unregister_tool
check("unregister_tool", reg.unregister_tool("minimal"))
check("unregister_tool (missing)", not reg.unregister_tool("minimal"))
check("count after unregister", reg.count() == 0)

# execute_tool convenience
reg.register_tool(MinimalTool())
result = reg.execute_tool(ToolRequest(tool_name="minimal"))
check("execute_tool via registry", result.success)
check("execute_tool (missing)", reg.execute_tool(ToolRequest(tool_name="missing")) is None)

# validate_tool
check("validate_tool", reg.validate_tool(ToolRequest(tool_name="minimal")) == [])
check("validate_tool (missing)", "not found" in reg.validate_tool(ToolRequest(tool_name="x"))[0])

# get_status
status = reg.get_status()
check("get_status count", status["tool_count"] == 1)
check("get_status tools", "minimal" in status["tools"])


# ─────────────────────────────────────────────────────────────────
print_header("TEST 5: ToolExecutor")
from runtime.tools.executor import ToolExecutor

# Reset registry for clean state
reg2 = ToolRegistry()
reg2.register_tool(MinimalTool())
executor = ToolExecutor(reg2)

# Successful execution
req = ToolRequest(tool_name="minimal")
result = executor.execute(req)
check("executor success", result.success)
check("executor timing", result.execution_time > 0)
check("executor output", result.output == "ok")

# Tool not found
result2 = executor.execute(ToolRequest(tool_name="missing"))
check("executor not found", not result2.success)
check("executor error message", "not found" in result2.error)


# ─────────────────────────────────────────────────────────────────
print_header("TEST 6: EventBus integration")
from runtime.event_bus import EventBus
from runtime.events import Event

bus = EventBus()
received = []
bus.subscribe("tool.started", lambda e: received.append(e.type))
bus.subscribe("tool.completed", lambda e: received.append(e.type))

reg3 = ToolRegistry()
reg3.register_tool(MinimalTool())
executor3 = ToolExecutor(reg3, event_bus=bus)

executor3.execute(ToolRequest(tool_name="minimal"))
check("event published (started)", "tool.started" in received)
check("event published (completed)", "tool.completed" in received)


# ─────────────────────────────────────────────────────────────────
print_header("TEST 7: CapabilityRegistry integration")
from runtime.capability_registry import CapabilityRegistry

cap_reg = CapabilityRegistry()
reg4 = ToolRegistry()

reg4.register_tool(MinimalTool(), capability_registry=cap_reg)
check("capability registered", cap_reg.has("tool.minimal"))

# Verify capability has tool metadata
cap_detail = cap_reg.get("tool.minimal")
check("capability has description", cap_detail is not None)
check("capability has category", cap_detail["metadata"]["category"] == "test")


# ─────────────────────────────────────────────────────────────────
print_header("TEST 8: Tool adapters")
from runtime.tools.adapters import (
    BrowserTool, ClipboardTool, AppLauncherTool,
    ScreenshotTool, FileTool, SystemTool,
)

# Check all adapters follow BaseTool contract
for cls in (BrowserTool, ClipboardTool, AppLauncherTool, ScreenshotTool, FileTool, SystemTool):
    instance = cls()
    meta = instance.metadata()
    check(f"{cls.__name__}.metadata().name", bool(meta.name))
    check(f"{cls.__name__}.metadata().description", bool(meta.description))
    check(f"{cls.__name__}.is_base_tool", isinstance(instance, BaseTool))

# Check BrowserTool validation
bt = BrowserTool()
check("browser valid action", bt.validate(ToolRequest(tool_name="browser", arguments={"action": "search", "query": "test"})) == [])
check("browser invalid action", len(bt.validate(ToolRequest(tool_name="browser", arguments={"action": "unknown"}))) > 0)
check("browser missing query", len(bt.validate(ToolRequest(tool_name="browser", arguments={"action": "search"}))) > 0)

# Check ClipboardTool validation
ct = ClipboardTool()
check("clipboard valid read", ct.validate(ToolRequest(tool_name="clipboard", arguments={"action": "read"})) == [])
check("clipboard valid write", ct.validate(ToolRequest(tool_name="clipboard", arguments={"action": "write", "text": "hello"})) == [])
check("clipboard missing text", len(ct.validate(ToolRequest(tool_name="clipboard", arguments={"action": "write"}))) > 0)

# Check AppLauncherTool validation
alt = AppLauncherTool()
check("app_launcher valid", alt.validate(ToolRequest(tool_name="app_launcher", arguments={"action": "open", "app_name": "chrome"})) == [])
check("app_launcher missing app_name", len(alt.validate(ToolRequest(tool_name="app_launcher", arguments={"action": "open"}))) > 0)

# Check FileTool validation
ft = FileTool()
check("file valid", ft.validate(ToolRequest(tool_name="file", arguments={"action": "find", "path": "readme"})) == [])
check("file invalid action", len(ft.validate(ToolRequest(tool_name="file", arguments={"action": "delete"}))) > 0)

# Check SystemTool validation
st = SystemTool()
check("system valid", st.validate(ToolRequest(tool_name="system", arguments={"action": "system_info"})) == [])
check("system invalid", len(st.validate(ToolRequest(tool_name="system", arguments={"action": "unknown"}))) > 0)

# Check ScreenshotTool validation (no required args)
sct = ScreenshotTool()
check("screenshot valid", sct.validate(ToolRequest(tool_name="screenshot")) == [])


# ─────────────────────────────────────────────────────────────────
print_header("TEST 9: Full integration — adapters in registry + executor")
from runtime.tools.models import ToolRequest

reg5 = ToolRegistry()
cap_reg5 = CapabilityRegistry()
adapters = [BrowserTool, ClipboardTool, AppLauncherTool, ScreenshotTool, FileTool, SystemTool]
for cls in adapters:
    reg5.register_tool(cls(), capability_registry=cap_reg5)

check("all 6 adapters registered", reg5.count() == 6)
check("6 capabilities registered", cap_reg5.count() == 6)

# Verify each adapter is discoverable
for cls in adapters:
    instance = cls()
    check(f"get_tool({instance.name})", reg5.get_tool(instance.name) is not None)

# Full executor integration with event bus
bus5 = EventBus()
events5 = []
bus5.subscribe("*", lambda e: events5.append(e.type))
exec5 = ToolExecutor(reg5, event_bus=bus5)

# Execute browser tool
result = exec5.execute(ToolRequest(tool_name="browser", arguments={"action": "search", "query": "test"}))
check("executor browser success", result.success)
check("executor published events", "tool.started" in events5 and "tool.completed" in events5)


# ─────────────────────────────────────────────────────────────────
# SUMMARY
print()
print("=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 60)
for t in tests:
    print(t)
print()

if failed > 0:
    print(f"❌ {failed} test(s) failed!")
    sys.exit(1)
else:
    print("✅ All tool runtime tests passed!")
    print()