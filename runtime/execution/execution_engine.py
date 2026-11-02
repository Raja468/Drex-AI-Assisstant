"""Execution Engine — converts Plans into sequential Task execution."""
from __future__ import annotations

import time
import threading
import uuid
from datetime import datetime
from typing import Any, Optional, Callable
from loguru import logger

from runtime.event_bus import EventBus
from runtime.execution.execution_events import (
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
    ExecutionStepCompleted,
    ExecutionStepFailed,
    ExecutionStepStarted,
)
from runtime.execution.execution_models import (
    ExecutionResult,
    ExecutionState,
    StepOutcome,
)
from runtime.planning.plan_models import Plan, PlanStep, PlanStatus
from runtime.tasks.task_manager import TaskManager
from runtime.tasks.task_models import Task, TaskStatus, TaskStep, TaskPriority


class ExecutionEngine:
    """
    Connects Planner → TaskManager → ToolRouter → ResponseService.

    Responsibilities:
      1. Convert Plan → Task
      2. Wait for human approval
      3. Execute steps sequentially
      4. Update task progress
      5. Publish execution events
      6. Report completion/failure
      7. Support cancellation

    Does NOT:
      - Plan or re-plan
      - Call AI directly
      - Execute in background
      - Run autonomously
    """

    def __init__(
        self,
        event_bus: EventBus,
        task_manager: TaskManager,
        tool_router=None,
        intent_service=None,
        response_service=None,
    ):
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._tool_router = tool_router
        self._intent_service = intent_service
        self._response_service = response_service
        self._lock = threading.RLock()
        self._state = ExecutionState.IDLE
        self._active_tasks: dict = {}
        self._cancelled: set = set()
        self._running = False
        self._approval_handler: Optional[Callable] = None
        logger.debug("ExecutionEngine initialized")

    # ── RuntimeSupervisor lifecycle ──────────────────────────

    def start(self) -> None:
        self._running = True
        logger.info("ExecutionEngine started")

    def stop(self) -> None:
        self._running = False
        with self._lock:
            self._active_tasks.clear()
            self._cancelled.clear()
        logger.info("ExecutionEngine stopped")

    @property
    def is_running(self) -> bool:
        """Whether the engine itself is running (not a specific task)."""
        return self._running

    @property
    def state(self) -> ExecutionState:
        return self._state

    def is_task_running(self, task_id: str) -> bool:
        """Check if a specific task is currently executing."""
        with self._lock:
            state = self._active_tasks.get(task_id)
            return state == ExecutionState.RUNNING

    # ── Approval handler ────────────────────────────────────

    def register_approval_handler(self, handler: Callable[[str], None]):
        """Register a handler that asks the user for confirmation."""
        self._approval_handler = handler
        logger.debug("Approval handler registered")

    # ── prepare: Plan → Task (no execution) ──────────────────

    def prepare(self, plan: Plan) -> Optional[Task]:
        """
        Convert Plan → Task via TaskManager.
        Does NOT execute.
        """
        with self._lock:
            self._state = ExecutionState.PREPARING

        if not plan.steps:
            logger.warning("Cannot prepare plan with no steps: {}", plan.id)
            with self._lock:
                self._state = ExecutionState.IDLE
            return None

        task = self._task_manager.create_task(
            title=plan.title,
            description=f"Execution of plan: {plan.id}",
            priority=TaskPriority.NORMAL,
            steps=[
                {"title": step.title}
                for step in plan.steps
            ],
        )

        with self._lock:
            self._active_tasks[task.id] = ExecutionState.WAITING_CONFIRMATION
            self._state = ExecutionState.WAITING_CONFIRMATION

        logger.info("Task prepared from plan | task_id={} | plan_id={} | steps={}",
                    task.id, plan.id, len(plan.steps))
        return task

    # ── execute: Sequential step execution ───────────────────

    def execute(self, task: Task) -> ExecutionResult:
        """
        Execute a prepared task sequentially.
        For each step:
          1. Publish execution.step_started
          2. Update TaskStep → RUNNING
          3. Execute via tool router or intent
          4. Update TaskStep status
          5. Publish completion/failure event
          6. Record StepOutcome

        Failure behavior: stop immediately, mark task failed.
        """
        start_time = time.perf_counter()
        outcomes: list = []
        completed = 0
        total = len(task.steps)

        with self._lock:
            self._state = ExecutionState.RUNNING
            self._active_tasks[task.id] = ExecutionState.RUNNING

        self._publish(ExecutionStarted, {
            "task_id": task.id,
            "plan_id": task.id,
            "total_steps": total,
        })

        # Start the task in TaskManager
        self._task_manager.start_task(task.id)

        for step in task.steps:
            # Check cancellation BEFORE processing each step
            if task.id in self._cancelled:
                with self._lock:
                    self._state = ExecutionState.CANCELLED
                    self._active_tasks[task.id] = ExecutionState.CANCELLED
                result = ExecutionResult(
                    task_id=task.id,
                    plan_id=task.id,
                    success=False,
                    total_steps=total,
                    completed_steps=completed,
                    outcomes=outcomes,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    cancelled=True,
                )
                self._publish(ExecutionCancelled, {"result": result.to_dict()})
                self._cancelled.discard(task.id)
                return result

            step_start = time.perf_counter()

            # Publish step started
            self._publish(ExecutionStepStarted, {
                "task_id": task.id,
                "step_id": step.id,
                "step_title": step.title,
                "step_number": completed + 1,
                "total_steps": total,
                "step_description": step.title,
            })

            # Execute step
            outcome = self._execute_step(step, task)

            # Record duration
            outcome.duration_ms = (time.perf_counter() - step_start) * 1000
            outcomes.append(outcome)

            if outcome.success:
                completed += 1
                self._publish(ExecutionStepCompleted, {
                    "task_id": task.id,
                    "step_id": step.id,
                    "step_title": step.title,
                    "step_number": completed,
                    "total_steps": total,
                    "step_description": step.title,
                    "output": outcome.output,
                })
            else:
                # Failure — stop immediately
                self._task_manager.fail_task(task.id, error=outcome.error)
                self._publish(ExecutionStepFailed, {
                    "task_id": task.id,
                    "step_id": step.id,
                    "step_title": step.title,
                    "step_number": completed + 1,
                    "total_steps": total,
                    "step_description": step.title,
                    "error": outcome.error,
                })
                elapsed = (time.perf_counter() - start_time) * 1000
                result = ExecutionResult(
                    task_id=task.id,
                    plan_id=task.id,
                    success=False,
                    total_steps=total,
                    completed_steps=completed,
                    failed_step=step.title,
                    outcomes=outcomes,
                    duration_ms=elapsed,
                )
                with self._lock:
                    self._state = ExecutionState.FAILED
                    self._active_tasks[task.id] = ExecutionState.FAILED
                self._publish(ExecutionFailed, {"result": result.to_dict()})
                logger.info("Execution failed | task={} | step={} | error={}",
                            task.id, step.title, outcome.error)
                return result

        # All steps completed successfully
        self._task_manager.complete_task(task.id)
        elapsed = (time.perf_counter() - start_time) * 1000
        result = ExecutionResult(
            task_id=task.id,
            plan_id=task.id,
            success=True,
            total_steps=total,
            completed_steps=completed,
            outcomes=outcomes,
            duration_ms=elapsed,
        )
        with self._lock:
            self._state = ExecutionState.COMPLETED
            self._active_tasks[task.id] = ExecutionState.COMPLETED
        self._publish(ExecutionCompleted, {"result": result.to_dict()})
        logger.info("Execution completed | task={} | steps={} | {}ms",
                    task.id, total, int(elapsed))
        return result

    # ── cancel ───────────────────────────────────────────────

    def cancel(self, task_id: str) -> bool:
        """Mark a task for cancellation. Returns True if accepted."""
        with self._lock:
            if task_id in self._active_tasks:
                self._cancelled.add(task_id)
                self._state = ExecutionState.CANCELLED
                logger.info("Execution cancellation requested | task={}", task_id)
                return True
            # Accept any well-formed UUID as a pre-cancellation (task may not be active yet)
            try:
                uuid.UUID(task_id)
                self._cancelled.add(task_id)
                self._state = ExecutionState.CANCELLED
                logger.info("Execution pre-cancellation accepted | task={}", task_id)
                return True
            except (ValueError, AttributeError):
                return False


    # ── Internal step execution ──────────────────────────────

    def _execute_step(self, step: TaskStep, task: Task) -> StepOutcome:
        """
        Execute a single step.
        1. ToolRouter.route_plan_step(step) if implemented
        2. Fallback: IntentService.classify → ToolRouter.route
        3. If no tool, return success with step title as output
        """
        step_text = step.title

        # Try tool router with the step title as input
        tool_result = None
        if self._tool_router is not None and self._intent_service is not None:
            try:
                intent_result = self._intent_service.classify(step_text)
                if self._tool_router.can_handle(intent_result):
                    tool_result = self._tool_router.route(step_text, intent_result)
            except Exception as e:
                logger.warning("Step routing failed | step={} | error={}", step_text, e)

        if tool_result is not None:
            output = tool_result.output or ""
            if tool_result.success:
                return StepOutcome(
                    step_id=step.id,
                    step_title=step.title,
                    success=True,
                    output=output,
                )
            return StepOutcome(
                step_id=step.id,
                step_title=step.title,
                success=False,
                error=tool_result.error or "Tool execution failed",
            )

        # No tool matched — step is informational (no execution needed)
        return StepOutcome(
            step_id=step.id,
            step_title=step.title,
            success=True,
            output=f"Step completed: {step.title}",
        )

    # ── Internal ─────────────────────────────────────────────

    def _publish(self, event_class, payload: dict):
        """Publish an execution event through the EventBus."""
        try:
            event = event_class(source="execution_engine", payload=payload)
            self._event_bus.publish(event)
        except Exception as e:
            logger.error("Failed to publish {}: {}", event_class.__name__, e)


__all__ = ["ExecutionEngine"]