# DREX Jarvis Gap Analysis

## Executive Summary

DREX is approximately **45% architecturally aligned** with a Jarvis-style assistant.

That number is not a UI score. It reflects the amount of current architecture that can support a voice-first, realtime, context-aware desktop operating assistant without being replaced.

The repository contains real building blocks:

- Multi-provider AI routing and fallback in `brain/ai_router.py`
- Central request orchestration in `core/orchestrator.py`
- SQLite memory with thread-aware access in `memory/db_manager.py`
- Voice listener, speaker, wake word, VAD, and interruption modules in `voice/`
- Desktop automation for apps, browser launching, system controls, screenshots, clipboard, and files in `automation/`
- Screen capture, vision analysis, app awareness, floating orb, tray, hotkeys, and state engine in `assistant/`
- CustomTkinter desktop UI in `gui/`

The gap is that these pieces are still composed around a **chatbot request-response loop**. The dominant runtime is:

`main.py -> Orchestrator.process() -> intent parser / automation / AI -> GUI chat or TTS`

A Jarvis-style AI operating assistant needs a different center of gravity:

`Runtime daemon -> state engine -> realtime voice loop -> awareness bus -> planner -> tool execution -> verification -> multimodal feedback`

The current system has many modules that point in that direction, but they are not yet the primary runtime.

## 1. Architecture Support Percentage

Estimated support for a true Jarvis-style assistant: **45%**

| Area | Current Readiness | Notes |
| --- | ---: | --- |
| AI provider routing | 75% | Strong fallback model routing exists, but not tool-native or realtime-native. |
| Voice pipeline | 55% | Listener, speaker, wake word, VAD, and interruption exist, but realtime turn-taking is wrapped around synchronous processing. |
| Memory | 45% | SQLite conversation/facts/preferences exist, but no semantic memory, task memory, project memory, or long-horizon recall. |
| Automation | 40% | Can launch apps, open sites, control volume, manage files, and press keys; cannot reliably operate arbitrary apps toward goals. |
| Vision and awareness | 35% | Screen capture, vision analyzer, and app awareness exist, but mostly on-demand rather than continuous context. |
| Runtime/background operation | 35% | Tray/hotkey/floating orb modules exist, but `main.py` still starts the full GUI/orchestrator path. |
| Autonomous execution | 20% | No planner, action graph, verification loop, rollback strategy, or durable task queue. |
| UI model | 35% | Chat UI is mature; Jarvis/HUD/orb components exist but do not define the product interaction model. |

## 2. Chatbot-Oriented Parts

The current product still feels like a chatbot because the main workflow is built around text turns, message bubbles, and a single response.

Chatbot-oriented architecture:

- `gui/chat_panel.py` is still a primary interface surface with welcome prompts, chat bubbles, typing indicators, and message count.
- `gui/input_bar.py` keeps the bottom text-entry pattern central.
- `gui/app.py` wires callbacks around chat display, streaming labels, and user/assistant messages.
- `core/orchestrator.py` treats each user request as a single `process(user_input)` transaction.
- `brain/prompt_builder.py` builds prompts from recent chat history and user facts, not active task state.
- `memory/db_manager.py` stores conversations, preferences, facts, and sessions, but not projects, tasks, screen state, app state, or action history.
- `automation/task_handler.py` returns human-readable strings after one action instead of running multi-step plans with feedback.
- `main.py` launches `DrexApp`, not a background agent runtime.

Chatbot-oriented behavior:

- User asks.
- DREX parses once.
- DREX either runs a command or calls an LLM.
- DREX returns a text answer.
- Optional TTS speaks the answer.

Jarvis behavior should be:

- DREX is already running.
- DREX maintains awareness of microphone, screen, active app, project, tasks, and user intent.
- DREX decides whether it should listen, wait, ask, execute, or update silently.
- DREX performs actions in the OS, checks whether they worked, and continues until the task is complete or blocked.

