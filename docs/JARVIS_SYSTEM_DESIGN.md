# DREX Jarvis System Design

## Design Goal

Transform DREX from a chatbot with desktop tools into an AI operating assistant.

The product should run as a background-first, voice-first, context-aware runtime that can:

- Listen naturally.
- Respond in realtime.
- Observe the desktop.
- Understand active work context.
- Execute multi-step tasks.
- Verify outcomes.
- Ask for permission only when needed.
- Fall back gracefully when capabilities are unavailable.

## Target Architecture

```text
                     +------------------------------+
                     |         User Interface        |
                     | Orb / HUD / Tray / Chat Mode |
                     +---------------+--------------+
                                     |
                                     v
+------------------+      +---------+----------+      +-------------------+
| Realtime Layer   | ---> | Runtime Event Bus  | <--- | Awareness Layer   |
| Wake/VAD/STT/TTS |      | Typed system events|      | Screen/App/Tasks  |
+------------------+      +---------+----------+      +-------------------+
                                     |
                                     v
                     +---------------+---------------+
                     |          Core Layer            |
                     | Orchestrator / Planner / Memory|
                     +---------------+---------------+
                                     |
                                     v
                     +---------------+---------------+
                     |        Execution Layer         |
                     | Apps / Files / Browser / Dev   |
                     +-------------------------------+
```

## Core Layer

### 1. AI Orchestrator

Current equivalent:

- `core/orchestrator.py`
- `brain/ai_router.py`
- `brain/prompt_builder.py`
- `core/intent_parser.py`
- `core/fast_router.py`

Target responsibility:

- Own high-level intent resolution.
- Decide whether a request is conversational, command-like, task-like, visual, or project-related.
- Select fast path, local path, remote model path, or planner path.
- Emit structured events instead of directly managing all side effects.
- Coordinate with the planner and execution engines.

Required redesign:

- Split `Orchestrator.process()` into smaller services:
  - `IntentService`
  - `ResponseService`
  - `ToolRouter`
  - `ConversationService`
  - `ScreenQuestionService`
  - `TaskPlanningService`
- Keep `AIRouter` but add tool-aware request types.
- Introduce a `CapabilityRegistry` so runtime knows what is actually available.
- Introduce structured response envelopes:

```text
AssistantResult
- status: success | blocked | failed | needs_permission | partial
- user_message: str
- speech_message: str
- events: list
- tool_results: list
- next_actions: list
```

### 2. Memory Engine

Current equivalent:

- `memory/db_manager.py`
- `memory/context_builder.py`
- `memory/conversation_store.py`
- `memory/user_preferences.py`
- `brain/prompt_builder.py`

Target responsibility:

- Store conversation memory.
- Store user preferences and identity.
- Store durable task state.
- Store project context.
- Store semantic facts.
- Store recent awareness snapshots.
- Store action audit history.

Required data domains:

- `conversation_messages`
- `user_facts`
- `preferences`
- `tasks`
- `task_steps`
- `tool_events`
- `awareness_snapshots`
- `projects`
- `project_files`
- `permissions`

Required upgrade:

- Add semantic memory through embeddings or local vector index.
- Add fact extraction beyond names.
- Add time decay and confidence.
- Add source attribution for facts.
- Add task memory so DREX can resume interrupted work.

### 3. Voice Engine

Current equivalent:

- `voice/listener.py`
- `voice/speaker.py`
- `voice/wake_word.py`
- `voice/vad.py`
- `voice/interruption_handler.py`
- `core/voice_agent.py`

Target responsibility:

- Always-on wake word and push-to-talk.
- VAD-based speech boundaries.
- Streaming STT.
- Streaming TTS.
- Barge-in interruption.
- Echo cancellation.
- Voice state events for UI and planner.

Required redesign:

- Make `VoiceEngine` a first-class runtime component, not a lazy dependency inside `Orchestrator`.
- Use a session model:

```text
VoiceSession
- state: idle | wake_detected | listening | transcribing | thinking | speaking | interrupted
- transcript_partial
- transcript_final
- started_at
- last_audio_at
- cancellation_token
```

- Emit events:
  - `wake.detected`
  - `speech.started`
  - `speech.partial`
  - `speech.final`
  - `speech.interrupted`
  - `tts.started`
  - `tts.chunk_spoken`
  - `tts.ended`

### 4. Automation Engine

Current equivalent:

- `automation/task_handler.py`
- `automation/app_launcher.py`
- `automation/browser_control.py`
- `automation/system_control.py`
- `automation/file_manager.py`

Target responsibility:

- Execute safe, structured desktop actions.
- Return structured results.
- Verify effects.
- Integrate with permission policy.
- Support app-specific adapters.

Required redesign:

- Replace string-only tool returns with structured `ToolResult`.
- Add execution primitives:
  - launch app
  - focus app
  - close app
  - click
  - type
  - hotkey
  - wait for window
  - wait for UI element
  - screenshot
  - OCR region
  - verify condition

Required app adapters:

- Browser adapter
- VS Code adapter
- File Explorer adapter
- Terminal adapter
- PDF/document adapter
- Generic GUI adapter

### 5. Vision Engine

Current equivalent:

- `assistant/screen_capture.py`
- `assistant/vision_analyzer.py`
- OCR/document utilities

