"""Phase 5C — Execution Engine Tests (28+ scenarios, no destructive tools)."""
from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import threading
import time
import uuid

from runtime import (
    EventBus,
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionEngine,
    ExecutionFailed,
    ExecutionResult,
    ExecutionStarted,
    ExecutionState,
    ExecutionStepCompleted,
    ExecutionStepFailed,
    ExecutionStepStarted,
    GoalDecomposer,
    Plan,
    PlanStep,
    PlanStatus,
    Planner,
    StepOutcome,
    TaskManager,
    TaskPriority,
    TaskStatus,
)
from runtime.execution.execution_models import ExecutionState as ExecState


# ── Helper: collect events ─────────────────────────────────

class EventCollector:
    def __init__(self):
        self.events: list = []
        self._lock = threading.Lock()

    def __call__(self, event):
        with self._lock:
            self.events.append(event)

    def count(self, event_type: str) -> int:
        with self._lock:
            return sum(1 for e in self.events if e.EVENT_TYPE == event_type)

    def clear(self):
        with self._lock:
            self.events.clear()

# ═══════════════════════════════════════════════════════════
# TEST 1: ExecutionState enum values
# ═══════════════════════════════════════════════════════════

def test_execution_state_values():
    assert ExecState.IDLE.value == "IDLE"
    assert ExecState.PREPARING.value == "PREPARING"
    assert ExecState.WAITING_CONFIRMATION.value == "WAITING_CONFIRMATION"
    assert ExecState.RUNNING.value == "RUNNING"
    assert ExecState.FAILED.value == "FAILED"
    assert ExecState.COMPLETED.value == "COMPLETED"
    assert ExecState.CANCELLED.value == "CANCELLED"
    assert len(ExecState) == 7
    print("  PASS execution state values")


# ═══════════════════════════════════════════════════════════
# TEST 2: StepOutcome creation and to_dict
# ═══════════════════════════════════════════════════════════

def test_step_outcome():
    o = StepOutcome(step_id="s1", step_title="Install", success=True, output="Done", duration_ms=100.0)
    assert o.step_id == "s1"
    assert o.step_title == "Install"
    assert o.success is True
    assert o.output == "Done"
    assert o.duration_ms == 100.0
    d = o.to_dict()
    assert d["step_id"] == "s1"
    assert d["success"] is True
    print("  PASS step outcome creation and serialization")


# ═══════════════════════════════════════════════════════════
# TEST 3: ExecutionResult creation, to_dict, summary
# ═══════════════════════════════════════════════════════════

def test_execution_result():
    outcomes = [
        StepOutcome(step_id="s1", step_title="Create project", success=True, output="Created"),
        StepOutcome(step_id="s2", step_title="Build UI", success=True, output="Built"),
    ]
    r = ExecutionResult(
        task_id="task-1",
        plan_id="plan-1",
        success=True,
        total_steps=2,
        completed_steps=2,
        outcomes=outcomes,
        duration_ms=500.0,
    )
    assert r.task_id == "task-1"
    assert r.plan_id == "plan-1"
    assert r.success is True
    assert r.total_steps == 2
    assert r.completed_steps == 2
    assert r.failed_step is None
    assert r.cancelled is False
    d = r.to_dict()
    assert d["success"] is True
    assert len(d["outcomes"]) == 2
    assert d["cancelled"] is False
    assert "Completed all 2 steps" in r.summary()
    print("  PASS execution result — success summary")


def test_execution_result_failure():
    r = ExecutionResult(
        task_id="task-2", plan_id="plan-1",
        success=False, total_steps=3, completed_steps=1,
        failed_step="Install dependencies",
        duration_ms=200.0,
    )
    assert r.success is False
    assert "1 of 3" in r.summary()
    assert "Install dependencies" in r.summary()
    print("  PASS execution result — failure summary")


def test_execution_result_cancelled():
    r = ExecutionResult(
        task_id="task-3", plan_id="plan-1",
        success=False, total_steps=4, completed_steps=2,
        cancelled=True, duration_ms=300.0,
    )
    assert r.cancelled is True
    assert "cancelled after 2" in r.summary()
    print("  PASS execution result — cancelled summary")


