# Phase 6 — Awareness System

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AwarenessEngine                           │
│  Central coordinator — owns all awareness subsystems        │
│  Maintains SystemSnapshot, refreshes every 5s               │
│  Provides get_context_for_prompt() for AI injection         │
├───────────────────────┬─────────────────────────────────────┤
│   WindowTracker       │      ScreenAnalyzer                 │
│   polls every 2s      │      on-demand analysis             │
│   pygetwindow + psutil│      wraps ScreenCapture +          │
│   publishes           │      VisionAnalyzer from            │
│   window_changed      │      assistant/ module              │
│   events on change    │      30s cache for dedup            │
└───────────┬───────────┴───────────┬─────────────────────────┘
            │                       │
            ▼                       ▼
    ┌───────────────┐     ┌──────────────────┐
    │  WindowInfo   │     │  ScreenContext   │
    │  dataclass    │     │  dataclass       │
    │  title        │     │  description     │
    │  process_name │     │  visible_text    │
    │  pid          │     │  ui_elements     │
    │  is_active    │     │  captured_at     │
    └───────────────┘     └──────────────────┘
            │                       │
            └───────────┬───────────┘
                        ▼
              ┌──────────────────┐
              │  SystemSnapshot  │
              │  dataclass       │
              │  active_window   │
              │  screen_context  │
              │  cpu_percent     │
              │  memory_percent  │
              └──────────────────┘
```

## Awareness Data Flow

```
[System]                         [AwarenessEngine]              [Orchestrator]
   │                                    │                            │
   │  WindowTracker polls every 2s      │                            │
   │  ├── pygetwindow.getActiveWindow() │                            │
   │  ├── psutil for process name       │                            │
   │  └── publish window_changed if     │                            │
   │      title differs                 │                            │
   │                                    │                            │
   │  Snapshot refresh every 5s         │                            │
   │  ├── WindowTracker.get_current()   │                            │
   │  ├── ScreenAnalyzer.get_cached()   │                            │
   │  ├── psutil.cpu_percent()          │                            │
   │  ├── psutil.virtual_memory()       │                            │
   │  └── publish context_updated       │                            │
   │                                    │                            │
   │  Screen analysis on demand:        │                            │
   │  ├── ScreenCapture.capture_full()  │                            │
   │  ├── VisionAnalyzer.analyze()      │                            │
   │  └── cache for 30s TTL            │                            │
   │                                    │                            │
   │                                    │  get_context_for_prompt()  │
   │                                    │◄───────────────────────────│
   │                                    │       injects into         │
   │                                    │     _get_ai_response()     │
   │                                    │───────────────────────────►│
   │                                    │    [System Context: ...]   │
   │                                    │                            │
   │                                    │  describe_screen()         │
   │                                    │◄─────────── (screen_query  │
   │                                    │────────────  intent)       │
   │                                    │  "You have Code.exe..."    │
```

## Event Flow Diagram

```
WindowTracker          EventBus              Subscribers
    │                     │                      │
    │ (title changed)     │                      │
    │────────────────────►│                      │
    │ window_changed      │─────────────────────►│ (any subscriber)
    │                     │                      │
AwarenessEngine           │                      │
    │                     │                      │
    │ (snapshot refresh)  │                      │
    │────────────────────►│                      │
    │ context_updated     │─────────────────────►│ (any subscriber)
    │                     │                      │
ScreenAnalyzer            │                      │
    │                     │                      │
    │ (screen analyzed)   │                      │
    │────────────────────►│                      │
    │ screen_analyzed     │─────────────────────►│ (any subscriber)
