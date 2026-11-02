"""
runtime/events.py - Typed runtime event definitions for DREX.

Events are intentionally lightweight and JSON-safe. They carry no behavior
beyond a type, timestamp, source, and payload so existing systems can publish
and consume them without tight coupling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping


Payload = Mapping[str, Any]


@dataclass(frozen=True)
class Event:
    """Base event structure used by the runtime event bus."""

    type: str
    timestamp: float = field(default_factory=time.time)
    source: str = "runtime"
    payload: Payload = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary representation."""
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "source": self.source,
            "payload": dict(self.payload),
        }


class RuntimeEvent(Event):
    """Convenience base class for named runtime events."""

    EVENT_TYPE = "runtime.event"

    def __init__(self, source: str = "runtime", payload: Payload | None = None):
        super().__init__(
            type=self.EVENT_TYPE,
            timestamp=time.time(),
            source=source,
            payload=payload or {},
        )


class SystemStarted(RuntimeEvent):
    EVENT_TYPE = "system.started"


class SystemStopped(RuntimeEvent):
    EVENT_TYPE = "system.stopped"


class VoiceListeningStarted(RuntimeEvent):
    EVENT_TYPE = "voice.listening.started"


class VoiceListeningStopped(RuntimeEvent):
    EVENT_TYPE = "voice.listening.stopped"


class WakeWordDetected(RuntimeEvent):
    EVENT_TYPE = "voice.wake_word.detected"


class TranscriptReceived(RuntimeEvent):
    EVENT_TYPE = "voice.transcript.received"


class ResponseStarted(RuntimeEvent):
    EVENT_TYPE = "response.started"


class ResponseCompleted(RuntimeEvent):
    EVENT_TYPE = "response.completed"


class ToolExecutionStarted(RuntimeEvent):
    EVENT_TYPE = "tool.execution.started"


class ToolExecutionFinished(RuntimeEvent):
    EVENT_TYPE = "tool.execution.finished"


class ProviderSelected(RuntimeEvent):
    EVENT_TYPE = "provider.selected"


class TaskStarted(RuntimeEvent):
    EVENT_TYPE = "task.started"


class TaskFinished(RuntimeEvent):
    EVENT_TYPE = "task.finished"


class PermissionRequested(RuntimeEvent):
    EVENT_TYPE = "permission.requested"


# ── Voice engine events (Phase 2) ──────────────────────────────

class VoiceStarted(RuntimeEvent):
    EVENT_TYPE = "voice.started"


class VoiceStopped(RuntimeEvent):
    EVENT_TYPE = "voice.stopped"


class ListeningStarted(RuntimeEvent):
    EVENT_TYPE = "voice.listening_started"


class ListeningStopped(RuntimeEvent):
    EVENT_TYPE = "voice.listening_stopped"


class SpeechStarted(RuntimeEvent):
    EVENT_TYPE = "voice.speech_started"


class SpeechFinished(RuntimeEvent):
    EVENT_TYPE = "voice.speech_finished"


class VoiceInterrupted(RuntimeEvent):
    EVENT_TYPE = "voice.interrupted"


class VoiceError(RuntimeEvent):
    EVENT_TYPE = "voice.error"


class VoiceStateChanged(RuntimeEvent):
    EVENT_TYPE = "voice.state_changed"


CORE_EVENT_TYPES = {
    "SystemStarted": SystemStarted.EVENT_TYPE,
    "SystemStopped": SystemStopped.EVENT_TYPE,
    "VoiceListeningStarted": VoiceListeningStarted.EVENT_TYPE,
    "VoiceListeningStopped": VoiceListeningStopped.EVENT_TYPE,
    "WakeWordDetected": WakeWordDetected.EVENT_TYPE,
    "TranscriptReceived": TranscriptReceived.EVENT_TYPE,
    "ResponseStarted": ResponseStarted.EVENT_TYPE,
    "ResponseCompleted": ResponseCompleted.EVENT_TYPE,
    "ToolExecutionStarted": ToolExecutionStarted.EVENT_TYPE,
    "ToolExecutionFinished": ToolExecutionFinished.EVENT_TYPE,
    "ProviderSelected": ProviderSelected.EVENT_TYPE,
    "TaskStarted": TaskStarted.EVENT_TYPE,
    "TaskFinished": TaskFinished.EVENT_TYPE,
    "PermissionRequested": PermissionRequested.EVENT_TYPE,
    "VoiceStarted": VoiceStarted.EVENT_TYPE,
    "VoiceStopped": VoiceStopped.EVENT_TYPE,
    "ListeningStarted": ListeningStarted.EVENT_TYPE,
    "ListeningStopped": ListeningStopped.EVENT_TYPE,
    "SpeechStarted": SpeechStarted.EVENT_TYPE,
    "SpeechFinished": SpeechFinished.EVENT_TYPE,
    "VoiceInterrupted": VoiceInterrupted.EVENT_TYPE,
    "VoiceError": VoiceError.EVENT_TYPE,
    "VoiceStateChanged": VoiceStateChanged.EVENT_TYPE,
}


__all__ = [
    "CORE_EVENT_TYPES",
    "Event",
    "ListeningStarted",
    "ListeningStopped",
    "PermissionRequested",
    "ProviderSelected",
    "ResponseCompleted",
    "ResponseStarted",
    "RuntimeEvent",
    "SpeechFinished",
    "SpeechStarted",
    "SystemStarted",
    "SystemStopped",
    "TaskFinished",
    "TaskStarted",
    "ToolExecutionFinished",
    "ToolExecutionStarted",
    "TranscriptReceived",
    "VoiceError",
    "VoiceInterrupted",
    "VoiceListeningStarted",
    "VoiceListeningStopped",
    "VoiceStarted",
    "VoiceStateChanged",
    "VoiceStopped",
    "WakeWordDetected",
]