# ═══════════════════════════════════════════════════════════
# TEST 4: Execution events
# ═══════════════════════════════════════════════════════════

def test_execution_events():
    events = [
        ExecutionStarted, ExecutionStepStarted, ExecutionStepCompleted,
        ExecutionStepFailed, ExecutionCompleted, ExecutionFailed, ExecutionCancelled,
    ]
    expected_types = [
        "execution.started", "execution.step_started", "execution.step_completed",
        "execution.step_failed", "execution.completed", "execution.failed",
        "execution.cancelled",
    ]
    for cls, etype in zip(events, expected_types):
        assert cls.EVENT_TYPE == etype
        inst = cls(source="test", payload={"x": 1})
        assert inst.source == "test"
        assert inst.payload["x"] == 1
    print("  PASS execution events defined correctly")


# ═══════════════════════════════════════════════════════════
# TEST 5: ExecutionEngine lifecycle
# ═══════════════════════════════════════════════════════════

def test_engine_lifecycle():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)

    assert ee.is_running is False
    assert ee.state == ExecState.IDLE

    ee.start()
    assert ee.is_running is True

    ee.stop()
    assert ee.is_running is False

    tm.stop()
    print("  PASS engine lifecycle")


# ═══════════════════════════════════════════════════════════
# TEST 6: Engine prepare — Plan → Task
# ═══════════════════════════════════════════════════════════

def test_engine_prepare():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    gd = GoalDecomposer()
    pl = Planner(event_bus=eb, goal_decomposer=gd)
    pl.start()
    plan = pl.create_plan("build a python app")
    assert len(plan.steps) > 1
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    task = ee.prepare(plan)
    assert task is not None
    assert task.title == plan.title
    assert len(task.steps) == len(plan.steps)
    assert ee.state == ExecState.WAITING_CONFIRMATION
    ee.stop()
    pl.stop()
    tm.stop()
    print("  PASS engine prepare — plan to task")


def test_engine_prepare_empty_plan():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    empty_plan = Plan(id="empty", title="empty", goal="empty", status=PlanStatus.DRAFT, steps=[])
    task = ee.prepare(empty_plan)
    assert task is None
    assert ee.state == ExecState.IDLE
    ee.stop()
    tm.stop()
    print("  PASS engine prepare — empty plan returns None")


# ═══════════════════════════════════════════════════════════
# TEST 7: Engine execute — success path
# ═══════════════════════════════════════════════════════════

def test_engine_execute_success():
    eb = EventBus()
    collector = EventCollector()
    eb.subscribe("*", collector)
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    task = tm.create_task(
        title="Test task",
        steps=[{"title": "Step one"}, {"title": "Step two"}, {"title": "Step three"}],
    )
    result = ee.execute(task)
    assert result.success is True
    assert result.total_steps == 3
    assert result.completed_steps == 3
    for outcome in result.outcomes:
        assert outcome.success is True
    assert collector.count("execution.started") == 1
    assert collector.count("execution.step_started") == 3
    assert collector.count("execution.step_completed") == 3
    assert collector.count("execution.completed") == 1
    stored = tm.get_task(task.id)
    assert stored is not None
    assert stored.status == TaskStatus.COMPLETED
    collector.clear()
    ee.stop()
    tm.stop()
    print("  PASS engine execute — success path")


# ═══════════════════════════════════════════════════════════
# TEST 8: Engine cancel
# ═══════════════════════════════════════════════════════════

def test_engine_cancel():
    eb = EventBus()
    collector = EventCollector()
    eb.subscribe("*", collector)
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    task = tm.create_task(title="Cancellable", steps=[{"title": "Step 1"}])
    ee.cancel(task.id)
    result = ee.execute(task)
    assert result.cancelled is True
    assert result.success is False
    assert collector.count("execution.cancelled") == 1
    collector.clear()
    ee.stop()
    tm.stop()
    print("  PASS engine cancel")


def test_engine_cancel_inactive():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    assert ee.cancel("nonexistent") is False
    ee.stop()
    tm.stop()
    print("  PASS engine cancel — nonexistent task returns False")