```

## Polling Intervals & Cache TTL Rationale

| Component | Interval/TTL | Rationale |
|-----------|-------------|-----------|
| WindowTracker poll | 2 seconds | Fast enough to catch window switches (~0.5s human response time); light enough to avoid measurable CPU impact |
| SystemSnapshot refresh | 5 seconds | Balances freshness of CPU/memory data with overhead; window data may be up to 2s old anyway |
| ScreenAnalyzer cache | 30 seconds | Vision API calls are expensive (latency + token cost). 30s TTL means the user sees "what was on screen 30s ago" — acceptable for context injection |

## CPU & Memory Impact

- **WindowTracker**: ~0.1ms per poll (pygetwindow call + optional psutil). 0.1ms × 0.5Hz = 0.05% CPU.
- **SystemSnapshot**: ~0.5ms per refresh (psutil calls). 0.5ms × 0.2Hz = 0.01% CPU.
- **ScreenAnalyzer**: Zero CPU when idle (on-demand only). When active: ~200-500ms for screenshot + ~1-3s for vision API call.
- **Memory**: ~1 MB total for all awareness data structures.

## Files Created

| File | Purpose | Size |
|------|---------|------|
| `runtime/awareness/__init__.py` | Package exports | 1.2 KB |
| `runtime/awareness/awareness_models.py` | WindowInfo, ScreenContext, SystemSnapshot | 3.8 KB |
| `runtime/awareness/awareness_events.py` | WindowChanged, ScreenAnalyzed, ContextUpdated, AppOpened, AppClosed | 1.0 KB |
| `runtime/awareness/window_tracker.py` | WindowTracker background poller | 6.5 KB |
| `runtime/awareness/screen_analyzer.py` | ScreenAnalyzer with caching | 5.2 KB |
| `runtime/awareness/awareness_engine.py` | AwarenessEngine coordinator | 7.1 KB |
| `tests/test_phase6.py` | 55 test cases | 11.5 KB |
| `docs/phase6_awareness_system.md` | This document | — |

## Files Modified

| File | Lines Changed | Change |
|------|--------------|--------|
| `runtime/__init__.py` | Lines 31-45, 140-153 | Imported and exported all awareness classes |
| `main.py` | Lines 258-273 | Registered AwarenessEngine with RuntimeSupervisor + capabilities |
| `core/orchestrator.py` | Lines 98-101, 153-156 | Added `awareness_engine` class-level + instance attributes |
| `core/orchestrator.py` | Lines 730-750 | Injected awareness context into `_get_ai_response()` via extra_context |
| `core/orchestrator.py` | Lines 890-897 | Added AwarenessEngine fallback in `_handle_screen_query()` |

## Full RuntimeSupervisor Component Tree (All Phases)

```
RuntimeSupervisor
├── event_bus          [autostart=false]  Phase 1
├── orchestrator       [autostart=false]  Phase 1
├── voice_engine       [autostart=true]   Phase 2
├── tool_registry      [autostart=false]  Phase 3
├── tool_executor      [autostart=false]  Phase 3
├── task_manager       [autostart=true]   Phase 5A
├── planner            [autostart=true]   Phase 5B
├── execution_engine   [autostart=true]   Phase 5C
├── awareness_engine   [autostart=true]   Phase 6 ◄── NEW
└── capability_registry [autostart=false] Phase 1
```

## Test Results Summary

| Suite | Result |
|-------|--------|
| Phase 4 (IntentService, ToolRouter, ResponseService) | 24/24 PASS ✓ |
| Phase 5A (TaskManager, TaskStore) | 47/47 PASS ✓ |
| Phase 5B (Planner, GoalDecomposer) | 82/82 PASS ✓ |
| Phase 5C (ExecutionEngine, ExecutionModels) | 34/34 PASS ✓ |
| Phase 6 (Awareness models, tracker, analyzer, engine, runtime) | 55/55 PASS ✓ |
| main.py --test (system diagnostics) | 14/14 PASS ✓ |

## Success Criteria Verification

- [x] `python main.py --test` → 14/14 PASS
- [x] `python tests/test_phase4.py` → 24/24 PASS
- [x] `python tests/test_phase5a.py` → 47/47 PASS
- [x] `python tests/test_phase5b.py` → 82/82 PASS
- [x] `python tests/test_phase5c.py` → 34/34 PASS
- [x] `python tests/test_phase6.py` → 55/55 PASS
- [x] AwarenessEngine autostarts with RuntimeSupervisor
- [x] "awareness" and "screen_awareness" registered in CapabilityRegistry
- [x] WindowTracker polls every 2 seconds without blocking GUI
- [x] awareness.window_changed fires when window switches
- [x] orchestrator.awareness_engine is accessible
- [x] get_context_for_prompt() injects into AI calls
- [x] describe_screen() works for screen_query intent
- [x] No existing functionality broken
- [x] No continuous screen recording (on-demand only)

## Future Integration Points

### Phase 7 — Jarvis UI HUD (Next)
```
AwarenessEngine.get_context_for_prompt()
         │
         ▼
JarvisPanel displays:
  ┌──────────────────────┐
  │ 🖥 VS Code            │  ← active window
  │ 📄 script.py          │  ← window title
  │ ⚡ CPU: 23% RAM: 61%  │  ← system stats
  └──────────────────────┘
```

### Future — Browser Awareness
```
BrowserAwarenessPlugin → reads Chrome tabs via chrome.debugger API
                       → merges into SystemSnapshot.browser_tabs
                       → awareness.context_updated carries tab info
```

### Future — File / Project Awareness
```
FileAwarenessPlugin → watches active editor path
                    → detects open projects (package.json, .git)
                    → injected as "You are working on: DREX project"