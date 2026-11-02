# DREX Voice Runtime Architecture

> Phase 2 — Voice becomes a first-class runtime subsystem owned by RuntimeSupervisor

## Architecture Diagram

```
RuntimeSupervisor
    │
    ├── EventBus
    │       │
    │       └── VoiceEngine publishes:
    │           voice.started
    │           voice.stopped
    │           voice.listening_started
    │           voice.listening_stopped
    │           voice.speech_started
    │           voice.speech_finished
    │           voice.wake_word_detected
    │           voice.transcript
    │           voice.interrupted
    │           voice.state_changed
    │
    ├── CapabilityRegistry
    │       │
    │       └── voice capability (tracked)
    │
    └── VoiceEngine (managed component)
            │
            ├── Speaker (wrapped — pyttsx3 / edge-tts)
            ├── Listener (wrapped — speech_recognition)
            ├── WakeWordDetector (wrapped — pvporcupine / fallback)
            └── InterruptionHandler (wrapped — mic monitoring)
```

## Component Ownership

### Before Phase 2 (ad-hoc)

```
Orchestrator          GUI
    │                    │
    ├── speaker (lazy)   ├── start_voice_listening()
    ├── listener (lazy)  ├── stop_voice_listening()
    ├── wake_word (lazy) └── voice toggle button
    └── voice_state
```

Voice state, lifecycle, and health were spread across Orchestrator, VoiceAgent,
and GUI with no single source of truth.

### After Phase 2 (runtime-owned)

```
RuntimeSupervisor
    │
    └── VoiceEngine  ←── single owner of voice
            │
            ├── speaker, listener, wake_word, interruption
            ├── VoiceState (unified enum — IDLE/LISTENING/PROCESSING/SPEAKING/INTERRUPTED/ERROR)
            ├── health()
            ├── status()
            └── EventBus publishing

Orchestrator (backward-compatible delegation)
    │
    ├── speaker     → delegates to VoiceEngine.speaker  (if available)
    ├── listener    → delegates to VoiceEngine.listener (if available)
    ├── wake_word   → delegates to VoiceEngine.wake_word (if available)
    └── shutdown    → VoiceEngine handles speaker/listener/wake_word shutdown
```

## Startup Flow

```
main.py
    │
    ├── 1. Create Orchestrator (existing — unchanged)
    │
    ├── 2. initialize_runtime(orch):
    │       ├── Create RuntimeSupervisor
    │       ├── Register orchestrator (autostart=false)
    │       ├── Create VoiceEngine(event_bus=supervisor.event_bus)
    │       ├── Register VoiceEngine (autostart=true)
    │       ├── Wire orch._voice_engine = voice_engine
    │       ├── Create CapabilityRegistry with CORE_CAPABILITIES
    │       ├── Register capability_registry (autostart=false)
    │       └── supervisor.start()
    │
    ├── 3. RuntimeSupervisor.start():
    │       ├── Start VoiceEngine.start():
    │       │       ├── Probe speaker/listener/wake_word availability
    │       │       ├── Start InterruptionHandler monitoring
    │       │       ├── Set state → IDLE
    │       │       └── Publish voice.started event
    │       └── Publish SystemStarted event
    │
    └── 4. Enter GUI loop
```

## Shutdown Flow

```
GUI window closed
    │
    ├── 1. Orchestrator.shutdown():
    │       ├── stop_voice_loop() → Listener.stop_continuous(), WakeWord.stop()
    │       ├── DB end session
    │       └── (VoiceEngine handles speaker/listener/wake_word lifecycle)
    │
    ├── 2. RuntimeSupervisor.stop():
    │       ├── Stop VoiceEngine.stop():
    │       │       ├── Stop InterruptionHandler
    │       │       ├── Stop WakeWord
    │       │       ├── Stop Listener
    │       │       ├── Stop Speaker
    │       │       └── Publish voice.stopped event
    │       └── Publish SystemStopped event
    │
    └── 3. RuntimeSupervisor shutdown() → VoiceEngine.shutdown():
            ├── Speaker.shutdown()
            ├── Listener.shutdown()
            ├── WakeWord.shutdown()
            └── InterruptionHandler.shutdown()
```

## State Transitions

```
                    ┌──────────────────────────────┐
                    │            IDLE               │
                    └──────────┬───────────────────┘
                               │
                    start_listening()
                               │
                               ▼
                    ┌──────────────────────────────┐
                    │          LISTENING            │
                    └──────────┬───────────────────┘
                               │
                    on_transcript()
                               │
                               ▼
                    ┌──────────────────────────────┐
                    │         PROCESSING            │
                    └──────────┬───────────────────┘
                               │
                    speak() / on_response_complete()
                               │
                               ▼
                    ┌──────────────────────────────┐
                    │          SPEAKING             │
                    └──────────┬───────────────────┘
                               │
                    on_speech_finished()
                               │
                               ▼
                    ┌──────────────────────────────┐
                    │            IDLE               │
                    └──────────────────────────────┘

Error/Interrupt paths:

    SPEAKING ──interrupt()──→ INTERRUPTED ──→ LISTENING
    ANY STATE ──error──→ ERROR ──→ IDLE
```

