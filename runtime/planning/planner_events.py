"""Plan lifecycle events published through the EventBus."""
from runtime.events import RuntimeEvent


class PlanCreated(RuntimeEvent):
    EVENT_TYPE = "planner.plan_created"


class PlanUpdated(RuntimeEvent):
    EVENT_TYPE = "planner.plan_updated"


class PlanCompleted(RuntimeEvent):
    EVENT_TYPE = "planner.plan_completed"


class PlanFailed(RuntimeEvent):
    EVENT_TYPE = "planner.plan_failed"


class PlanCancelled(RuntimeEvent):
    EVENT_TYPE = "planner.plan_cancelled"


__all__ = [
    "PlanCancelled", "PlanCompleted", "PlanCreated",
    "PlanFailed", "PlanUpdated",
]