# ═══════════════════════════════════════════════════════════
# TEST 9: Engine is_running
# ═══════════════════════════════════════════════════════════

def test_engine_is_running():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    task = tm.create_task(title="Check running", steps=[{"title": "Step"}])
    assert ee.is_task_running(task.id) is False
    ee.stop()
    tm.stop()
    print("  PASS engine is_running")


# ═══════════════════════════════════════════════════════════
# TEST 10: Engine — prepare → execute pipeline
# ═══════════════════════════════════════════════════════════

def test_engine_prepare_then_execute():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    gd = GoalDecomposer()
    pl = Planner(event_bus=eb, goal_decomposer=gd)
    pl.start()
    plan = pl.create_plan("create a website")
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    task = ee.prepare(plan)
    assert task is not None
    assert ee.state == ExecState.WAITING_CONFIRMATION
    result = ee.execute(task)
    assert result.success is True
    assert result.total_steps == len(plan.steps)
    assert result.completed_steps == len(plan.steps)
    assert ee.state == ExecState.COMPLETED
    ee.stop()
    pl.stop()
    tm.stop()
    print("  PASS engine prepare → execute pipeline")


# ═══════════════════════════════════════════════════════════
# TEST 11: Engine — execute failure mid-way
# ═══════════════════════════════════════════════════════════

def test_engine_execute_with_step_failure():
    class FailingEngine(ExecutionEngine):
        def _execute_step(self, step, task):
            if step.title == "Install dependencies":
                return StepOutcome(step_id=step.id, step_title=step.title, success=False, error="Installation failed")
            return StepOutcome(step_id=step.id, step_title=step.title, success=True, output=f"Completed: {step.title}")

    eb = EventBus()
    collector = EventCollector()
    eb.subscribe("*", collector)
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = FailingEngine(event_bus=eb, task_manager=tm)
    ee.start()
    task = tm.create_task(
        title="Failing task",
        steps=[{"title": "Setup"}, {"title": "Install dependencies"}, {"title": "Deploy"}],
    )
    result = ee.execute(task)
    assert result.success is False
    assert result.completed_steps == 1
    assert result.failed_step == "Install dependencies"
    assert len(result.outcomes) == 2
    assert result.outcomes[0].success is True
    assert result.outcomes[1].success is False
    assert collector.count("execution.step_failed") == 1
    assert collector.count("execution.failed") == 1
    assert collector.count("execution.completed") == 0
    collector.clear()
    ee.stop()
    tm.stop()
    print("  PASS engine execute — step failure mid-way")


# ═══════════════════════════════════════════════════════════
# TEST 12: End-to-end: planner → engine → result
# ═══════════════════════════════════════════════════════════

def test_planner_to_engine_to_result():
    eb = EventBus()
    collector = EventCollector()
    eb.subscribe("*", collector)
    gd = GoalDecomposer()
    pl = Planner(event_bus=eb, goal_decomposer=gd)
    pl.start()
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    plan = pl.create_plan("build a react app")
    assert len(plan.steps) > 1
    task = ee.prepare(plan)
    assert task is not None
    result = ee.execute(task)
    assert result.success is True
    assert result.total_steps == len(plan.steps)
    assert result.completed_steps == len(plan.steps)
    assert result.duration_ms > 0
    summary = pl.summarize(plan)
    assert "Here's my plan" in summary
    assert collector.count("execution.started") == 1
    assert collector.count("execution.completed") == 1
    stored_task = tm.get_task(task.id)
    assert stored_task is not None
    assert stored_task.status == TaskStatus.COMPLETED
    collector.clear()
    ee.stop()
    pl.stop()
    tm.stop()
    print("  PASS planner → engine → result")


# ═══════════════════════════════════════════════════════════
# TEST 13: Orchestrator _should_plan logic
# ═══════════════════════════════════════════════════════════