## 3. What Prevents Realtime Operation

Primary blockers:

1. **Synchronous orchestrator core**
   - `Orchestrator.process()` does too much in one blocking path.
   - It combines deduplication, fast routing, intent parsing, memory writes, automation, AI calls, screen analysis, streaming, TTS, and callback delivery.
   - A realtime assistant needs an event-driven runtime where listening, thinking, speaking, screen monitoring, and task execution can happen concurrently.

2. **Voice is not the primary event source**
   - `Listener.start_continuous()` exists.
   - Wake word exists.
   - `VoiceAgent` exists.
   - But `main.py` does not boot a first-class voice agent runtime as the main product shell.

3. **VAD is present but not deeply integrated**
   - `voice/vad.py` exists.
   - `voice/listener.py` lazy-loads VAD but still primarily uses `speech_recognition` phrase capture and Google Web Speech.
   - This creates turn boundaries after utterances, not a low-latency streaming voice session.

4. **TTS streaming is sentence-level, not duplex realtime**
   - `Speaker.speak_stream()` can speak sentences as chunks arrive.
   - But STT, LLM streaming, TTS, and interruption are not coordinated by a single duplex session controller.

5. **Callbacks are point-to-point**
   - GUI callbacks, stream callbacks, voice callbacks, and state callbacks are registered manually.
   - A realtime system needs an event bus with typed events and lifecycle ownership.

6. **No scheduler or background worker model**
   - Long-running tasks are not represented as jobs.
   - There is no priority queue for urgent voice input versus background project work.

## 4. What Prevents Full Desktop Control

Current desktop control is mostly command execution and shell-level automation.

Existing capabilities:

- Launch known apps and websites.
- Close processes by executable name.
- Open browser URLs and search pages.
- Control volume, mute, screenshot, lock, sleep, restart, shutdown.
- Read and set clipboard.
- Find and open files.
- Press keys and type text using `pyautogui` if available.
- Capture screenshots and run vision analysis.

Blockers to full desktop control:

1. **No UI action model**
   - DREX cannot represent actions like click button, select menu item, fill field, drag item, wait for dialog, or verify result as structured steps.

2. **No observation-action loop**
   - Screen vision can describe a screenshot, but automation does not use vision continuously to decide the next action.

3. **No app adapters**
   - Browser, VS Code, file explorer, terminal, PDF reader, email, and office apps need specialized controllers.
   - Current browser support opens URLs; it does not inspect DOM, tabs, forms, downloads, or page state.

4. **No reliable active window controller**
   - `assistant/app_awareness.py` detects active window metadata.
   - It does not own focus, window positioning, app state, foreground enforcement, or process/window mapping.

5. **No permission contract for broad control**
   - `PermissionManager` exists, but approvals are not wired into a full action policy with risk classes, scopes, audit logs, and user overrides.

6. **No verification**
   - Commands return messages, but DREX usually does not check whether the desired external state was achieved.

## 5. What Prevents Autonomous Task Execution

Current DREX can perform single commands. It cannot yet execute projects autonomously.

Blockers:

1. **No planner**
   - There is no module that converts a goal into a task graph with steps, dependencies, tools, checkpoints, and completion criteria.

2. **No durable task queue**
   - There is no persistent job table for pending, active, paused, failed, retried, and completed tasks.

3. **No execution state**
   - Memory stores conversations and facts, not current plan state, tool outputs, action attempts, or unresolved blockers.

4. **No verification/retry loop**
   - Actions do not have expected outcomes, validation functions, retries, fallback tools, or rollback behavior.

5. **No project workspace model**
   - DREX has file utilities, but no concept of a project root, repo state, open files, dependency graph, tests, or user objective.

6. **No tool result schema**
   - Automation modules mostly return strings. Autonomous agents need structured results: success, failure reason, changed resources, evidence, next suggested action.

