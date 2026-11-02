"""
runtime/runtime_supervisor.py - DREX runtime lifecycle supervisor.

The supervisor owns runtime startup/shutdown sequencing and component health.
It wraps existing systems by duck-typing common lifecycle methods (`start`,
`stop`, `shutdown`) instead of requiring rewrites.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from runtime.event_bus import EventBus
from runtime.events import SystemStarted, SystemStopped
from runtime.health import HealthRegistry


@dataclass
class RuntimeComponent:
    """Registered runtime component."""

    name: str
    instance: Any
    autostart: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class RuntimeSupervisor:
    """
    Thread-safe lifecycle owner for DREX runtime components.

    Components can be any object. On start, the supervisor calls `start()` when
    present. On stop, it calls `stop()` if present, otherwise `shutdown()` if
    present. Components without lifecycle methods are still tracked for health.
    """

    def __init__(self, event_bus: EventBus | None = None):
        self.event_bus = event_bus or EventBus()
        self.health = HealthRegistry()
        self._lock = threading.RLock()
        self._components: dict[str, RuntimeComponent] = {}
        self._running = False
        self._started_at: float | None = None
        self._stopped_at: float | None = None

        self.register_component(
            "event_bus",
            self.event_bus,
            autostart=False,
            metadata={"role": "runtime_events"},
        )
        logger.info("RuntimeSupervisor initialized")

    def register_component(
        self,
        name: str,
        component: Any,
        autostart: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register a component for lifecycle and health tracking."""
        if not name:
            raise ValueError("component name is required")
        if component is None:
            raise ValueError("component instance is required")

        with self._lock:
            if name in self._components:
                raise ValueError(f"component already registered: {name}")

            component_record = RuntimeComponent(
                name=name,
                instance=component,
                autostart=autostart,
                metadata=metadata or {},
            )
            self._components[name] = component_record
            self.health.register(name, metadata=component_record.metadata)

        logger.info("Component registered | name={} | autostart={}", name, autostart)

    def start(self) -> None:
        """Start the runtime and autostart components in registration order."""
        with self._lock:
            if self._running:
                logger.debug("Runtime already running")
                return
            components = list(self._components.values())
            self._running = True
            self._started_at = time.time()
            self._stopped_at = None

        logger.info("Runtime starting")

        for component in components:
            if not component.autostart:
                self.health.update(component.name, status="ready")
                continue
            self._start_component(component)

        self.event_bus.publish(SystemStarted(payload={"component_count": len(components)}))
        logger.info("Runtime started")

    def stop(self) -> None:
        """Stop runtime components in reverse registration order."""
        with self._lock:
            if not self._running:
                logger.debug("Runtime already stopped")
                return
            components = list(reversed(list(self._components.values())))
            self._running = False
            self._stopped_at = time.time()

        logger.info("Runtime stopping")

        for component in components:
            if component.name == "event_bus":
                self.health.update(component.name, status="stopped", shutdown_success=True)
                continue
            self._stop_component(component)

        self.event_bus.publish(SystemStopped(payload={"component_count": len(components)}))
        logger.info("Runtime stopped")

    def restart(self) -> None:
        """Restart the runtime safely."""
        logger.info("Runtime restarting")
        self.stop()
        self.start()

    def get_status(self) -> dict[str, Any]:
        """Return JSON-safe runtime status."""
        with self._lock:
            component_names = list(self._components.keys())
            running = self._running
            started_at = self._started_at
            stopped_at = self._stopped_at

        return {
            "running": running,
            "started_at": started_at,
            "stopped_at": stopped_at,
            "components": component_names,
            "health": self.health.get_status(),
            "event_bus": self.event_bus.get_status(),
        }

    def _start_component(self, component: RuntimeComponent) -> None:
        logger.info("Component starting | name={}", component.name)
        try:
            start = getattr(component.instance, "start", None)
            if callable(start):
                start()
            self.health.update(
                component.name,
                status="running",
                startup_success=True,
                last_error="",
            )
            logger.info("Component started | name={}", component.name)
        except Exception as exc:
            self.health.update(
                component.name,
                status="error",
                startup_success=False,
                last_error=str(exc),
            )
            logger.exception("Component start failed | name={} | error={}", component.name, exc)

    def _stop_component(self, component: RuntimeComponent) -> None:
        logger.info("Component stopping | name={}", component.name)
        try:
            stop = getattr(component.instance, "stop", None)
            shutdown = getattr(component.instance, "shutdown", None)
            if callable(stop):
                stop()
            elif callable(shutdown):
                shutdown()
            self.health.update(
                component.name,
                status="stopped",
                shutdown_success=True,
                last_error="",
            )
            logger.info("Component stopped | name={}", component.name)
        except Exception as exc:
            self.health.update(
                component.name,
                status="error",
                shutdown_success=False,
                last_error=str(exc),
            )
            logger.exception("Component stop failed | name={} | error={}", component.name, exc)


__all__ = ["RuntimeSupervisor", "RuntimeComponent"]
