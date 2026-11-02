"""
runtime/health.py - Runtime component health tracking.

Health records are JSON-safe and deliberately generic so existing DREX modules
can be wrapped without implementing new interfaces immediately.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ComponentHealth:
    """Health information for one runtime component."""

    name: str
    status: str = "registered"
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float | None = None
    startup_success: bool | None = None
    shutdown_success: bool | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def heartbeat(self) -> None:
        self.last_heartbeat = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "startup_success": self.startup_success,
            "shutdown_success": self.shutdown_success,
            "last_error": self.last_error,
            "metadata": dict(self.metadata),
        }


class HealthRegistry:
    """Thread-safe registry of component health records."""

    def __init__(self):
        self._lock = threading.RLock()
        self._components: dict[str, ComponentHealth] = {}
        logger.debug("HealthRegistry initialized")

    def register(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            if name not in self._components:
                self._components[name] = ComponentHealth(
                    name=name,
                    metadata=metadata or {},
                )
            elif metadata:
                self._components[name].metadata.update(metadata)

    def update(
        self,
        name: str,
        status: str | None = None,
        startup_success: bool | None = None,
        shutdown_success: bool | None = None,
        last_error: str | None = None,
        metadata: dict[str, Any] | None = None,
        heartbeat: bool = True,
    ) -> None:
        with self._lock:
            if name not in self._components:
                self._components[name] = ComponentHealth(name=name)
            record = self._components[name]
            if status is not None:
                record.status = status
            if startup_success is not None:
                record.startup_success = startup_success
            if shutdown_success is not None:
                record.shutdown_success = shutdown_success
            if last_error is not None:
                record.last_error = last_error
            if metadata:
                record.metadata.update(metadata)
            if heartbeat:
                record.heartbeat()

    def heartbeat(self, name: str) -> None:
        self.update(name, heartbeat=True)

    def get_component(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._components.get(name)
            return record.to_dict() if record else None

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            components = {
                name: record.to_dict()
                for name, record in self._components.items()
            }
        return {
            "component_count": len(components),
            "components": components,
        }


__all__ = ["ComponentHealth", "HealthRegistry"]