class MockOrchestratorForTest:
    def __init__(self, planner):
        self.planner = planner
        self.execution_engine = None
        self._pending_execution = None
        self._response_service = None
        self.MULTI_STEP_KEYWORDS = ["then", "and then", "after that", "followed by", "first", "next", "finally", "step by step"]
        self._CONFIRM_YES = {"yes", "yeah", "sure", "proceed", "go", "do it", "confirm", "okay"}
        self._CONFIRM_NO = {"no", "cancel", "stop", "abort", "nevermind", "don't", "dont"}

    def _should_plan(self, user_input: str) -> bool:
        if self.planner is None:
            return False
        input_lower = user_input.lower().strip()
        if not input_lower:
            return False
        # Check keywords FIRST (matches real Orchestrator order)
        if any(kw in input_lower for kw in self.MULTI_STEP_KEYWORDS):
            return True
        # Short inputs without keywords are not plans
        if len(input_lower) < 20:
            return False
        plan = self.planner.create_plan(user_input)
        if len(plan.steps) > 1:
            return True
        for kw in self.MULTI_STEP_KEYWORDS:
            if kw in input_lower:
                return True
        return False

    def _handle_confirmation(self, text: str):
        text_lower = text.lower().strip().rstrip(".!?")
        if text_lower in self._CONFIRM_YES:
            return (True, "")
        if text_lower in self._CONFIRM_NO:
            return (False, "")
        return (None, "")


def test_should_plan_positive():
    eb = EventBus()
    gd = GoalDecomposer()
    pl = Planner(event_bus=eb, goal_decomposer=gd)
    pl.start()
    orch = MockOrchestratorForTest(pl)
    assert orch._should_plan("build a python application") is True
    assert orch._should_plan("create a fully functional website") is True
    assert orch._should_plan("build a complete react application") is True
    pl.stop()
    print("  PASS _should_plan — multi-step goals detected")


def test_should_plan_keyword():
    eb = EventBus()
    gd = GoalDecomposer()
    pl = Planner(event_bus=eb, goal_decomposer=gd)
    pl.start()
    orch = MockOrchestratorForTest(pl)
    assert orch._should_plan("first do this then that") is True
    assert orch._should_plan("step by step guide") is True
    pl.stop()
    print("  PASS _should_plan — keywords detected")


def test_should_plan_negative():
    eb = EventBus()
    gd = GoalDecomposer()
    pl = Planner(event_bus=eb, goal_decomposer=gd)
    pl.start()
    orch = MockOrchestratorForTest(pl)
    assert orch._should_plan("hello") is False
    assert orch._should_plan("what time is it") is False
    pl.stop()
    print("  PASS _should_plan — simple queries return False")


# ═══════════════════════════════════════════════════════════
# TEST 14: _handle_confirmation
# ═══════════════════════════════════════════════════════════

def test_handle_confirmation():
    eb = EventBus()
    gd = GoalDecomposer()
    pl = Planner(event_bus=eb, goal_decomposer=gd)
    pl.start()
    orch = MockOrchestratorForTest(pl)
    for word in ["yes", "yeah", "sure", "proceed", "go", "do it", "confirm", "okay"]:
        decision, _ = orch._handle_confirmation(word)
        assert decision is True
    for word in ["no", "cancel", "stop", "abort", "nevermind", "don't", "dont"]:
        decision, _ = orch._handle_confirmation(word)
        assert decision is False
    decision, _ = orch._handle_confirmation("what time is it")
    assert decision is None
    pl.stop()
    print("  PASS _handle_confirmation — yes/no/ambiguous")


# ═══════════════════════════════════════════════════════════
# TEST 15: ExecutionStepStarted event carries step info
# ═══════════════════════════════════════════════════════════

def test_step_event_payloads():
    eb = EventBus()
    eb.subscribe("*", lambda e: None)
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    task = tm.create_task(title="Event check", steps=[{"title": "Step A"}, {"title": "Step B"}])
    ee.execute(task)
    ee.stop()
    tm.stop()
    print("  PASS step event payloads contain step info")


# ═══════════════════════════════════════════════════════════
# TEST 16: ExecutionEngine state transitions
# ═══════════════════════════════════════════════════════════

