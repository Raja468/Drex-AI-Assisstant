"""Main planning service — creates, stores, and manages Plans."""
from __future__ import annotations

import uuid
import threading
from datetime import datetime
from typing import Any, Optional
from loguru import logger

from runtime.event_bus import EventBus
from runtime.planning.goal_decomposer import GoalDecomposer
from runtime.planning.plan_models import Plan, PlanPriority, PlanStatus, PlanStep
from runtime.planning.planner_events import (
    PlanCancelled,
    PlanCompleted,
    PlanCreated,
    PlanFailed,
    PlanUpdated,
)


class Planner:
    """
    Main planning service.
    Creates, stores, and manages Plans.
    Stores plans in memory only (Phase 5B).
    Publishes events through EventBus.
    Does NOT execute tools. Does NOT call AI.
    """

    def __init__(self, event_bus: EventBus, goal_decomposer: GoalDecomposer):
        self._plans: dict[str, Plan] = {}
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._decomposer = goal_decomposer
        self._running = False
        logger.debug("Planner initialized")

    # ── RuntimeSupervisor lifecycle ──────────────────────────

    def start(self) -> None:
        """Initialize — log ready state."""
        self._running = True
        logger.info("Planner started | in-memory store ready")

    def stop(self) -> None:
        """Clean shutdown — clear in-memory plans, log."""
        self._running = False
        with self._lock:
            count = len(self._plans)
            self._plans.clear()
        logger.info("Planner stopped | {} plans cleared", count)

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Plan CRUD ────────────────────────────────────────────

    def create_plan(
        self,
        goal: str,
        priority: PlanPriority = PlanPriority.NORMAL,
        metadata: dict[str, Any] = None,
    ) -> Plan:
        """
        1. Decompose goal into step list via GoalDecomposer
        2. Create PlanStep for each step string
        3. Create Plan with all steps
        4. Store in self._plans
        5. Publish planner.plan_created event
        6. Log with loguru
        7. Return Plan
        """
        step_titles = self._decomposer.decompose(goal)
        now = datetime.now()
        steps = [
            PlanStep(
                id=str(uuid.uuid4()),
                title=title,
                status=PlanStatus.DRAFT,
                created_at=now,
                updated_at=now,
            )
            for title in step_titles
        ]

        plan = Plan(
            id=str(uuid.uuid4()),
            title=goal[:80] if len(goal) > 80 else goal,
            goal=goal,
            status=PlanStatus.DRAFT,
            priority=priority,
            steps=steps,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._plans[plan.id] = plan

        self._publish(PlanCreated, {"plan": plan.to_dict()})
        logger.info("Plan created | id={} | title={} | steps={}", plan.id, plan.title, len(steps))
        return plan

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Return plan by ID or None if not found."""
        with self._lock:
            return self._plans.get(plan_id)

    def list_plans(self, status: PlanStatus = None) -> list[Plan]:
        """Return all plans, optionally filtered by status."""
        with self._lock:
            plans = list(self._plans.values())
        if status:
            plans = [p for p in plans if p.status == status]
        return sorted(plans, key=lambda p: p.created_at, reverse=True)

    def update_plan(self, plan_id: str, **kwargs) -> Optional[Plan]:
        """Update plan fields, publish planner.plan_updated, return updated Plan."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return None
            for key, value in kwargs.items():
                if hasattr(plan, key) and key not in ("id", "created_at", "steps"):
                    setattr(plan, key, value)
            plan.updated_at = datetime.now()
        self._publish(PlanUpdated, {"plan": plan.to_dict()})
        logger.info("Plan updated | id={}", plan_id)
        return plan

    def delete_plan(self, plan_id: str) -> bool:
        """Remove plan from memory, return True if deleted."""
        with self._lock:
            if plan_id in self._plans:
                del self._plans[plan_id]
                logger.info("Plan deleted | id={}", plan_id)
                return True
        return False

    def summarize(self, plan: Plan) -> str:
        """
        Return human-readable plan summary for user confirmation.
        Example:
          "Here's my plan for 3 steps:
           1. Create React project
           2. Install dependencies
           3. Deploy application"
        """
        if not plan.steps:
            return f"Plan '{plan.title}' has no steps yet."

        lines = [f"Here's my plan for {plan.title} ({len(plan.steps)} steps):"]
        for i, step in enumerate(plan.steps, 1):
            lines.append(f"  {i}. {step.title}")
        return "\n".join(lines)

    # ── Internal ─────────────────────────────────────────────

    def _publish(self, event_class, payload: dict):
        """Publish a planner event through the EventBus."""
        try:
            event = event_class(source="planner", payload=payload)
            self._event_bus.publish(event)
        except Exception as e:
            logger.error("Failed to publish {}: {}", event_class.__name__, e)


__all__ = ["Planner"]