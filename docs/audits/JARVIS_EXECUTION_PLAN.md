# DREX Jarvis Execution Plan

## Ranking Principle

This roadmap ranks work by product transformation impact, not by visual novelty.

Cosmetic UI work is intentionally not first. DREX will stop feeling like a chatbot only when the runtime, voice loop, awareness model, and execution model change.

## High Impact

### 1. Create Runtime Supervisor and Event Bus

Impact: High  
Complexity: Medium  
Risk: Medium  
Estimated time: 2-4 days

Build the new composition root that owns lifecycle and event flow.

Deliverables:

- `RuntimeSupervisor`
- typed event bus
- engine startup/shutdown order
- runtime health status
- cancellation tokens
- structured event logging

Why first:

Without this, every other feature keeps attaching to `Orchestrator.process()` and the app remains a chatbot with more modules.

### 2. Promote Voice Engine to First-Class Runtime Component

Impact: High  
Complexity: Medium-High  
Risk: Medium  
Estimated time: 3-6 days

Move voice lifecycle out of GUI/orchestrator ownership.

Deliverables:

- `VoiceEngine`
- wake word events
- VAD events
- final transcript events
- TTS start/end events
- interruption events
- clean state transitions into `StateEngine`

Why:

Jarvis is voice-first. The microphone cannot be a button attached to chat.

### 3. Split `Orchestrator.process()` into Services

Impact: High  
Complexity: High  
Risk: High  
Estimated time: 5-8 days

Break the monolithic request path into composable services.

Deliverables:

- `IntentService`
- `ConversationService`
- `ToolRouter`
- `ScreenQuestionService`
- `ResponseService`
- structured `AssistantResult`

Why:

Current orchestration blocks realtime behavior, autonomous tasks, and clean mode separation.

### 4. Add Structured Tool Interface

Impact: High  
Complexity: Medium  
Risk: Medium  
Estimated time: 3-5 days

Convert automation from string-returning handlers into structured tools.

Deliverables:

- `ToolRequest`
- `ToolResult`
- `ToolRegistry`
- risk classification
- permission requirement metadata
- audit record for each action

Why:

Autonomy requires tools that machines can reason about, not just user-facing messages.

### 5. Add Task Planner and Durable Task Queue

Impact: High  
Complexity: High  
Risk: High  
Estimated time: 7-12 days

Add autonomous execution backbone.

Deliverables:

- task table
- task step table
- planner interface
- executor loop
- pause/resume/cancel
- progress events
- verification hooks
- blocker reporting

Why:

This is the difference between "open Chrome" and "complete this project task while I work."

### 6. Add Observation-Action-Verification Loop

Impact: High  
Complexity: High  
Risk: High  
Estimated time: 6-10 days

Make desktop actions self-checking.

Deliverables:

- screen before/after snapshots
- active window verification
- process/window verification
- generic wait conditions
- retry policy
- failure reason taxonomy

Why:

Full desktop control is impossible without knowing whether actions worked.

### 7. Make Agent/Orb Runtime the Default Product Shell

Impact: High  
Complexity: Medium  
Risk: Medium  
Estimated time: 3-5 days

Use the existing `assistant/` runtime concepts as the default interaction model.

Deliverables:

- boot to background runtime
- tray icon starts by default
- orb visible by default
- chat opens as secondary mode
- state engine drives UI
- hotkeys wired to runtime

Why:

The current app starts as a desktop chat window. The target product must start as an assistant presence.

## Medium Impact

### 8. Add Capability Registry

Impact: Medium-High  
Complexity: Medium  
Risk: Low  
Estimated time: 2-3 days

Track installed and available capabilities.

Deliverables:

- provider availability
- voice availability
- wake word availability
- VAD availability
- pyautogui availability
- screen capture availability
- tray/hotkey availability
- browser automation availability

Why:

Optional dependencies currently degrade in scattered ways. A runtime assistant needs to know its actual powers.

### 9. Upgrade Memory to Task and Context Memory

Impact: Medium-High  
Complexity: Medium-High  
Risk: Medium  
Estimated time: 4-7 days

Add memory domains beyond chat.

Deliverables:

- project records
- task records
- tool event records
- awareness snapshots
- action audit history
- semantic memory plan

Why:

Jarvis needs continuity, not just conversation history.

### 10. Add Active Window and Screen Awareness Bus

Impact: Medium-High  
Complexity: Medium  
Risk: Medium  
Estimated time: 4-6 days

Turn on context gathering in a controlled way.

Deliverables:

