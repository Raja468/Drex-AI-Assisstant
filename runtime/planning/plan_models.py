"""Plan data models with serialization support."""
from __future__ import annotations

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlanStatus(Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PlanPriority(Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class PlanStep:
    id: str
    title: str
    description: str = ""
    status: PlanStatus = PlanStatus.DRAFT
    dependencies: list[str] = field(default_factory=list)
    estimated_duration: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "dependencies": list(self.dependencies),
            "estimated_duration": self.estimated_duration,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=PlanStatus(data.get("status", "DRAFT")),
            dependencies=data.get("dependencies", []),
            estimated_duration=data.get("estimated_duration", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class Plan:
    id: str
    title: str
    goal: str
    status: PlanStatus = PlanStatus.DRAFT
    priority: PlanPriority = PlanPriority.NORMAL
    steps: list[PlanStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "goal": self.goal,
            "status": self.status.value,
            "priority": self.priority.value,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        return cls(
            id=data["id"],
            title=data["title"],
            goal=data["goal"],
            status=PlanStatus(data.get("status", "DRAFT")),
            priority=PlanPriority(data.get("priority", "NORMAL")),
            steps=[PlanStep.from_dict(s) for s in data.get("steps", [])],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    def step_count(self) -> int:
        return len(self.steps)

    def is_ready(self) -> bool:
        return all(s.title.strip() for s in self.steps) if self.steps else False


__all__ = ["Plan", "PlanPriority", "PlanStatus", "PlanStep"]