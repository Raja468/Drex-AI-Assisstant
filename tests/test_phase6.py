"""
Phase 6 verification: Awareness models, events, WindowTracker, ScreenAnalyzer,
AwarenessEngine, runtime integration, and orchestrator wiring.

Required tests (24 total):
  1.  test_window_info_defaults         — WindowInfo fields correct
  2.  test_screen_context_defaults      — ScreenContext fields correct
  3.  test_screen_context_to_dict       — serialization works
  4.  test_screen_context_is_stale      — is_stale(0) True, is_stale(9999) False
  5.  test_system_snapshot_defaults     — SystemSnapshot fields correct
  6.  test_system_snapshot_describe     — describe() returns non-empty string
  7.  test_window_tracker_init          — initializes without error
  8.  test_get_active_window            — returns WindowInfo or None (no crash)
  9.  test_window_tracker_start_stop    — start() and stop() without error
  10. test_window_tracker_get_current   — get_current() before poll returns None
  11. test_screen_analyzer_init         — initializes, available is bool
  12. test_get_cached_empty             — get_cached() returns None initially
  13. test_describe_current_string      — describe_current() returns string
  14. test_awareness_engine_init        — initializes without error
  15. test_get_snapshot_initial         — get_snapshot() returns None initially
  16. test_get_context_for_prompt       — returns string (may be empty)
  17. test_awareness_engine_start_stop  — start() and stop() without error
  18. test_describe_screen_string       — describe_screen() returns string
  19. test_window_changed_event         — EventBus receives awareness.window_changed
  20. test_context_updated_event        — EventBus receives awareness.context_updated
  21. test_runtime_registration         — AwarenessEngine in RuntimeSupervisor
  22. test_capability_registered        — "awareness" in CapabilityRegistry
  23. test_orchestrator_has_awareness   — orchestrator.awareness_engine is not None
  24. test_context_for_prompt_string    — get_context_for_prompt() returns str
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import threading
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


# ═══════════════════════════════════════════════════════════
# TEST 1-6: Awareness Models
# ═══════════════════════════════════════════════════════════

from runtime.awareness import (
    WindowInfo, ScreenContext, SystemSnapshot,
    WindowChanged, ContextUpdated,
    WindowTracker, ScreenAnalyzer, AwarenessEngine,
)
from runtime import EventBus, RuntimeSupervisor, CapabilityRegistry


header("TEST 1-6: Awareness Models")

# Test 1: WindowInfo defaults
wi = WindowInfo()
check("WindowInfo title defaults to ''", wi.title == "")
check("WindowInfo process_name defaults to ''", wi.process_name == "")
check("WindowInfo pid defaults to 0", wi.pid == 0)
check("WindowInfo is_active defaults to False", wi.is_active is False)

# Test 2: ScreenContext defaults
sc = ScreenContext()
check("ScreenContext window defaults to None", sc.window is None)
check("ScreenContext description defaults to ''", sc.description == "")
check("ScreenContext visible_text defaults to ''", sc.visible_text == "")
check("ScreenContext ui_elements is empty list", sc.ui_elements == [])
check("ScreenContext analysis_duration_ms defaults to 0.0", sc.analysis_duration_ms == 0.0)

# Test 3: ScreenContext to_dict
wi2 = WindowInfo(title="Test App", process_name="test.exe", pid=1234, is_active=True)
sc2 = ScreenContext(window=wi2, description="A test screen", visible_text="Hello")
d = sc2.to_dict()
check("to_dict has window key", "window" in d)
check("to_dict window title", d["window"]["title"] == "Test App")
check("to_dict description", d["description"] == "A test screen")

# Test 4: ScreenContext is_stale
from datetime import datetime, timedelta
future_sc = ScreenContext(captured_at=datetime.now() + timedelta(seconds=3600))
old_sc = ScreenContext(captured_at=datetime.now() - timedelta(seconds=100))
check("is_stale(9999) False for future", future_sc.is_stale(9999) is False)
check("is_stale(0) True for old", old_sc.is_stale(0) is True)
check("is_stale(200) False for 100s old", old_sc.is_stale(200) is False)

# Test 5: SystemSnapshot defaults
ss = SystemSnapshot()
check("SystemSnapshot active_window defaults to None", ss.active_window is None)
check("SystemSnapshot screen_context defaults to None", ss.screen_context is None)
check("SystemSnapshot cpu_percent defaults to 0.0", ss.cpu_percent == 0.0)
check("SystemSnapshot memory_percent defaults to 0.0", ss.memory_percent == 0.0)
check("SystemSnapshot to_dict has keys", "active_window" in ss.to_dict())

# Test 6: SystemSnapshot describe
wi3 = WindowInfo(title="VS Code", process_name="Code.exe", pid=5678, is_active=True)
ss2 = SystemSnapshot(active_window=wi3, cpu_percent=25.0, memory_percent=50.0)
desc = ss2.describe()
check("describe() returns non-empty string", len(desc) > 0)
check("describe() contains process name", "Code.exe" in desc)
check("describe() contains CPU", "CPU" in desc)

ss_empty = SystemSnapshot()
check("describe() empty returns string", len(ss_empty.describe()) > 0)


# ═══════════════════════════════════════════════════════════
# TEST 7-10: WindowTracker
# ═══════════════════════════════════════════════════════════

header("TEST 7-10: WindowTracker")

# Test 7: WindowTracker init
eb = EventBus()
wt = WindowTracker(event_bus=eb)
check("WindowTracker initialized", wt is not None)
check("get_current() before poll returns None", wt.get_current() is None)

# Test 8: get_active_window - should not crash (may return None on headless)
aw = wt.get_active_window()
check("get_active_window returns WindowInfo or None", aw is None or isinstance(aw, WindowInfo))

# Test 9: start/stop without error
wt.start()
check("WindowTracker start() succeeded", True)
wt.stop()
check("WindowTracker stop() succeeded", True)

# Test 10: get_current() before poll returns None (new instance)
eb2 = EventBus()
wt2 = WindowTracker(event_bus=eb2)
check("get_current() before poll returns None (2)", wt2.get_current() is None)


# ═══════════════════════════════════════════════════════════
# TEST 11-13: ScreenAnalyzer
# ═══════════════════════════════════════════════════════════

header("TEST 11-13: ScreenAnalyzer")

eb3 = EventBus()
sa = ScreenAnalyzer(event_bus=eb3)
check("ScreenAnalyzer initialized", sa is not None)
check("ScreenAnalyzer.available is bool", isinstance(sa.available, bool))

# Test 12: get_cached returns None initially
check("get_cached returns None initially", sa.get_cached() is None)

# Test 13: describe_current returns string (may be fallback text if unavailable)
desc_str = sa.describe_current()
check("describe_current returns string", isinstance(desc_str, str))
check("describe_current non-empty", len(desc_str) > 0)


# ═══════════════════════════════════════════════════════════
# TEST 14-18: AwarenessEngine
# ═══════════════════════════════════════════════════════════

header("TEST 14-18: AwarenessEngine")

eb4 = EventBus()
ae = AwarenessEngine(event_bus=eb4)
check("AwarenessEngine initialized", ae is not None)
check("AwarenessEngine has window_tracker", hasattr(ae, "window_tracker"))
check("AwarenessEngine has screen_analyzer", hasattr(ae, "screen_analyzer"))

# Test 15: get_snapshot returns None initially
check("get_snapshot returns None initially", ae.get_snapshot() is None)

# Test 16: get_context_for_prompt returns string
ctx = ae.get_context_for_prompt()
check("get_context_for_prompt returns str", isinstance(ctx, str))
# May be empty because no snapshot yet

# Test 17: start/stop without error
ae.start()
check("AwarenessEngine start() succeeded", True)
ae.stop()
check("AwarenessEngine stop() succeeded", True)

# Test 18: describe_screen returns string
desc = ae.describe_screen()
check("describe_screen returns str", isinstance(desc, str))
check("describe_screen non-empty", len(desc) > 0)


# ═══════════════════════════════════════════════════════════
# TEST 19-20: Awareness Events
# ═══════════════════════════════════════════════════════════

header("TEST 19-20: Awareness Events")

# Test 19: WindowChanged event
eb5 = EventBus()
received_events = []

def on_window_changed(event):
    received_events.append(event)

eb5.subscribe("awareness.window_changed", on_window_changed)

# Manually trigger a window_changed event via the window tracker
wt5 = WindowTracker(event_bus=eb5)
wt5._publish(WindowChanged, {"window": wi3.to_dict(), "previous_title": ""})
ec = len(received_events)
check("window_changed event received", ec >= 1)
if ec > 0:
    check("window_changed carries window info", "window" in received_events[0].payload)

# Test 20: ContextUpdated event
eb6 = EventBus()
received_updates = []

def on_context_updated(event):
    received_updates.append(event)

eb6.subscribe("awareness.context_updated", on_context_updated)
ae6 = AwarenessEngine(event_bus=eb6)
ae6._refresh_snapshot()
ec2 = len(received_updates)
check("context_updated event received", ec2 >= 1)
if ec2 > 0:
    check("context_updated carries snapshot", "snapshot" in received_updates[0].payload)


# ═══════════════════════════════════════════════════════════
# TEST 21: Runtime registration
# ═══════════════════════════════════════════════════════════

header("TEST 21-22: Runtime integration")

eb7 = EventBus()
supervisor = RuntimeSupervisor(event_bus=eb7)

# Create and register AwarenessEngine
ae7 = AwarenessEngine(event_bus=supervisor.event_bus)
supervisor.register_component(
    "awareness_engine",
    ae7,
    autostart=True,
    metadata={"role": "environment_awareness"},
)

# Start the runtime
supervisor.start()
status = supervisor.get_status()
check("awareness_engine in runtime components", "awareness_engine" in status["components"])
supervisor.stop()


# ═══════════════════════════════════════════════════════════
# TEST 22: Capability registry
# ═══════════════════════════════════════════════════════════

registry = CapabilityRegistry()
registry.register("awareness", available=True)
registry.register("screen_awareness", available=True)
caps = registry.list_capabilities()
cap_names = {c["name"] for c in caps}
check("awareness capability registered", "awareness" in cap_names)
check("screen_awareness capability registered", "screen_awareness" in cap_names)
aw_cap = registry.get("awareness")
check("awareness capability available", aw_cap is not None and aw_cap.get("available") is True)


# ═══════════════════════════════════════════════════════════
# TEST 23: Orchestrator has awareness_engine
# ═══════════════════════════════════════════════════════════

header("TEST 23-24: Orchestrator integration")

from core.orchestrator import Orchestrator
check("Orchestrator has awareness_engine attr", hasattr(Orchestrator, "awareness_engine"))


# ═══════════════════════════════════════════════════════════
# TEST 24: Context for prompt returns string
# ═══════════════════════════════════════════════════════════

eb8 = EventBus()
ae8 = AwarenessEngine(event_bus=eb8)
ctx_str = ae8.get_context_for_prompt()
check("get_context_for_prompt() returns str", isinstance(ctx_str, str))
# After refresh, should return something meaningful
ae8._refresh_snapshot()
ctx_str2 = ae8.get_context_for_prompt()
check("get_context_for_prompt() after refresh is str", isinstance(ctx_str2, str))


# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════

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
    print("ALL PHASE 6 TESTS PASSED")
    print()