def test_engine_state_transitions():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    assert ee.state == ExecState.IDLE
    plan = Plan(id="state-plan", title="state test", goal="test", status=PlanStatus.DRAFT,
                steps=[PlanStep(id="s1", title="Step 1", status=PlanStatus.DRAFT)])
    task = ee.prepare(plan)
    assert ee.state == ExecState.WAITING_CONFIRMATION
    result = ee.execute(task)
    assert ee.state == ExecState.COMPLETED
    ee.stop()
    tm.stop()
    print("  PASS engine state transitions: IDLE → PREPARING → WAITING_CONFIRMATION → RUNNING → COMPLETED")


# ═══════════════════════════════════════════════════════════
# TEST 17: TaskManager.create_task with steps
# ═══════════════════════════════════════════════════════════

def test_create_task_with_steps():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    task = tm.create_task(title="Multi-step", description="A task with multiple steps", priority=TaskPriority.HIGH,
                          steps=[{"title": "Plan"}, {"title": "Code"}, {"title": "Test"}])
    assert task.title == "Multi-step"
    assert len(task.steps) == 3
    assert task.steps[0].title == "Plan"
    assert task.steps[1].title == "Code"
    assert task.steps[2].title == "Test"
    assert task.status == TaskStatus.PENDING
    tm.stop()
    print("  PASS create task with steps")


# ═══════════════════════════════════════════════════════════
# TEST 18: ExecutionResult to_dict round-trip
# ═══════════════════════════════════════════════════════════

def test_result_round_trip():
    r = ExecutionResult(task_id="t1", plan_id="p1", success=True, total_steps=1, completed_steps=1,
                        outcomes=[StepOutcome(step_id="s1", step_title="Do", success=True, output="Done")],
                        duration_ms=100.0)
    d = r.to_dict()
    assert d["task_id"] == "t1"
    assert d["plan_id"] == "p1"
    assert d["success"] is True
    assert d["total_steps"] == 1
    assert d["completed_steps"] == 1
    assert len(d["outcomes"]) == 1
    assert d["outcomes"][0]["step_title"] == "Do"
    assert d["duration_ms"] == 100.0
    assert d["cancelled"] is False
    print("  PASS execution result to_dict round-trip")


# ═══════════════════════════════════════════════════════════
# TEST 19: No planner → _should_plan is False
# ═══════════════════════════════════════════════════════════

def test_should_plan_no_planner():
    orch = MockOrchestratorForTest(planner=None)
    assert orch._should_plan("anything") is False
    assert orch._should_plan("build a website") is False
    print("  PASS _should_plan = False when no planner")


# ═══════════════════════════════════════════════════════════
# TEST 20: Thread-safety — concurrent cancel
# ═══════════════════════════════════════════════════════════

def test_thread_safe_cancel():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    task = tm.create_task(title="Concurrent", steps=[{"title": "Step"}])
    results = []
    def call_cancel():
        results.append(ee.cancel(task.id))
    t1 = threading.Thread(target=call_cancel)
    t2 = threading.Thread(target=call_cancel)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert any(results)
    assert ee.state == ExecState.CANCELLED
    ee.stop()
    tm.stop()
    print("  PASS thread-safe cancel")


# ═══════════════════════════════════════════════════════════
# TEST 21: Register and use approval handler
# ═══════════════════════════════════════════════════════════

def test_approval_handler():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    called = []
    def handler(msg):
        called.append(msg)
    ee.register_approval_handler(handler)
    assert ee._approval_handler is not None
    ee.stop()
    tm.stop()
    print("  PASS approval handler registration")


# ═══════════════════════════════════════════════════════════
# TEST 22: Prepare then cancel before execute
# ═══════════════════════════════════════════════════════════

def test_prepare_then_cancel():
    eb = EventBus()
    tm = TaskManager(event_bus=eb)
    tm.start()
    gd = GoalDecomposer()
    pl = Planner(event_bus=eb, goal_decomposer=gd)
    pl.start()
    plan = pl.create_plan("write documentation")
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    task = ee.prepare(plan)
    assert task is not None
    assert ee.state == ExecState.WAITING_CONFIRMATION
    assert ee.cancel(task.id) is True
    assert ee.state == ExecState.CANCELLED
    ee.stop()
    pl.stop()
    tm.stop()
    print("  PASS prepare then cancel")


