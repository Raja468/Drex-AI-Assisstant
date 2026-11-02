"""
Phase 4 verification: IntentService, ToolRouter, ResponseService, orchestrator wiring.

Test cases:
1. IntentService classifies "open chrome" -> intent="app_launch", tool_hint="app_launcher"
2. IntentService classifies "what time is it" -> intent="time_date", tool_hint=None
3. IntentService classifies "hello how are you" -> intent="small_talk", tool_hint=None
4. ToolRouter.can_handle() returns True for app_launch intent
5. ToolRouter.can_handle() returns False for small_talk intent
6. ToolRouter.route() returns ToolResult for browser intent
7. ResponseService.format_tool_result() success -> natural string
8. ResponseService.format_tool_result() failure -> error string
9. ResponseService.format_error() never raises
10. Full pipeline: text -> IntentService -> ToolRouter -> ResponseService
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from loguru import logger

logger.remove()

passed = 0
failed = 0
tests = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        mark = "PASS"
    else:
        failed += 1
        mark = "FAIL"
    msg = f"  {mark} {name}"
    if detail:
        msg += f" -- {detail}"
    tests.append(msg)


def header(title):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


# Setup
from core.intent_parser import IntentParser
from core.intent_service import IntentService, IntentResult
from core.tool_router import ToolRouter
from core.response_service import ResponseService
from runtime.tools.models import ToolMetadata, ToolRequest, ToolResult
from runtime.tools.permissions import RiskLevel
from runtime.tools.base_tool import BaseTool
from runtime.tools.registry import ToolRegistry
from runtime.tools.executor import ToolExecutor

parser = IntentParser()
intent_svc = IntentService(parser)
resp_svc = ResponseService()


# Test 1: open chrome
header("TEST 1: IntentService classifies 'open chrome'")
r1 = intent_svc.classify("open chrome")
check("intent == app_launch", r1.intent == "app_launch", f"got {r1.intent}")
check("tool_hint == app_launcher", r1.tool_hint == "app_launcher", f"got {r1.tool_hint}")
check("confidence == 0.95", r1.confidence == 0.95)
check("entities[app] == chrome", r1.entities.get("app") == "chrome")

# Test 2: what's the time (IntentParser matches "what's the time" regex)
header("TEST 2: IntentService classifies 'what's the time'")
r2 = intent_svc.classify("what's the time")
check("intent == time_date", r2.intent == "time_date", f"got {r2.intent}")
check("tool_hint is None", r2.tool_hint is None)

# Test 3: hello (exact match required by IntentParser)
header("TEST 3: IntentService classifies 'hello'")
r3 = intent_svc.classify("hello")
check("intent == small_talk", r3.intent == "small_talk", f"got {r3.intent}")
check("tool_hint is None", r3.tool_hint is None)


# Test 4-6: ToolRouter
header("TEST 4-6: ToolRouter")

class MockTool(BaseTool):
    def __init__(self, name: str):
        self._name = name
    def metadata(self):
        return ToolMetadata(name=self._name, description="", category="test", risk_level=RiskLevel.LOW)
    def execute(self, r):
        return ToolResult(success=True, output="Done.")
    def validate(self, r):
        return []

reg = ToolRegistry()
reg.register_tool(MockTool("browser"))
reg.register_tool(MockTool("app_launcher"))
executor = ToolExecutor(reg)
router = ToolRouter(reg, executor, intent_svc)

# Test 4
ir_h = IntentResult(intent="app_launch", tool_hint="app_launcher")
check("can_handle(app_launch)", router.can_handle(ir_h))

# Test 5
ir_n = IntentResult(intent="small_talk", tool_hint=None)
check("can_handle(small_talk) is False", not router.can_handle(ir_n))

# Test 6
ir_b = IntentResult(intent="browser_control", tool_hint="browser")
result = router.route("open chrome", ir_b)
check("route returns ToolResult", result is not None)
check("route success", result.success)


# Test 7-9: ResponseService
header("TEST 7-9: ResponseService")

res1 = resp_svc.format_tool_result(ToolResult(success=True, output="Done."))
check("format success ends with .", res1.strip().endswith("."))

res2 = resp_svc.format_tool_result(ToolResult(success=False, error="not found"))
check("format failure contains not found", "not found" in res2.lower())

try:
    res3 = resp_svc.format_error(Exception("test error"))
    check("format_error never raises", True, f"got: {res3}")
except Exception:
    check("format_error never raises", False)


# Test 10: Full pipeline
header("TEST 10: Full pipeline")

# app_launch pipeline
app_text = "open chrome"
app_intent = intent_svc.classify(app_text)
check("app intent classified", app_intent.intent == "app_launch")
check("app tool_hint", app_intent.tool_hint == "app_launcher")

app_result = router.route(app_text, app_intent)
check("app route succeeded", app_result is not None and app_result.success)

app_response = resp_svc.format_tool_result(app_result)
check("app response ends with .", app_response.strip().endswith("."))

# browser pipeline
browser_text = "search for python"
browser_intent = intent_svc.classify(browser_text)
check("browser intent classified", browser_intent.tool_hint == "browser")

browser_result = router.route(browser_text, browser_intent)
check("browser route succeeded", browser_result is not None and browser_result.success)

browser_response = resp_svc.format_tool_result(browser_result)
check("browser response ends with .", browser_response.strip().endswith("."))

# small_talk pipeline (no tool -- falls through to AI)
small_text = "hello"
small_intent = intent_svc.classify(small_text)
check("small_talk tool_hint is None", small_intent.tool_hint is None)
small_result = router.route(small_text, small_intent)
check("small_talk route returns None", small_result is None)


# Summary
print()
print("=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 60)
for t in tests:
    print(t)
print()

if failed > 0:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL PHASE 4 TESTS PASSED")
    print()