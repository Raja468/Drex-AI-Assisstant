# DREX Runtime Architecture

> Phase 1 — Runtime Foundation for the Jarvis-style AI Operating Assistant

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     RuntimeSupervisor                           │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  EventBus    │  │Capability    │  │  HealthRegistry      │   │
│  │              │  │Registry      │  │                      │   │
│  │ publish()   │  │ register()   │  │  register()          │   │
│  │ subscribe() │  │ has()        │  │  update()            │   │
│  │ unsubscribe │  │ diagnostics()│  │  heartbeat()         │   │
│  └─────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Registered Components                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │Orchestr. │ │Voice     │ │Automation│ │GUI       │  │   │
│  │  │(core)    │ │(voice)   │ │(autom.)  │ │(gui)     │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Existing DREX Systems                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │  Brain   │ │  Memory  │ │ Voice    │ │  GUI             │   │
│  │ (AI)     │ │ (DB)     │ │ (TTS/STT)│ │ (customtkinter)  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │Automation│ │ Assistant│ │ Plugins  │                        │
│  └──────────┘ └──────────┘ └──────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### RuntimeSupervisor (`runtime/runtime_supervisor.py`)

The top-level lifecycle owner. Responsibilities:

- **Startup sequencing** — Starts registered components in order, respecting `autostart` flag
- **Shutdown sequencing** — Stops components in reverse registration order
- **Component registration** — Track any object by name for lifecycle and health
- **Health checks** — Delegates per-component health to `HealthRegistry`
- **Runtime status** — Returns a JSON-safe snapshot of all components, health, and event bus state

Key design decisions:
- Thread-safe with `threading.RLock`
- Duck-types lifecycle methods (`start()`, `stop()`, `shutdown()`) — no interface required
- Publishes `SystemStarted` / `SystemStopped` events on lifecycle transitions

### EventBus (`runtime/event_bus.py`)

Lightweight publish/subscribe event infrastructure. Responsibilities:

- **subscribe(event_type, handler)** — Register a callable for an event type
- **unsubscribe(event_type, handler)** — Remove a registered handler
- **publish(event)** — Deliver an event to matching subscribers
- **Wildcard support** — Subscribe to `"*"` to receive all events
- **Thread safety** — All operations protected by `threading.RLock`
- **Logging** — All subscribe/unsubscribe/publish operations logged via `loguru`