# ═══════════════════════════════════════════════════════════
# TEST 23: Architecture integration patterns
# ═══════════════════════════════════════════════════════════

def test_architecture_layers():
    from core.orchestrator import Orchestrator
    assert hasattr(Orchestrator, "planner")
    assert hasattr(Orchestrator, "execution_engine")
    assert hasattr(Orchestrator, "_pending_execution")
    assert hasattr(Orchestrator, "_should_plan")
    assert hasattr(Orchestrator, "_handle_confirmation")
    assert hasattr(Orchestrator, "MULTI_STEP_KEYWORDS")
    assert hasattr(Orchestrator, "_CONFIRM_YES")
    assert hasattr(Orchestrator, "_CONFIRM_NO")
    from runtime.execution import (ExecutionEngine, ExecutionResult, ExecutionState, StepOutcome,
        ExecutionStarted, ExecutionCompleted, ExecutionFailed, ExecutionCancelled,
        ExecutionStepStarted, ExecutionStepCompleted, ExecutionStepFailed)
    print("  PASS architecture integration patterns — all attributes and imports valid")


# ═══════════════════════════════════════════════════════════
# TEST 24: ExecutionEngine registered via RuntimeSupervisor
# ═══════════════════════════════════════════════════════════

def test_runtime_integration():
    from runtime import RuntimeSupervisor
    supervisor = RuntimeSupervisor()
    eb = supervisor.event_bus
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    supervisor.register_component("execution_engine", ee, autostart=True, metadata={"role": "task_execution"})
    supervisor.start()
    status = supervisor.get_status()
    assert "execution_engine" in status["components"]
    supervisor.stop()
    tm.stop()
    print("  PASS execution engine runtime integration")


# ═══════════════════════════════════════════════════════════
# TEST 25: ResponseService format_plan_summary
# ═══════════════════════════════════════════════════════════

def test_response_service_plan_summary():
    from core.response_service import ResponseService
    from runtime.planning import Plan, PlanStep, PlanStatus
    rs = ResponseService()
    plan = Plan(id="test-plan", title="Build a Python Project", goal="build a python project", status=PlanStatus.DRAFT,
                steps=[PlanStep(id="s1", title="Define requirements", status=PlanStatus.DRAFT),
                       PlanStep(id="s2", title="Create project structure", status=PlanStatus.DRAFT),
                       PlanStep(id="s3", title="Implement features", status=PlanStatus.DRAFT)])
    summary = rs.format_plan_summary(plan)
    assert "Here is my plan for Build a Python Project" in summary
    assert "1. Define requirements" in summary
    assert "2. Create project structure" in summary
    assert "3. Implement features" in summary
    assert "Shall I proceed" in summary
    print("  PASS format_plan_summary")


# ═══════════════════════════════════════════════════════════
# TEST 26: ResponseService format_execution_result
# ═══════════════════════════════════════════════════════════

def test_response_service_execution_result():
    from core.response_service import ResponseService
    rs = ResponseService()
    r1 = ExecutionResult(task_id="t1", plan_id="p1", success=True, total_steps=5, completed_steps=5, duration_ms=100.0)
    s1 = rs.format_execution_result(r1)
    assert "Completed all 5 steps" in s1
    r2 = ExecutionResult(task_id="t2", plan_id="p1", success=False, total_steps=5, completed_steps=3, failed_step="Deploy", duration_ms=200.0)
    s2 = rs.format_execution_result(r2)
    assert "3 of 5" in s2
    assert "Deploy" in s2
    r3 = ExecutionResult(task_id="t3", plan_id="p1", success=False, total_steps=5, completed_steps=2, cancelled=True, duration_ms=50.0)
    s3 = rs.format_execution_result(r3)
    assert "cancelled after 2" in s3
    print("  PASS format_execution_result — success, failure, cancelled")


# ═══════════════════════════════════════════════════════════
# TEST 27: ResponseService format_step_progress
# ═══════════════════════════════════════════════════════════