- active window polling
- screen snapshot throttling
- clipboard change events
- awareness cache
- privacy controls
- context injection policy

Why:

Context-aware response requires context to exist before the user asks.

### 11. Add Browser Awareness and Control

Impact: Medium-High  
Complexity: High  
Risk: Medium  
Estimated time: 7-14 days

Move beyond opening URLs.

Deliverables:

- browser adapter
- active tab detection
- page title/URL extraction
- DOM text extraction
- form filling
- tab management
- download monitoring

Why:

Much of a modern operating assistant's work happens in the browser.

### 12. Add Project Awareness for Development Workflows

Impact: Medium-High  
Complexity: Medium-High  
Risk: Medium  
Estimated time: 5-10 days

Make DREX understand local projects.

Deliverables:

- detect repo root
- git status summary
- file tree summaries
- test command detection
- terminal output ingestion
- current IDE/window awareness

Why:

"Project execution capable" requires understanding projects as persistent objects.

### 13. Local Fast Intent Model

Impact: Medium  
Complexity: Medium  
Risk: Medium  
Estimated time: 3-6 days

Supplement regex fast routing with a local classifier.

Deliverables:

- local intent classifier
- confidence threshold
- fallback to LLM
- command alias learning
- latency metrics

Why:

Sub-second responses need fuzzy intent recognition without remote model calls.

### 14. Permission and Safety Policy Upgrade

Impact: Medium  
Complexity: Medium  
Risk: Medium  
Estimated time: 3-5 days

Make permissions systematic.

Deliverables:

- risk levels
- approval UI events
- remembered approvals by scope
- audit trail
- destructive action safeguards
- privacy settings for screen/mic/clipboard

Why:

Full desktop control without a trust model is brittle and risky.

## Low Impact

### 15. HUD UI Consolidation

Impact: Low-Medium  
Complexity: Medium  
Risk: Low  
Estimated time: 3-5 days

After runtime changes, consolidate Jarvis UI surfaces.

Deliverables:

- one orb/HUD component strategy
- remove duplicate mode concepts
- state-driven indicators
- compact awareness panels

Why not first:

A better HUD on top of chatbot architecture still feels like a chatbot.

### 16. Settings Cleanup

Impact: Low  
Complexity: Low-Medium  
Risk: Low  
Estimated time: 1-3 days

Only after the capability registry exists.

Deliverables:

- settings based on actual capabilities
- voice/privacy controls
- provider status
- hotkey configuration

### 17. Chat Panel Simplification

Impact: Low  
Complexity: Low  
Risk: Low  
Estimated time: 1-2 days

Keep chat as long-form mode, but stop treating it as home base.

Deliverables:

- chat mode remains available
- remove redundant assistant-mode controls from chat surface
- use runtime state instead of chat-specific state where possible

### 18. Visual Polish

Impact: Low  
Complexity: Low-Medium  
Risk: Low  
Estimated time: ongoing

Polish after product behavior changes.

Deliverables:

- animation quality
- status text
- icon consistency
- HUD density
- accessibility

## Suggested Implementation Order

1. Runtime supervisor and event bus
2. Capability registry
3. Voice engine ownership
4. Structured tool interface
5. Orchestrator split
6. Agent/orb runtime as default shell
7. Task planner and durable queue
8. Observation-action-verification loop
9. Awareness bus
10. Browser and project adapters
11. Memory upgrade
12. UI consolidation

## Key Risks

### Architecture Regression

Risk:

Breaking existing chat, streaming, memory, or provider fallback while reorganizing.

Mitigation:

Wrap existing orchestrator first. Do not rewrite all logic at once.

### Dependency Fragility

Risk:

Voice, tray, hotkeys, screen capture, and GUI modules rely on optional OS packages.

Mitigation:

Capability registry plus graceful degradation.

### Unsafe Automation

Risk:

Desktop control can close apps, delete files, expose screen data, or type in the wrong window.

Mitigation:

Permission policy, active window verification, scoped approvals, and audit logs.

### Latency Drift

Risk:

Adding awareness and planning can make simple commands slower.

Mitigation:

Preserve fast path. Route common commands through local intent and structured tools before any remote model call.

## Definition of Done for Transformation

DREX no longer feels like a chatbot when:

- It starts as an always-available assistant presence.
- Voice activation is primary.
- It can answer simple commands in under one second.
- It knows the active app/screen when relevant.
- It can execute multi-step desktop tasks.
- It verifies actions.
- It can be interrupted naturally.
- Chat is a secondary mode, not the product's center.
