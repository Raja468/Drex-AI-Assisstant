# Phase 5B — Planner Foundation

## Architecture

```
RuntimeSupervisor
 ├── EventBus
 ├── CapabilityRegistry
 ├── ToolRegistry + ToolExecutor          (Phase 3)
 ├── TaskManager + TaskStore              (Phase 5A)
 └── Planner                              (Phase 5B)
      └── GoalDecomposer (rule-based)
```

## Plan Lifecycle

```
DRAFT ──→ READY ──→ ACTIVE ──→ COMPLETED
                    │            │
                    ├── PAUSED ──┘
                    │
                    ├── FAILED
                    └── CANCELLED
```

1. **DRAFT** — Plan created via `Planner.create_plan()`. Goal decomposer generates step list.
2. **READY** — All steps have titles. `is_ready()` returns `True`.
3. **ACTIVE** — Plan is being worked on (future phase).
4. **COMPLETED** — All steps completed successfully.
5. **PAUSED** — Work on plan suspended.
6. **FAILED** — An error occurred during execution.
7. **CANCELLED** — Plan abandoned.

## GoalDecomposer Template Matching

The decomposer uses a **two-pass** matching strategy:

1. **Pass 1: Exact word match** — If a template key appears as a complete word in the goal, it matches immediately. Keys are sorted by length descending (longest first) so `"documentation"` matches before `"api"` or `"website"`.

2. **Pass 2: Substring match** — If no exact word match is found, checks if any template key appears as a substring anywhere in the goal text.

3. **Fallback** — If no template matches, returns the `"default"` template.

### Template Library

| Key | Steps | Priority |
|-----|-------|----------|
| `documentation` | 5 steps | Length `13` |
| `database` | 5 steps | Length `8` |
| `website` | 5 steps | Length `7` |
| `python` | 5 steps | Length `6` |
| `react` | 6 steps | Length `5` |
| `api` | 5 steps | Length `3` |
| `default` | 5 steps | Fallback |

## Event Flow

```
Planner.create_plan(goal)
  │
  ├── GoalDecomposer.decompose(goal) → list[str]
  ├── Create Plan dataclass with PlanSteps
  ├── Store in self._plans[plan.id]
  ├── Publish: EventBus → planner.plan_created
  └── Return Plan

Planner.update_plan(plan_id, **kwargs)
  ├── Update fields on Plan
  ├── Store in self._plans[plan.id]
  ├── Publish: EventBus → planner.plan_updated
  └── Return Plan
```

### Events Published

- `planner.plan_created` — Plan created via `create_plan()`
- `planner.plan_updated` — Plan modified via `update_plan()`
- `planner.plan_completed` — Plan completed via future execution
- `planner.plan_failed` — Plan failed via future execution
- `planner.plan_cancelled` — Plan cancelled via future execution

## Future Integration Points

### Phase 5C → Execution Engine
- Connect Planner + TaskManager
- Planner creates Plans, Execution Engine creates Tasks from PlanSteps
- Each completed task step updates the Plan status
- Wire into orchestration pipeline

### Phase 6 → Awareness System
- System context feeds into Planner for smarter decomposition
- Awareness of current desktop state influences plan creation
- Application detection, file system state, running processes

### Phase 7 → Jarvis UI
- Display active plans in GUI
- Plan progress visualization (step completion)
- User can approve/modify/cancel plans
- Voice feedback for plan summaries

## Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `runtime/planning/__init__.py` | Package init | 22 |
| `runtime/planning/plan_models.py` | Plan, PlanStep, PlanStatus, PlanPriority | 108 |
| `runtime/planning/planner_events.py` | 5 lifecycle events | 30 |
| `runtime/planning/goal_decomposer.py` | Rule-based goal decomposition | 107 |
| `runtime/planning/planner.py` | Main planning service | 176 |
| `tests/test_phase5b.py` | 24 tests, 82 assertions | 340 |

## Files Modified

| File | Line(s) | Change |
|------|---------|--------|
| `main.py` | 227–237 | Planner + GoalDecomposer creation, RuntimeSupervisor registration |
| `main.py` | 247 | `planning` capability registered |
| `runtime/__init__.py` | 39–47 | Import planning classes |
| `runtime/__init__.py` | 87–97 | Added planning exports to `__all__` |
| `core/orchestrator.py` | N/A | `orchestrator.planner = planner` added in main.py wiring |

## Risks Discovered

1. **Template key collision** — Short keys like `"api"` (3 chars) can match as substrings in unrelated words. Mitigated by two-pass word-match-first strategy and length-descending sort order.

2. **In-memory only storage** — Plans do not survive restart in Phase 5B. This is intentional — Phase 5C will add persistence when connecting to TaskStore/TaskManager.

## Test Results

```
Phase 4  : 24/24 PASS
Phase 5A : 47/47 PASS
Phase 5B : 82/82 PASS (24 scenarios)
Diagnostics: 14/14 PASS
```

## Readiness for Phase 5C

✅ **Ready.** Planner creates structured plans from goals. No tools executed, no AI called. Foundation for execution engine is stable and tested.