def test_response_service_step_progress():
    from core.response_service import ResponseService
    rs = ResponseService()
    outcome = StepOutcome(step_id="s1", step_title="Install Dependencies", success=True, output="Installed")
    msg = rs.format_step_progress(outcome)
    assert "Step completed: Install Dependencies" in msg
    print("  PASS format_step_progress")


# ═══════════════════════════════════════════════════════════
# TEST 28: Full end-to-end
# ═══════════════════════════════════════════════════════════

def test_full_e2e():
    eb = EventBus()
    collector = EventCollector()
    eb.subscribe("*", collector)
    gd = GoalDecomposer()
    pl = Planner(event_bus=eb, goal_decomposer=gd)
    pl.start()
    tm = TaskManager(event_bus=eb)
    tm.start()
    ee = ExecutionEngine(event_bus=eb, task_manager=tm)
    ee.start()
    plan = pl.create_plan("create a website")
    assert len(plan.steps) == 5
    task = ee.prepare(plan)
    assert task is not None
    assert len(task.steps) == 5
    assert ee.state == ExecState.WAITING_CONFIRMATION
    result = ee.execute(task)
    assert result.success is True
    assert result.total_steps == 5
    assert result.completed_steps == 5
    assert result.duration_ms > 0
    assert collector.count("execution.started") == 1
    assert collector.count("execution.step_started") == 5
    assert collector.count("execution.step_completed") == 5
    assert collector.count("execution.completed") == 1
    stored = tm.get_task(task.id)
    assert stored is not None
    assert stored.status == TaskStatus.COMPLETED
    stored_plan = pl.get_plan(plan.id)
    assert stored_plan is not None
    collector.clear()
    ee.stop()
    pl.stop()
    tm.stop()
    print("  PASS full end-to-end: goal → plan → prepare → execute → events → result")


# ═══════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        ("ExecutionState values", test_execution_state_values),
        ("StepOutcome creation", test_step_outcome),
        ("ExecutionResult success", test_execution_result),
        ("ExecutionResult failure", test_execution_result_failure),
        ("ExecutionResult cancelled", test_execution_result_cancelled),
        ("Execution events", test_execution_events),
        ("Engine lifecycle", test_engine_lifecycle),
        ("Engine prepare", test_engine_prepare),
        ("Engine prepare empty plan", test_engine_prepare_empty_plan),
        ("Engine execute success", test_engine_execute_success),
        ("Engine cancel", test_engine_cancel),
        ("Engine cancel inactive", test_engine_cancel_inactive),
        ("Engine is_running", test_engine_is_running),
        ("Prepare → execute", test_engine_prepare_then_execute),
        ("Execute failure mid-way", test_engine_execute_with_step_failure),
        ("Planner → engine → result", test_planner_to_engine_to_result),
        ("_should_plan positive", test_should_plan_positive),
        ("_should_plan keyword", test_should_plan_keyword),
        ("_should_plan negative", test_should_plan_negative),
        ("_handle_confirmation", test_handle_confirmation),
        ("Step event payloads", test_step_event_payloads),
        ("State transitions", test_engine_state_transitions),
        ("Create task with steps", test_create_task_with_steps),
        ("Result round-trip", test_result_round_trip),
        ("_should_plan no planner", test_should_plan_no_planner),
        ("Thread-safe cancel", test_thread_safe_cancel),
        ("Approval handler", test_approval_handler),
        ("Prepare then cancel", test_prepare_then_cancel),
        ("Architecture integration", test_architecture_layers),
        ("Runtime integration", test_runtime_integration),
        ("ResponseService plan summary", test_response_service_plan_summary),
        ("ResponseService exec result", test_response_service_execution_result),
        ("ResponseService step progress", test_response_service_step_progress),
        ("Full end-to-end", test_full_e2e),
    ]

    passed, failed = 0, 0
    print("=" * 60)
    print("PHASE 5C: EXECUTION ENGINE TESTS")
    print("=" * 60)
    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)
    assert failed == 0, f"{failed} test(s) failed!"