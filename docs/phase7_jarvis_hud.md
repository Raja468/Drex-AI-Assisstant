# Phase 7: Jarvis HUD — Documentation

## Before/After UI Architecture

```
BEFORE (Phase 6):
┌──────────────────────────────────────────────────────┐
│  StatusBar (top)                                      │
├──────────┬───────────────────────────────────────────┤
│          │                                           │
│  Sidebar │  ChatPanel (always visible)               │
│  (240px) │  + InputBar (bottom)                      │
│          │                                           │
└──────────┴───────────────────────────────────────────┘

AFTER (Phase 7):
┌──────────────────────────────────────────────────────┐
│  StatusBar (top)                                      │
├──────────┬───────────────────────────────────────────┤
│          │                                           │
│  Sidebar │  JARVIS HUD (default)    ◄── CHANGED     │
│  (240px) │  ┌─────────────────────────────────┐     │
│          │  │  HUDHeader (clock/status)        │     │
│          │  ├──────────┬───────────┬──────────┤     │
│          │  │ Stats    │   Orb     │ Session  │     │
│          │  │ Panel    │  (center) │ Panel    │     │
│          │  │ (180px)  │ (expand)  │ (180px)  │     │
│          │  ├──────────┴───────────┴──────────┤     │
│          │  │  HUDFooter (cmd/latency)         │     │
│          │  └─────────────────────────────────┘     │
│          │                                           │
└──────────┴───────────────────────────────────────────┘
```

## Widget Hierarchy

```
DrexApp (CTk)
├── status_bar: StatusBar
├── sidebar: Sidebar
├── center_panel: CTkFrame
│   ├── chat_panel: ChatPanel         (grid_remove() in jarvis mode)
│   ├── input_bar: InputBar           (grid_remove() in jarvis mode)
│   └── jarvis_panel: JarvisPanel     (grid_remove() in chat mode)
│       ├── _header: HUDHeader
│       │   ├── title: "DREX | PERSONAL ASSISTANT"
│       │   ├── STATUS column
│       │   ├── MODE column
│       │   ├── ERRORS column
│       │   └── clock: live updating
│       ├── _stats_panel: HUDStatsPanel
│       │   ├── CPU
│       │   ├── RAM
│       │   ├── WINDOW
│       │   └── PROCESS
│       ├── _orb: JarvisOrb           (animated canvas)
│       │   └── _task_progress_frame  (hidden by default)
│       │       ├── _task_progress_label
│       │       └── _task_progress_bar
│       └── _session_panel: HUDSessionPanel
│           ├── PROVIDER
│           ├── RESPONSES
│           ├── AVG TIME
│           └── UPTIME
└── _footer: HUDFooter
    ├── LAST CMD
    ├── LATENCY
    └── TIME
```

## Thread Safety Notes

**Rule: ALL Tkinter/CTk widget updates MUST happen on the main thread.**

### Bridge mechanisms used:

1. **Queue-based (existing pattern):**
   - `_response_queue` in app.py
   - Background thread → `put()` → Main thread `_poll_queue()` via `after(50ms)`

2. **VoiceAgent callback:**
   ```
   VoiceAgent (background thread)
     → on_state_change callback
     → lambda state: self.after(0, ...)  ← schedules on main thread
     → DrexApp._on_voice_state_changed()
   ```

3. **EventBus subscriptions:**
   ```
   AwarenessEngine._snapshot_loop (background thread)
     → EventBus.publish(ContextUpdated)
     → DrexApp._on_context_updated()  ← called on publishing thread
     → self.after(0, lambda: jarvis_panel.update_system_stats(...))  ← schedules on main thread
   ```

4. **Animation loops:**
   - `JarvisOrb._animate()` uses `self.after(speed, self._animate)` — already on main thread
   - `HUDHeader._update_clock()` uses `self.after(1000, ...)` — already on main thread

## Voice State → Orb State Mapping

| VoiceAgent Enum | Orb State | Header Status | Orb Color | Animation |
|-----------------|-----------|---------------|-----------|-----------|
| `VoiceState.IDLE` | `"idle"` | STANDBY | `#00d4ff` (cyan, dim) | Slow rotation |
| `VoiceState.LISTENING` | `"listening"` | LISTENING | `#00d4ff` (cyan, bright) | Pulse rings |
| `VoiceState.PROCESSING` | `"processing"` | PROCESSING | `#ffb800` (amber) | Fast spinner |
| `VoiceState.SPEAKING` | `"speaking"` | SPEAKING | `#00ff88` (green) | Wave rings |
| `VoiceState.INTERRUPTED` | `"interrupted"` | INTERRUPTED | `#ff3860` (red flash) | Red alternation |

## Awareness → HUD Update Flow

```
AwarenessEngine._snapshot_loop (every 5s)
    └── _refresh_snapshot()
        └── Builds SystemSnapshot (cpu, ram, active_window)
        └── Publishes: EventBus.publish(ContextUpdated, {"snapshot": ...})

            ┌─── DrexApp._on_context_updated(event) ───┐
            │  (called on EventBus thread)              │
            │  Extracts snapshot from event.payload      │
            │  Calls: self.after(0, lambda: ...)         │
            └────────────────────────────────────────────┘
                        ↓
            ┌─── Main thread: jarvis_panel.update_system_stats() ──┐
            │  Flashes CPU/RAM/WINDOW/PROCESS labels on change     │
            └───────────────────────────────────────────────────────┘
```

## How to Add New HUD Panels in Future

1. Create new widget file in `gui/` (e.g., `gui/hud_mypanel.py`)
2. Widget inherits from `ctk.CTkFrame`
3. Add update methods that run on main thread
4. Import and instantiate in `gui/jarvis_panel.py`
5. Grid into the 3-column layout:
   - Column 0: left panel (fixed 180px)
   - Column 1: center orb area (expands)
   - Column 2: right panel (fixed 180px)
6. Expose update method on `JarvisPanel` for app.py to call
7. Wire events in `app.py._connect_orchestrator()` via `self.after()`

## Key Files

| File | Purpose |
|------|---------|
| `gui/app.py` | Root window, mode switching, event wiring |
| `gui/jarvis_panel.py` | Jarvis HUD container (embedded CTkFrame) |
| `gui/jarvis_orb.py` | Animated orbital ring canvas |
| `gui/hud_header.py` | Header bar with clock/status/mode/errors |
| `gui/hud_footer.py` | Footer with last command/latency/time |
| `gui/hud_stats_panel.py` | Left: CPU/RAM/WINDOW/PROCESS |
| `gui/hud_session_panel.py` | Right: PROVIDER/RESPONSES/AVG/UPTIME |
| `gui/sidebar.py` | Left sidebar with mode toggle + personality |
| `runtime/awareness/awareness_engine.py` | System snapshot every 5s |
| `core/voice_agent.py` | Voice state machine with on_state_change |

## Design Decisions

- **JarvisPanel is CTkFrame, not CTkToplevel**: embedded inside `center_panel`
- **No拆除 chat panel**: chat_panel always exists, just grid_remove() in jarvis mode
- **Default mode = jarvis**: matches app.py line 77 and sidebar.py line 47
- **Input bar hidden in jarvis mode**: voice-first interaction
- **All HUD updates via after()**: never touch widgets from background threads
- **Session stats accumulate**: response_count and total_latency_ms tracked per session