## Event List

| Event Type | Source | Payload | Description |
|-----------|--------|---------|-------------|
| `voice.started` | `voice_engine` | `{}` | VoiceEngine started successfully |
| `voice.stopped` | `voice_engine` | `{}` | VoiceEngine stopped cleanly |
| `voice.listening_started` | `voice_engine` | `{}` | Listening mode activated |
| `voice.listening_stopped` | `voice_engine` | `{}` | Listening mode deactivated |
| `voice.speech_started` | `voice_engine` | `{text_length}` | TTS playback started |
| `voice.speech_finished` | `voice_engine` | `{}` | TTS playback completed |
| `voice.wake_word_detected` | `voice_engine` | `{}` | Wake word heard |
| `voice.transcript` | `voice_engine` | `{text}` | Speech transcribed |
| `voice.interrupted` | `voice_engine` | `{}` | Speech interrupted by user |
| `voice.error` | `voice_engine` | `{error}` | Voice subsystem error |
| `voice.state_changed` | `voice_engine` | `{from, to}` | State transition occurred |

## Health Diagnostics

VoiceEngine exposes `health()` which returns:

```json
{
    "microphone_available": true,
    "speaker_available": true,
    "wake_word_available": false,
    "state": "idle",
    "is_running": true,
    "is_speaking": false,
    "is_listening": false,
    "last_error": "",
    "errors_since_start": 0,
    "uptime_seconds": 42.5
}
```

## Backward Compatibility

All existing APIs continue to work:

| API | Before | After |
|-----|--------|-------|
| `orch.speaker` | Lazy-init `Speaker()` | Delegates to `VoiceEngine.speaker` |
| `orch.listener` | Lazy-init `Listener()` | Delegates to `VoiceEngine.listener` |
| `orch.wake_word` | Lazy-init `WakeWordDetector()` | Delegates to `VoiceEngine.wake_word` |
| `orch.start_voice_listening()` | Direct listener start | Delegates through VoiceEngine |
| `orch.stop_voice_listening()` | Direct listener stop | Delegates through VoiceEngine |
| `gui._start_voice()` | Calls `orch.start_voice_listening()` | Unchanged |
| `gui._stop_voice()` | Calls `orch.stop_voice_listening()` | Unchanged |
| `orch.shutdown()` | Direct speaker/listener shutdown | VoiceEngine owns lifecycle |

If VoiceEngine is NOT available (e.g. in tests), the Orchestrator falls back to
its original lazy-init behavior exactly as before.

## Files

```
Created:
  voice/voice_engine.py          — Runtime-owned voice subsystem

Modified:
  runtime/events.py              — Added VoiceStarted, VoiceStopped, ListeningStarted,
                                    ListeningStopped, SpeechStarted, SpeechFinished,
                                    VoiceInterrupted, VoiceError, VoiceStateChanged
  core/orchestrator.py           — Added _voice_engine delegation in speaker,
                                    listener, wake_word properties
  main.py                        — create_runtime() now creates VoiceEngine,
                                    registers it, and wires it to orchestrator

Unchanged (wrapped, not replaced):
  voice/speaker.py               — Dual-engine TTS
  voice/listener.py              — Resilient continuous listening
  voice/wake_word.py             — pvporcupine wake word
  voice/wake_word_simple.py      — Fallback wake word
  voice/interruption_handler.py  — Mic monitoring interrupt
  voice/vad.py                   — Voice activity detection
  voice/voice_agent.py           — Kept for reference (no longer primary)
  gui/app.py                     — All voice toggle buttons unchanged
  gui/jarvis_panel.py            — All voice toggle buttons unchanged
```

## Risks

1. **VoiceEngine wrapper introduces one extra property lookup** — Negligible overhead; all wrapped modules are lazy-created.
2. **InterruptionHandler still uses direct PyAudio** — No change; VoiceEngine wraps it without modification.
3. **Orchestrator._voice_engine is set via monkey-patch from main.py** — Clean pattern for runtime wiring; the orchestrator checks `_voice_engine is not None` before delegating.
4. **voice_agent.py is now secondary** — The `VoiceAgent` class in `core/voice_agent.py` was a first attempt at voice state management. It's kept for reference but `VoiceEngine` is now the canonical owner. No breaking change.

## Recommended Next Steps (Phase 3)

1. **Tool System** — Register `ToolRegistry` as a managed component
2. **Planner** — Register `Planner` as a managed component with dependency ordering
3. **Awareness System** — Register `AwarenessEngine`, subscribe to screen/context events
4. **Active health probes** — Poll VoiceEngine health and auto-mark capabilities unhealthy
5. **Async EventBus** — Layer async dispatch without changing event definitions