7. **No long-running supervision**
   - Background task execution is not supervised by a runtime with cancellation, pause/resume, progress events, and user approval interrupts.

## 6. What Prevents Sub-Second Responses

DREX has a `FastRouter`, which is the right instinct. But sub-second response requires the fast path to be the product default for simple cases, not just a shortcut inside a large synchronous method.

Blockers:

1. **Heavy startup and per-request path**
   - `Orchestrator.process()` touches routing, memory, AI prompt building, and optional TTS in one method.

2. **Network STT**
   - `voice/listener.py` uses Google Web Speech first, with Sphinx fallback.
   - Network speech recognition makes sub-second voice response unreliable.

3. **Provider fallback delays**
   - AI fallback intentionally sleeps on rate limits or connection issues.
   - Good for reliability, bad for low latency unless separated by request type.

4. **No intent cache / prewarming**
   - Common commands are regex-matched, but models, clients, and screen context are not proactively warmed and cached for realtime use.

5. **No local small model path**
   - Fast classification is regex/keyword-based.
   - There is no local intent model for fuzzy commands, corrections, or tool selection.

6. **Potential fast-path bug**
   - In `Orchestrator.process()`, the fast-router branch references `provider` before it is assigned in the visible code path. This should be audited before relying on FastRouter as the realtime path.

## 7. What Prevents Multimodal Awareness

Existing pieces:

- `assistant/screen_capture.py`
- `assistant/vision_analyzer.py`
- `assistant/app_awareness.py`
- `utils/document_extractor.py`
- OCR/PDF/document utilities

Blockers:

1. **On-demand vision only**
   - Screen analysis happens when asked, not continuously or opportunistically.

2. **No awareness bus**
   - Active window, screen OCR, clipboard, browser state, project state, voice state, and user task state are not normalized into one shared context stream.

3. **No temporal model**
   - DREX does not know what changed on screen over time.

4. **No browser DOM awareness**
   - Browser automation opens pages, but there is no browser extension, CDP controller, Playwright session, or DOM extractor.

5. **No project awareness**
   - There is no watcher for active repo, git status, open editor files, test results, terminal output, or running dev server.

6. **No multimodal prompt policy**
   - Prompt building injects conversation and facts; it does not automatically decide when to include screen, clipboard, active app, selected text, or project context.

## 8. What Prevents Continuous Background Operation

Existing pieces:

- `assistant/system_tray.py`
- `assistant/global_hotkey.py`
- `assistant/floating_orb.py`
- `voice/wake_word.py`
- `voice/listener.py`
- `core/voice_agent.py`

Blockers:

1. **Main entry point still launches GUI-first**
   - `main.py` starts `DrexApp` for normal mode.
   - It does not compose `StateEngine`, `ModeManager`, tray, hotkeys, floating orb, voice agent, and orchestrator into a daemon runtime.

2. **Lifecycle ownership is fragmented**
   - GUI owns callbacks.
   - Orchestrator owns voice modules lazily.
   - Assistant runtime modules own state separately.
   - There is no single runtime supervisor.

3. **No background task supervision**
   - Continuous operation needs jobs, health checks, watchdogs, crash recovery, and restart policy.

4. **Optional dependencies degrade silently**
   - Many capabilities are optional and log warnings.
   - The product needs a capability registry visible to the runtime and UI.

5. **No resource budget manager**
   - Continuous microphone, screen monitoring, OCR, and AI calls need CPU, battery, privacy, and frequency budgets.

## Core Diagnosis

DREX feels like a chatbot because the **chat turn** is still the atomic unit of the system.

A Jarvis-style assistant needs the **operating context** to be the atomic unit:

- What is the user doing?
- What changed?
- What task is active?
- What can DREX safely do next?
- What does DREX need to observe before acting?
- Is the user speaking, interrupting, waiting, or ignoring?

The shortest path is not another UI redesign. It is to make the assistant runtime the primary composition root and make chat a secondary mode.