Target responsibility:

- Capture screen and regions.
- Detect active UI elements.
- Extract visible text.
- Compare before/after screenshots.
- Support action verification.
- Feed relevant visual context into the awareness bus.

Required redesign:

- Add continuous but throttled screen monitoring.
- Add image diffing.
- Add OCR cache.
- Add UI element extraction format:

```text
UIElement
- type
- label
- bounds
- confidence
- source: ocr | vision | accessibility | browser_dom
```

### 6. Desktop Control Engine

Target responsibility:

- Own OS-level control.
- Maintain active window state.
- Provide safe low-level input.
- Enforce permissions and user trust boundaries.

Required components:

- Window manager
- Process manager
- Input controller
- Clipboard controller
- Notification controller
- Permission controller
- Audit logger

The desktop control engine should expose a small action API and hide platform-specific details from planners.

## Realtime Layer

### Wake Word

Use `voice/wake_word.py` as the starting point.

Target:

- Runs continuously in background.
- Emits event rather than directly invoking the orchestrator.
- Has cooldown, mute state, and privacy controls.

### VAD

Use `voice/vad.py` and `assistant/silence_detector.py` as starting points.

Target:

- Detect speech start and stop with low latency.
- Drive UI state immediately.
- Avoid sending silence to STT.
- Support interruption during TTS.

### Interruptions

Use both current interruption handlers as source material:

- `voice/interruption_handler.py`
- `assistant/interruption_handler.py`

Target:

- Cancel TTS immediately.
- Cancel or reprioritize in-flight generation.
- Preserve partial context.
- Transition to listening within hundreds of milliseconds.

### Streaming Speech

Current `Speaker.speak_stream()` is sentence-level. Target should be lower-latency:

- Stream LLM tokens.
- Segment speech intelligently.
- Begin speaking after first complete phrase.
- Allow interruption at any time.
- Track currently spoken text for recovery.

### Background Execution

Add a runtime supervisor:

```text
RuntimeSupervisor
- starts/stops engines
- owns event bus
- monitors health
- restarts failed workers
- handles shutdown
- manages background jobs
```

## Awareness Layer

### Screen Monitoring

Target:

- Periodically capture screen thumbnails.
- Detect meaningful changes.
- OCR changed regions.
- Update awareness cache.
- Respect privacy and battery settings.

### Active Window Awareness

Use `assistant/app_awareness.py`.

Add:

- Process ID mapping.
- App type classification.
- Focus history.
- Window bounds.
- Foreground enforcement.

### Browser Awareness

Current browser control opens URLs. Target browser awareness needs:

- Browser extension or Chrome DevTools Protocol.
- Active tab URL and title.
- DOM extraction.
- Form field detection.
- Download state.
- Page text summarization.
- Safe browser actions.

### Project Awareness

Add a `ProjectAwarenessEngine`:

- Detect active repo/project root.
- Read git status.
- Track open editor files.
- Watch file changes.
- Track test commands and outputs.
- Track running dev servers.
- Summarize project structure.

### Task Awareness

Add a `TaskStateEngine`:

- Current goal.
- Plan steps.
- Completed steps.
- Pending approvals.
- Last tool result.
- Confidence.
- Blockers.
- Next action.

## Execution Layer

### Open Applications

Current support exists in `automation/app_launcher.py`.

Upgrade:

- Verify app opened.
- Focus the window.
- Return process/window metadata.
- Support app aliases and installed app discovery.

### Use Applications

Add app adapters:

```text
AppAdapter
- can_handle(window/app/process)
- observe()
- actions()
- execute(action)
- verify(action, result)
```

Generic GUI fallback:

- Screenshot.
- Detect UI element.
- Move/click/type.
- Verify.

### File Management

Current support exists in `automation/file_manager.py`.

Upgrade:

- Create, move, rename, delete, copy, compress files.
- Preview file contents.
- Ask permission for destructive actions.
- Track changes.
- Support workspace-scoped operations.

### Browser Automation

Target:

- Open/search remains fast.
- Add controlled browser sessions.
- Use DOM when possible.
- Use vision fallback when DOM unavailable.
- Support forms, clicks, downloads, tab management, and page summarization.

### Development Workflow Automation

Add `DevWorkflowEngine`:

- Detect project language.
- Install dependencies with approval.
- Run tests.
- Parse failures.
- Edit files through controlled patches.
- Run linters.
- Start dev servers.
- Inspect logs.
- Summarize progress.

## New Composition Root

`main.py` should eventually start:

```text
RuntimeSupervisor
- StateEngine
- EventBus
- CapabilityRegistry
- MemoryEngine
- AIOrchestrator
- VoiceEngine
- AwarenessEngine
- AutomationEngine
- DesktopControlEngine
- TaskEngine
- UIRuntime
```

Chat mode should become one UI surface attached to the runtime, not the runtime itself.

## Migration Strategy

1. Introduce event bus and runtime supervisor without removing existing GUI.
2. Wrap current orchestrator as a service.
3. Move voice lifecycle out of `Orchestrator` into `VoiceEngine`.
4. Move automation into structured tool interface.
5. Add task engine and durable task state.
6. Promote orb/HUD/tray runtime to default.
7. Keep chat as secondary long-form mode.

