"""
Phase 5B verification: Plan models, GoalDecomposer, Planner, events, runtime integration.

Required tests (24 total):
  1.  test_create_plan              — Plan created with correct defaults
  2.  test_create_plan_step         — PlanStep created with correct defaults
  3.  test_plan_serialization       — to_dict() / from_dict() round-trip
  4.  test_step_serialization       — PlanStep to_dict() / from_dict()
  5.  test_plan_step_count          — step_count() returns correct int
  6.  test_plan_is_ready            — is_ready() True when steps have titles
  7.  test_decompose_website        — "website" keyword -> website steps
  8.  test_decompose_react          — "react" keyword -> react steps
  9.  test_decompose_python         — "python" keyword -> python steps
  10. test_decompose_documentation  — "documentation" keyword -> doc steps
  11. test_decompose_default        — unknown goal -> default steps
  12. test_decompose_case_insensitive — "React Website" matches "react"
  13. test_add_template             — add_template() persists new template
  14. test_planner_create_plan      — create_plan() returns Plan with steps
  15. test_planner_get_plan         — get_plan() retrieves by ID
  16. test_planner_list_plans       — list_plans() returns all plans
  17. test_planner_list_by_status   — filter by status works
  18. test_planner_delete_plan      — delete_plan() removes from memory
  19. test_planner_update_plan      — update_plan() changes fields
  20. test_planner_summarize        — summarize() returns non-empty string
  21. test_plan_created_event       — EventBus receives planner.plan_created
  22. test_plan_updated_event       — EventBus receives planner.plan_updated
  23. test_runtime_registration     — Planner registered in RuntimeSupervisor
  24. test_capability_registered    — "planning" in CapabilityRegistry
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
from runtime.event_bus import EventBus
from runtime.planning import (
    GoalDecomposer, Plan, PlanCancelled, PlanCompleted,
    PlanCreated, PlanFailed, PlanPriority, PlanStatus,
    PlanStep, PlanUpdated, Planner,
)
from runtime import CapabilityRegistry, RuntimeSupervisor


# ── Test 1: Plan creation defaults ──────────────────────────
header("TEST 1: Plan creation defaults")
plan = Plan(
    id="plan-1",
    title="Test Plan",
    goal="Build a website",
)
check("id is set", plan.id == "plan-1")
check("title is set", plan.title == "Test Plan")
check("goal is set", plan.goal == "Build a website")
check("status is DRAFT", plan.status == PlanStatus.DRAFT)
check("priority is NORMAL", plan.priority == PlanPriority.NORMAL)
check("steps is empty list", plan.steps == [])
check("metadata is empty dict", plan.metadata == {})


# ── Test 2: PlanStep creation defaults ──────────────────────
header("TEST 2: PlanStep creation defaults")
step = PlanStep(id="step-1", title="Do something")
check("step id is set", step.id == "step-1")
check("step title is set", step.title == "Do something")
check("description defaults to empty", step.description == "")
check("status defaults to DRAFT", step.status == PlanStatus.DRAFT)
check("dependencies defaults to empty", step.dependencies == [])
check("estimated_duration defaults to 0", step.estimated_duration == 0)


# ── Test 3: Plan serialization ─────────────────────────────
header("TEST 3: Plan serialization round-trip")
import datetime as _dt
_now = _dt.datetime.now()
original_plan = Plan(
    id="serial-plan-1",
    title="Serialization Plan",
    goal="Test serialization",
    status=PlanStatus.ACTIVE,
    priority=PlanPriority.HIGH,
    steps=[PlanStep(id="ps1", title="Step A", created_at=_now, updated_at=_now)],
    metadata={"version": "1"},
    created_at=_now,
    updated_at=_now,
)
data = original_plan.to_dict()
restored_plan = Plan.from_dict(data)
check("plan id matches", restored_plan.id == original_plan.id)
check("plan title matches", restored_plan.title == original_plan.title)
check("plan goal matches", restored_plan.goal == original_plan.goal)
check("plan status matches", restored_plan.status == original_plan.status)
check("plan priority matches", restored_plan.priority == original_plan.priority)
check("plan steps count matches", len(restored_plan.steps) == 1)
check("plan metadata matches", restored_plan.metadata["version"] == "1")


# ── Test 4: PlanStep serialization ─────────────────────────
header("TEST 4: PlanStep serialization round-trip")
original_step = PlanStep(
    id="serial-step-1",
    title="Original Step",
    description="A description",
    status=PlanStatus.READY,
    dependencies=["dep-1"],
    estimated_duration=120,
    created_at=_now,
    updated_at=_now,
)
step_data = original_step.to_dict()
restored_step = PlanStep.from_dict(step_data)
check("step id matches", restored_step.id == original_step.id)
check("step title matches", restored_step.title == original_step.title)
check("step description matches", restored_step.description == "A description")
check("step status matches", restored_step.status == PlanStatus.READY)
check("step dependencies match", restored_step.dependencies == ["dep-1"])
check("step duration matches", restored_step.estimated_duration == 120)


# ── Test 5: Plan step_count ────────────────────────────────
header("TEST 5: Plan step_count")
plan_3 = Plan(id="pc-1", title="3 Steps", goal="goal", steps=[
    PlanStep(id="s1", title="1"),
    PlanStep(id="s2", title="2"),
    PlanStep(id="s3", title="3"),
])
check("step_count() returns 3", plan_3.step_count() == 3)

plan_0 = Plan(id="pc-2", title="0 Steps", goal="goal")
check("step_count() returns 0 for empty", plan_0.step_count() == 0)


# ── Test 6: Plan is_ready ──────────────────────────────────
header("TEST 6: Plan is_ready")
ready_plan = Plan(id="ready-1", title="Ready", goal="goal", steps=[
    PlanStep(id="s1", title="Step 1"),
    PlanStep(id="s2", title="Step 2"),
])
check("is_ready() True when steps have titles", ready_plan.is_ready())

empty_plan = Plan(id="empty-1", title="Empty", goal="goal")
check("is_ready() False when no steps", empty_plan.is_ready() is False)


# ── Test 7: decompose website ──────────────────────────────
header("TEST 7: GoalDecomposer — website")
decomposer = GoalDecomposer()
steps = decomposer.decompose("Create a website")
check("website steps match", steps == [
    "Define requirements",
    "Create project structure",
    "Build UI components",
    "Test website",
    "Deploy website",
])


# ── Test 8: decompose react ────────────────────────────────
header("TEST 8: GoalDecomposer — react")
steps = decomposer.decompose("Build a React app")
check("react steps match", steps[0] == "Define requirements")
check("react has 6 steps", len(steps) == 6)
check("react has Create React project", "Create React project" in steps)


# ── Test 9: decompose python ───────────────────────────────
header("TEST 9: GoalDecomposer — python")
steps = decomposer.decompose("Write a Python script")
check("python steps match", steps[0] == "Define requirements")
check("python has 5 steps", len(steps) == 5)
check("python has Implement features", "Implement features" in steps)


# ── Test 10: decompose documentation ────────────────────────
header("TEST 10: GoalDecomposer — documentation")
steps = decomposer.decompose("Write documentation for API")
check("documentation steps match", steps[0] == "Gather information")
check("documentation has 5 steps", len(steps) == 5)


# ── Test 11: decompose default ─────────────────────────────
header("TEST 11: GoalDecomposer — default fallback")
steps = decomposer.decompose("Something completely unknown and random")
check("default steps returned", steps == decomposer.TEMPLATES["default"])


# ── Test 12: case-insensitive matching ──────────────────────
header("TEST 12: GoalDecomposer — case insensitive")
steps_react = decomposer.decompose("REACT Website")
has_react_steps = "Create React project" in steps_react
has_website_steps = "Test website" in steps_react
check("REACT Website matches react or website", has_react_steps or has_website_steps,
      f"react={'Create React project' in steps_react} website={'Test website' in steps_react}")

steps = decomposer.decompose("Python API")
check("Python API matches python or api", "Implement features" in steps or "Design endpoints" in steps)


# ── Test 13: add_template ──────────────────────────────────
header("TEST 13: GoalDecomposer — add_template")
decomposer.add_template("custom", ["Step 1", "Step 2", "Step 3"])
steps = decomposer.decompose("do custom work")
check("custom template works", steps == ["Step 1", "Step 2", "Step 3"])
check("template names includes custom", "custom" in decomposer.get_template_names())


# ── Test 14: Planner create_plan ────────────────────────────
header("TEST 14: Planner create_plan")
bus = EventBus()
planner = Planner(event_bus=bus, goal_decomposer=GoalDecomposer())
plan = planner.create_plan("Build a website")
check("plan has id", plan.id is not None)
check("plan title is set", plan.title == "Build a website")
check("plan has 5 steps", plan.step_count() == 5)
check("plan status is DRAFT", plan.status == PlanStatus.DRAFT)
check("plan is in planner", planner.get_plan(plan.id) is not None)


# ── Test 15: Planner get_plan ──────────────────────────────
header("TEST 15: Planner get_plan")
plan2 = planner.create_plan("Test retrieval")
retrieved = planner.get_plan(plan2.id)
check("get_plan returns plan", retrieved is not None)
check("get_plan correct id", retrieved.id == plan2.id)
check("get_plan correct title", retrieved.title == "Test retrieval")

not_found = planner.get_plan("nonexistent")
check("get_plan returns None for missing", not_found is None)


# ── Test 16: Planner list_plans ────────────────────────────
header("TEST 16: Planner list_plans")
all_plans = planner.list_plans()
check("list_plans returns multiple", len(all_plans) >= 2)
ids = {p.id for p in all_plans}
check("plan from test 14 present", plan.id in ids)
check("plan from test 15 present", plan2.id in ids)


# ── Test 17: Planner list by status ────────────────────────
header("TEST 17: Planner list_plans by status")
draft_plans = planner.list_plans(status=PlanStatus.DRAFT)
check("draft plans returned", len(draft_plans) >= 2)
for p in draft_plans:
    check(f"  {p.id[:8]} is DRAFT", p.status == PlanStatus.DRAFT, f"got {p.status}")

active_plans = planner.list_plans(status=PlanStatus.ACTIVE)
check("no ACTIVE plans", len(active_plans) == 0)


# ── Test 18: Planner delete_plan ───────────────────────────
header("TEST 18: Planner delete_plan")
del_plan = planner.create_plan("Delete me")
check("plan exists before delete", planner.get_plan(del_plan.id) is not None)
deleted = planner.delete_plan(del_plan.id)
check("delete returns True", deleted is True)
check("plan gone after delete", planner.get_plan(del_plan.id) is None)

deleted_false = planner.delete_plan("nonexistent")
check("delete missing returns False", deleted_false is False)


# ── Test 19: Planner update_plan ───────────────────────────
header("TEST 19: Planner update_plan")
upd_plan = planner.create_plan("Original title")
updated = planner.update_plan(upd_plan.id, title="Updated title")
check("update returns plan", updated is not None)
check("title updated", updated.title == "Updated title")
check("goal unchanged", updated.goal == "Original title")

updated_bad = planner.update_plan("nonexistent", title="Nope")
check("update missing returns None", updated_bad is None)


# ── Test 20: Planner summarize ─────────────────────────────
header("TEST 20: Planner summarize")
sum_plan = planner.create_plan("API development")
summary = planner.summarize(sum_plan)
check("summary is non-empty", len(summary) > 0)
check("summary contains step count", "5 steps" in summary)
check("summary contains numbered steps", "1." in summary)
check("summary contains Plan title", "API development" in summary)

empty_for_summary = Plan(id="empty-sum", title="Empty", goal="goal")
empty_summary = planner.summarize(empty_for_summary)
check("empty plan summary mentions no steps", "no steps" in empty_summary)


# ── Test 21: Plan created event ────────────────────────────
header("TEST 21: Plan created event")
bus2 = EventBus()
planner2 = Planner(event_bus=bus2, goal_decomposer=GoalDecomposer())
received_events = []

def on_plan_created(event):
    received_events.append(event)

bus2.subscribe("planner.plan_created", on_plan_created)
event_plan = planner2.create_plan("Event test")
check("plan_created event received", len(received_events) == 1)
check("event carries plan id", received_events[0].payload["plan"]["id"] == event_plan.id)


# ── Test 22: Plan updated event ────────────────────────────
header("TEST 22: Plan updated event")
received_updates = []

def on_plan_updated(event):
    received_updates.append(event)

bus2.subscribe("planner.plan_updated", on_plan_updated)
planner2.update_plan(event_plan.id, title="Updated event title")
check("plan_updated event received", len(received_updates) == 1)
check("event carries plan title", received_updates[0].payload["plan"]["title"] == "Updated event title")


# ── Test 23: Runtime registration ──────────────────────────
header("TEST 23: Runtime registration")
rt_supervisor = RuntimeSupervisor()
gd = GoalDecomposer()
pln = Planner(event_bus=rt_supervisor.event_bus, goal_decomposer=gd)
rt_supervisor.register_component("planner", pln, autostart=True)
rt_supervisor.start()
check("planner component registered", "planner" in rt_supervisor.get_status()["components"])
check("planner is running", pln.is_running)
rt_supervisor.stop()


# ── Test 24: Capability registered ─────────────────────────
header("TEST 24: Capability registration")
registry = CapabilityRegistry()
registry.register("planning", available=True)
caps = registry.list_capabilities()
cap_names = {c["name"] for c in caps}
check("planning capability registered", "planning" in cap_names)
planning_cap = registry.get("planning")
check("planning capability available", planning_cap is not None)
check("planning available is True", planning_cap.get("available") is True)


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
    print("ALL PHASE 5B TESTS PASSED")
    print()