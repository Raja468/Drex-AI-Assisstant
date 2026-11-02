"""
runtime/capability_registry.py - Runtime capability tracking for DREX.

The CapabilityRegistry maintains a central inventory of available system
capabilities at runtime. Components register themselves (e.g. voice, ocr,
vision, browser, automation, tray, hotkeys, providers) along with their
health status and metadata.

This is *not* a plugin loader — it is purely a registry for querying what
is available and its current health. Actual initialization is owned by the
Orchestrator or RuntimeSupervisor.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class Capability:
    """Descriptor for a single runtime capability."""

    name: str
    available: bool = True
    healthy: bool = True
    version: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_checked: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "healthy": self.healthy,
            "version": self.version,
            "description": self.description,
            "metadata": dict(self.metadata),
            "registered_at": self.registered_at,
            "last_checked": self.last_checked,
        }


class CapabilityRegistry:
    """
    Thread-safe registry for querying runtime capabilities.

    Usage::

        registry = CapabilityRegistry()
        registry.register("voice", available=True, version="1.0")
        registry.register("automation", available=True)

        if registry.has("voice"):
            ...

        all_caps = registry.list_capabilities()
        diagnostics = registry.diagnostics()
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._capabilities: dict[str, Capability] = {}
        logger.debug("CapabilityRegistry initialized")

    # ── Registration ────────────────────────────────────────

    def register(
        self,
        name: str,
        available: bool = True,
        healthy: bool = True,
        version: str = "",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register or update a capability."""
        if not name or not name.strip():
            raise ValueError("capability name is required")

        with self._lock:
            if name in self._capabilities:
                existing = self._capabilities[name]
                existing.available = available
                existing.healthy = healthy
                if version:
                    existing.version = version
                if description:
                    existing.description = description
                if metadata:
                    existing.metadata.update(metadata)
                existing.last_checked = time.time()
                logger.debug("Capability updated | name={} | available={}", name, available)
            else:
                self._capabilities[name] = Capability(
                    name=name.strip(),
                    available=available,
                    healthy=healthy,
                    version=version,
                    description=description,
                    metadata=metadata or {},
                )
                logger.info("Capability registered | name={} | available={}", name, available)

    def remove(self, name: str) -> bool:
        """Remove a capability from the registry. Returns True if removed."""
        with self._lock:
            if name in self._capabilities:
                del self._capabilities[name]
                logger.info("Capability removed | name={}", name)
                return True
            return False

    # ── Queries ─────────────────────────────────────────────

    def has(self, name: str) -> bool:
        """Check if a capability is registered and available."""
        with self._lock:
            cap = self._capabilities.get(name)
            return cap is not None and cap.available

    def is_healthy(self, name: str) -> bool:
        """Check if a capability is healthy (implies available)."""
        with self._lock:
            cap = self._capabilities.get(name)
            return cap is not None and cap.available and cap.healthy

    def get(self, name: str) -> dict[str, Any] | None:
        """Get capability details as a dict, or None if not found."""
        with self._lock:
            cap = self._capabilities.get(name)
            return cap.to_dict() if cap else None

    def list_capabilities(
        self,
        only_available: bool = False,
        only_unhealthy: bool = False,
    ) -> list[dict[str, Any]]:
        """
        List all registered capabilities.

        Args:
            only_available: If True, only return available capabilities.
            only_unhealthy: If True, only return unhealthy capabilities.

        Returns:
            List of capability dicts.
        """
        with self._lock:
            caps = list(self._capabilities.values())

        result = []
        for cap in caps:
            if only_available and not cap.available:
                continue
            if only_unhealthy and cap.healthy:
                continue
            result.append(cap.to_dict())
        return result

    def count(self, only_available: bool = False) -> int:
        """Return the number of registered capabilities."""
        with self._lock:
            if only_available:
                return sum(1 for c in self._capabilities.values() if c.available)
            return len(self._capabilities)

    # ── Health / diagnostics ────────────────────────────────

    def mark_healthy(self, name: str) -> None:
        """Mark a capability as healthy."""
        with self._lock:
            cap = self._capabilities.get(name)
            if cap:
                cap.healthy = True
                cap.available = True
                cap.last_checked = time.time()

    def mark_unhealthy(self, name: str, reason: str = "") -> None:
        """Mark a capability as unhealthy (but still registered)."""
        with self._lock:
            cap = self._capabilities.get(name)
            if cap:
                cap.healthy = False
                cap.last_checked = time.time()
                if reason:
                    cap.metadata["unhealthy_reason"] = reason
                logger.warning("Capability unhealthy | name={} | reason={}", name, reason)

    def mark_unavailable(self, name: str, reason: str = "") -> None:
        """Mark a capability as fully unavailable."""
        with self._lock:
            cap = self._capabilities.get(name)
            if cap:
                cap.available = False
                cap.healthy = False
                cap.last_checked = time.time()
                if reason:
                    cap.metadata["unavailable_reason"] = reason
                logger.warning("Capability unavailable | name={} | reason={}", name, reason)

    def diagnostics(self) -> dict[str, Any]:
        """
        Full diagnostics snapshot for the runtime dashboard or CLI.

        Returns:
            Dict with summary and per-capability details.
        """
        with self._lock:
            all_caps = [c.to_dict() for c in self._capabilities.values()]

        available = [c for c in all_caps if c["available"]]
        unhealthy = [c for c in all_caps if not c["healthy"]]
        unavailable = [c for c in all_caps if not c["available"]]

        return {
            "total": len(all_caps),
            "available": len(available),
            "unhealthy": len(unhealthy),
            "unavailable": len(unavailable),
            "capabilities": all_caps,
        }

    # ── Bulk registration helpers ───────────────────────────

    def register_many(
        self,
        capabilities: dict[str, dict[str, Any]],
    ) -> None:
        """
        Register multiple capabilities at once.

        Args:
            capabilities: Dict mapping name -> kwargs for register().
        """
        for name, kwargs in capabilities.items():
            self.register(name, **kwargs)

    def get_status(self) -> dict[str, Any]:
        """Return a JSON-safe status dictionary (alias for diagnostics)."""
        return self.diagnostics()


# ── Predefined capability names for consistency ──────────────
CAPABILITY_VOICE = "voice"
CAPABILITY_OCR = "ocr"
CAPABILITY_VISION = "vision"
CAPABILITY_BROWSER = "browser"
CAPABILITY_AUTOMATION = "automation"
CAPABILITY_TRAY = "tray"
CAPABILITY_HOTKEYS = "hotkeys"
CAPABILITY_PROVIDERS = "providers"
CAPABILITY_SCREENSHOT = "screenshot"
CAPABILITY_CLIPBOARD = "clipboard"
CAPABILITY_FILE_MANAGER = "file_manager"
CAPABILITY_SYSTEM_CONTROL = "system_control"
CAPABILITY_PLUGINS = "plugins"
CAPABILITY_MEMORY = "memory"
CAPABILITY_WAKE_WORD = "wake_word"

CORE_CAPABILITIES: dict[str, dict[str, Any]] = {
    CAPABILITY_VOICE: {"description": "Speech-to-text and text-to-speech"},
    CAPABILITY_OCR: {"description": "Optical character recognition from screen"},
    CAPABILITY_VISION: {"description": "Screen awareness and vision analysis"},
    CAPABILITY_BROWSER: {"description": "Browser automation and control"},
    CAPABILITY_AUTOMATION: {"description": "Desktop automation (apps, files, system)"},
    CAPABILITY_TRAY: {"description": "System tray integration"},
    CAPABILITY_HOTKEYS: {"description": "Global hotkey bindings"},
    CAPABILITY_PROVIDERS: {"description": "AI provider connectivity"},
    CAPABILITY_SCREENSHOT: {"description": "Screen capture functionality"},
    CAPABILITY_CLIPBOARD: {"description": "Clipboard read/write"},
    CAPABILITY_FILE_MANAGER: {"description": "File system operations"},
    CAPABILITY_SYSTEM_CONTROL: {"description": "System control (shutdown, volume, etc.)"},
    CAPABILITY_PLUGINS: {"description": "Plugin system"},
    CAPABILITY_MEMORY: {"description": "Conversation and fact memory"},
    CAPABILITY_WAKE_WORD: {"description": "Wake word detection"},
}


__all__ = [
    "CAPABILITY_AUTOMATION",
    "CAPABILITY_BROWSER",
    "CAPABILITY_CLIPBOARD",
    "CAPABILITY_FILE_MANAGER",
    "CAPABILITY_HOTKEYS",
    "CAPABILITY_MEMORY",
    "CAPABILITY_OCR",
    "CAPABILITY_PLUGINS",
    "CAPABILITY_PROVIDERS",
    "CAPABILITY_SCREENSHOT",
    "CAPABILITY_SYSTEM_CONTROL",
    "CAPABILITY_TRAY",
    "CAPABILITY_VISION",
    "CAPABILITY_VOICE",
    "CAPABILITY_WAKE_WORD",
    "CORE_CAPABILITIES",
    "Capability",
    "CapabilityRegistry",
]