Key design decisions:
- Synchronous delivery (subscribers run on publisher's thread)
- Fault isolation — handler exceptions are caught and logged, never propagated
- No async queues — async can be layered on top without changing event definitions

### Event Types (`runtime/events.py`)

Typed, JSON-safe event dataclasses for the runtime:

| Event | Type String | Source |
|-------|------------|--------|
| `SystemStarted` | `system.started` | `runtime` |
| `SystemStopped` | `system.stopped` | `runtime` |
| `VoiceListeningStarted` | `voice.listening.started` | runtime |
| `VoiceListeningStopped` | `voice.listening.stopped` | runtime |
| `WakeWordDetected` | `voice.wake_word.detected` | runtime |
| `TranscriptReceived` | `voice.transcript.received` | runtime |
| `ResponseStarted` | `response.started` | runtime |
| `ResponseCompleted` | `response.completed` | runtime |
| `ToolExecutionStarted` | `tool.execution.started` | runtime |
| `ToolExecutionFinished` | `tool.execution.finished` | runtime |
| `ProviderSelected` | `provider.selected` | runtime |
| `TaskStarted` | `task.started` | runtime |
| `TaskFinished` | `task.finished` | runtime |
| `PermissionRequested` | `permission.requested` | runtime |

### CapabilityRegistry (`runtime/capability_registry.py`)

Central inventory of available runtime capabilities. Responsibilities:

- **register(name, available, healthy, ...)** — Add or update a capability
- **remove(name)** — Remove a capability
- **has(name)** — Query if a capability is registered and available
- **is_healthy(name)** — Query if a capability is healthy
- **diagnostics()** — Full diagnostics snapshot with counts
- **Basic lifecycle** — `mark_healthy()`, `mark_unhealthy()`, `mark_unavailable()`

Predefined capabilities:

| Name | Description |
|------|-------------|
| `voice` | Speech-to-text and text-to-speech |
| `ocr` | Optical character recognition from screen |
| `vision` | Screen awareness and vision analysis |
| `browser` | Browser automation and control |
| `automation` | Desktop automation (apps, files, system) |
| `tray` | System tray integration |
| `hotkeys` | Global hotkey bindings |
| `providers` | AI provider connectivity |
| `screenshot` | Screen capture functionality |
| `clipboard` | Clipboard read/write |
| `file_manager` | File system operations |
| `system_control` | System control (shutdown, volume, etc.) |
| `plugins` | Plugin system |
| `memory` | Conversation and fact memory |
| `wake_word` | Wake word detection |

### HealthRegistry (`runtime/health.py`)

Per-component health tracking. Responsibilities:

- **register(name, metadata)** — Create a health record
- **update(name, status, ...)** — Update health fields
- **heartbeat(name)** — Update last heartbeat timestamp
- **get_status()** — Full health snapshot

## Startup Sequence

```
main.py entry point
    │
    ├─ 1. Parse args, load .env, validate config
    │
    ├─ 2. Create Orchestrator (existing flow)
    │     • DBManager, PromptBuilder, AIRouter, IntentParser, etc.
    │     • Voice/lazy modules remain unchanged
    │
    ├─ 3. Initialize RuntimeSupervisor (NEW — additive)
    │     • create_runtime(orch):
    │         ├─ Instantiate RuntimeSupervisor + EventBus
    │         ├─ Register orchestrator as a component (autostart=false)
    │         ├─ Create CapabilityRegistry with CORE_CAPABILITIES
    │         ├─ Register capability_registry as a component
    │         └─ Return supervisor
    │     • supervisor.start():
    │         ├─ Publish SystemStarted event
    │         └─ Start autostart components (if any)
    │
    └─ 4. Enter GUI loop or text loop
```

## Shutdown Sequence

```
GUI window closed / text loop exited
    │
    ├─ 1. Orchestrator.shutdown() (existing)
    │     • Stop voice loops
    │     • End DB session, close DB
    │     • Shutdown speaker, listener, wake word
    │
    ├─ 2. RuntimeSupervisor.stop() (NEW — additive)
    │     • Stop components in reverse registration order
    │     • Publish SystemStopped event
    │
    └─ 3. Exit cleanly
```

## Future Integration Points

| Feature | Integration Point | Target Phase |
|---------|------------------|--------------|
| **Plugin System** | Register plugin instances as supervisor components | Phase 2 |
| **Async Event Queue** | Layer async dispatch on EventBus (e.g. `asyncio.Queue`) | Phase 2 |
| **Voice Engine** | Register VoiceEngine as a managed component with autostart | Phase 2 |
| **Tool System** | Register ToolRegistry as a component, subscribe to tool events | Phase 2 |
| **Planner** | Register Planner as a component with dependency ordering | Phase 3 |
| **Awareness System** | Register AwarenessEngine, subscribe to screen/context events | Phase 3 |
| **Hot Reload** | `supervisor.reload_component(name)` with health tracking | Future |
| **Metrics Export** | Push runtime status to Prometheus / file / GUI dashboard | Future |
| **Graceful Degradation** | Auto-disable unhealthy capabilities, notify via events | Future |

## Design Rationale

### Why synchronous EventBus?

The bus is intentionally synchronous. This keeps the foundation simple, testable, and easy to reason about. An async queue can be layered on when needed without changing event definitions or subscriber APIs.

### Why duck-typing for components?

Existing DREX modules (`Speaker`, `Listener`, `Automation`, etc.) already have `start()` and `shutdown()` methods. Requiring them to implement an interface would be a breaking change. Duck-typing lets us wrap them without modification.

### Why separate CapabilityRegistry from HealthRegistry?

Capabilities are about *what is available*. Health is about *how it's doing*. Keeping them separate avoids coupling availability state with runtime health, making both easier to reason about and test.

## File Listing

```
runtime/
├── __init__.py              — Package exports
├── capability_registry.py   — NEW: Runtime capability tracking
├── event_bus.py             — Thread-safe publish/subscribe
├── events.py                — Typed event definitions
├── health.py                — Component health tracking
└── runtime_supervisor.py    — Lifecycle supervisor

Modified files:
├── main.py                  — Added runtime initialization + shutdown
```

## Verification

After Phase 1, verify:

1. `python main.py --test` — All 14 diagnostics pass (unchanged)
2. `python -c "from runtime import RuntimeSupervisor, EventBus, CapabilityRegistry; print('OK')"` — All three core classes import
3. Application starts, runs, and exits without errors
4. Runtime lifecycle events appear in logs