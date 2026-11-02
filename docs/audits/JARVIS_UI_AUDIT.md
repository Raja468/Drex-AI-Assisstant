# DREX Jarvis UI Audit

## Summary

The current UI still presents DREX as a chat application with assistant features attached.

There are Jarvis-style components in the repository:

- `gui/jarvis_orb.py`
- `gui/jarvis_panel.py`
- `assistant/floating_orb.py`
- `assistant/agent_panel.py`
- `assistant/system_tray.py`
- `assistant/global_hotkey.py`
- `assistant/state_engine.py`

But the primary desktop UI remains:

- main window
- status bar
- sidebar
- chat panel
- input bar
- settings modal

That structure teaches the user: "type a message into a chat app."

A Jarvis-style AI operating assistant should teach: "DREX is present, listening, aware, and able to act."

## Current UI Model

Current default mental model:

```text
Open DREX window
Choose/chat in sidebar
Type or speak message
Wait for response bubble
Read response
Repeat
```

Target mental model:

```text
DREX is running
Orb/HUD shows state
User speaks or invokes hotkey
DREX understands context
DREX acts, reports progress, asks permission if needed
Chat opens only when long-form text is useful
```

## Comparison Against Jarvis / Iron Man HUD / AI OS Interfaces

### Jarvis

Expected:

- Ambient presence.
- Minimal explicit UI.
- Voice-first interaction.
- Immediate state feedback.
- System awareness.
- Action progress.
- Interruptible response.

Current:

- Chat window is dominant.
- Voice exists, but visually reads as an input option.
- HUD/orb exists but is not the core product shell.
- System awareness is hidden behind commands.

### Iron Man HUD

Expected:

- Live telemetry.
- Focused indicators.
- Context panels.
- Active task state.
- Motion tied to system state.

Current:

- Orb animation exists.
- Status bar exists.
- Chat bubbles dominate the interface.
- No persistent panels for active app, screen, current task, microphone state, tool execution, or permissions.

### AI Operating Systems

Expected:

- Task-centric interface.
- Background jobs.
- Context graph.
- Tool/action timeline.
- Approval queue.
- Project/workspace state.

Current:

- Conversations are visible.
- Tasks are not first-class UI objects.
- Automation results appear as text responses.
- There is no live task queue or action timeline.

### Voice-First Interfaces

Expected:

- Listening state is unmistakable.
- Wake word / muted / interrupted / speaking states are obvious.
- User does not need to look at chat to know what is happening.
- Visual feedback follows the voice loop.

Current:

- Voice toggle is attached to input bar and orb click behavior.
- State exists in code but is fragmented between voice state, assistant state, GUI status, and orb state.
- No unified voice session display.

## Unnecessary Chat Elements

These are not bad features, but they are over-prominent for the target product:

1. **Welcome prompt cards**
   - Useful for a chatbot onboarding flow.
   - Less useful for an always-on operating assistant.

2. **Message count / session chat framing**
   - Good for chat apps.
   - Not central to a Jarvis assistant.

3. **Persistent bottom text input as primary affordance**
   - Makes text chat feel like home base.
   - Text input should exist in chat mode, not define agent mode.

4. **Sidebar navigation as primary structure**
   - Sidebar implies an app with sections.
   - Jarvis should prioritize state, task, and context.

5. **Typing indicator as main progress signal**
   - A Jarvis assistant needs richer status:
     - listening
     - transcribing
     - thinking
     - using tool
     - verifying
     - waiting for permission
     - blocked

## Unnecessary Panels

Potentially unnecessary or over-weighted in Agent mode:

- Full sidebar.
- Full chat transcript.
- Settings-first navigation.
- Personality buttons as persistent prime UI.
- Help panel inside chat as a main discovery mechanism.

These can remain in Chat or Settings mode, but Agent mode should not be organized around them.

## Unused or Underintegrated UI

### Assistant Runtime UI

The `assistant/` package contains:

- Floating orb.
- Agent panel.
- System tray.
- Global hotkeys.
- State engine.
- Mode manager.

These appear architecturally intended for Agent mode, but `main.py` does not compose them as the default runtime.

### Jarvis Orb

`gui/jarvis_orb.py` provides a HUD-style ring system and status text.

Gap:

- It is a visual component, not yet a state-driven operating surface.
- It should reflect realtime state from `StateEngine` or `VoiceEngine`.
- It should not just replace chat visually; it should expose runtime state.

### Jarvis Panel

`gui/jarvis_panel.py` exists, but the current main composition path is still `gui/app.py`.

Gap:

- Need one canonical Jarvis/Agent surface.
- Avoid multiple parallel orb/panel concepts competing.

## Missing Realtime Indicators

Agent mode needs persistent indicators for:

- Wake word active/inactive.
- Microphone listening.
- VAD speech detected.
- Transcribing.
- Thinking / model selected.
- Speaking.
- Interruptible state.
- Tool execution.
- Verification.
- Permission required.
- Background task running.
- Network/provider degraded.
- Offline/local mode.

Current UI has some state labels, but not a unified realtime state model.

## Missing System Awareness Panels

The target UI should expose compact, glanceable panels for:

1. **Active App**
   - Current foreground app.
   - Window title.
   - App adapter status.

2. **Screen Awareness**
   - Last screen snapshot time.
   - OCR available/unavailable.
   - Vision provider available/unavailable.
   - Privacy mode.

3. **Current Task**
   - Goal.
   - Current step.
   - Progress.
   - Blocker/permission state.

4. **Execution Timeline**
   - Tool calls.
   - Results.
   - Verifications.
   - Failures.

5. **Voice Session**
   - Wake word.
   - Listening/transcribing/speaking.
   - Partial transcript.
   - Interruption detected.

6. **System Health**
   - AI providers.
   - Voice availability.
   - Hotkey/tray status.
   - Automation capability status.

## Target UI Structure

### Agent Mode

Primary:

- Floating orb or compact HUD.
- Voice state.
- Current task state.
- Minimal transcript only when useful.
- Permission prompts.
- Tool execution progress.

Secondary:

- Expandable command/task timeline.
- Compact context panel.
- Quick text input.

### Chat Mode

Purpose:

- Long-form conversations.
- Coding explanations.
- Document analysis.
- Reviewing history.

Chat mode should be a deliberate mode, not the default product identity.

### Background Mode

Purpose:

- Tray icon.
- Wake word.
- Hotkeys.
- Notifications.
- Background task progress.

## UI Recommendations

### High Priority

1. Make Agent/Orb runtime the default UI.
2. Drive all UI from a single `StateEngine`.
3. Add voice session indicators.
4. Add active task panel.
5. Add permission prompt surface.
6. Add tool execution timeline.
7. Keep chat as secondary mode.

### Medium Priority

1. Add active app and screen awareness chips.
2. Add provider/capability health indicators.
3. Add compact background task list.
4. Add interruption visual feedback.
5. Add "DREX is watching/listening" privacy status.

### Low Priority

1. Polish HUD visuals.
2. Improve ring animation.
3. Improve theme consistency.
4. Redesign settings.
5. Redesign sidebar.

## Main UI Diagnosis

DREX still feels like a chatbot because the UI shows:

- conversation first
- controls second
- context third
- action state barely at all

A Jarvis-style assistant should show:

- state first
- context second
- task/action third
- conversation only when needed
