# DREX Tool Runtime Architecture

> Phase 3 — Structured Tool Runtime for the Task Planner, Autonomous Workflows, and Agent Runtime

## Architecture Diagram

```
RuntimeSupervisor
    │
    ├── EventBus ←── ToolExecutor publishes:
    │                   tool.started
    │                   tool.completed
    │                   tool.failed
    │                   tool.permission_required
    │
    ├── CapabilityRegistry ←── tools register as:
    │                            tool.browser
    │                            tool.clipboard
    │                            tool.app_launcher
    │                            tool.screenshot
    │                            tool.file
    │                            tool.system
    │
    ├── ToolRegistry (managed component)
    │       │
    │       ├── register_tool(tool, capability_registry?)
    │       ├── get_tool(name)
    │       ├── list_tools(category?, risk_level?)
    │       └── execute_tool(request)  [convenience]
    │
    ├── ToolExecutor (managed component)
    │       │
    │       └── execute(request):
    │               ├── 1. Lookup (ToolRegistry)
    │               ├── 2. Validate (BaseTool.validate)
    │               ├── 3. Permission (PermissionEvaluator)
    │               ├── 4. Execute (BaseTool.execute with timing)
    │               └── 5. Publish events
    │
    └── Tool Adapters (wrapping existing automation)
            ├── BrowserTool → automation/browser_control.py
            ├── ClipboardTool → automation/system_control.py (clipboard)
            ├── AppLauncherTool → automation/app_launcher.py
            ├── ScreenshotTool → automation/system_control.py (screenshot)
            ├── FileTool → automation/file_manager.py
            └── SystemTool → automation/system_control.py
```

## Package Structure

```
runtime/tools/
├── __init__.py       — Package exports
├── models.py         — ToolRequest, ToolResult, ToolMetadata dataclasses
├── permissions.py    — RiskLevel (SAFE→CRITICAL), PermissionEvaluator
├── base_tool.py      — Abstract BaseTool (metadata, execute, validate)
├── registry.py       — ToolRegistry (register, list, execute, thread-safe)
├── executor.py       — ToolExecutor (full pipeline with events)
├── events.py         — Typed runtime events (ToolStarted, etc.)
└── adapters.py       — 6 tool adapters wrapping existing automation
```

## Execution Flow

```
Planner / Orchestrator / Agent
    │
    ├── Creates ToolRequest { tool_name, arguments, request_id }
    │
    ▼
ToolExecutor.execute(request)
    │
    ├── 1. ToolRegistry.get_tool(tool_name)
    │       └── Resolves to concrete BaseTool instance
    │
    ├── 2. tool.validate(request)
    │       └── Returns list of error strings (empty = valid)
    │
    ├── 3. PermissionEvaluator.check(risk_level, arguments)
    │       ├── SAFE/LOW → auto-approved
    │       ├── MEDIUM/HIGH/CRITICAL → checks approval handler
    │       └── No handler → denied (fail-safe)
    │
    ├── 4. Publish tool.started event
    │
    ├── 5. tool.execute(request) with time.perf_counter()
    │       ├── Success → ToolResult(success=True, output=...)
    │       └── Exception → ToolResult(success=False, error=...)
    │
    ├── 6. Publish tool.completed or tool.failed event
    │
    └── Returns ToolResult
```

## Event Flow

```
tool.started
    Payload: { tool_name, request_id, category, risk_level }
    Published by: ToolExecutor before execution

tool.completed
    Payload: { tool_name, request_id, category, risk_level, success, execution_time }
    Published by: ToolExecutor after success

tool.failed
    Payload: { tool_name, request_id, category, risk_level, success, execution_time }
    Published by: ToolExecutor after failure

tool.permission_required
    Payload: { tool_name, request_id, category, risk_level }
    Published by: ToolExecutor when permission is blocked
```

## Permission Model

| Risk Level | Examples | Auto-Approve? |
|------------|----------|---------------|
| SAFE | clipboard read, volume up, system info | Yes |
| LOW | browser search, open URL | Yes |
| MEDIUM | open/close app, find file | No (handler required) |
| HIGH | delete file, screenshot | No (handler required) |
| CRITICAL | shutdown, restart | No (handler required) |

## Tool Metadata

Each tool exposes a `ToolMetadata` descriptor:

```json
{
    "name": "browser",
    "description": "Search the web, open URLs, and navigate to sites",
    "category": "web",
    "risk_level": "low",
    "permissions_required": [],
    "version": "1.0.0",
    "tags": ["web", "search", "browser"]
}
```

## Backward Compatibility

- **Existing automation modules are NOT modified** — tool adapters import and delegate to them
- **Orchestrator is NOT rewritten** — `orch._tool_executor` is wired by `main.py` for future ToolRouter integration
- **GUI is unchanged** — buttons continue calling orchestator as before
- **VoiceEngine is unchanged** — voice pipeline operates independently
- **RuntimeSupervisor is unchanged** — ToolRegistry and ToolExecutor are registered as non-autostart components

## Start-up Sequence

```
main.py → initialize_runtime(orchestrator)
    │
    ├── RuntimeSupervisor()
    ├── Register orchestrator (autostart=false)
    ├── Create VoiceEngine → register (autostart=true)
    │
    ├── Create ToolRegistry
    ├── Create PermissionEvaluator (auto_approve_safe=true)
    ├── Create ToolExecutor(registry, evaluator, event_bus)
    │
    ├── Register 6 tool adapters:
    │   ├── BrowserTool        → tool_registry.register_tool()
    │   ├── ClipboardTool      → tool_registry.register_tool()
    │   ├── AppLauncherTool    → tool_registry.register_tool()
    │   ├── ScreenshotTool     → tool_registry.register_tool()
    │   ├── FileTool           → tool_registry.register_tool()
    │   └── SystemTool         → tool_registry.register_tool()
    │
    ├── Each registration also updates CapabilityRegistry:
    │   ├── tool.browser
    │   ├── tool.clipboard
    │   ├── tool.app_launcher
    │   ├── tool.screenshot
    │   ├── tool.file
    │   └── tool.system
    │
    ├── Register ToolRegistry (autostart=false)
    ├── Register ToolExecutor (autostart=false)
    ├── Wire orch._tool_executor = tool_executor
    │
    ├── Create CapabilityRegistry
    └── supervisor.start()
```

## Files

```
Created:
  runtime/tools/__init__.py     — Package exports
  runtime/tools/models.py       — ToolRequest, ToolResult, ToolMetadata
  runtime/tools/permissions.py  — RiskLevel, PermissionEvaluator
  runtime/tools/base_tool.py    — Abstract BaseTool
  runtime/tools/registry.py     — ToolRegistry (thread-safe)
  runtime/tools/executor.py     — ToolExecutor (full pipeline)
  runtime/tools/events.py       — Typed event classes
  runtime/tools/adapters.py     — 6 tool adapters
  tests/test_tool_runtime.py    — Test suite
  docs/tool_runtime_architecture.md — This document

Modified:
  runtime/__init__.py  — Added tool runtime exports
  main.py              — ToolRegistry + ToolExecutor created in create_runtime()
```

## Risks

1. **Tool adapters are thin wrappers** — No risk; they merely delegate to existing, tested automation modules.
2. **PermissionEvaluator blocks without handler** — Intentional fail-safe. Untrusted environments can register a handler for approval dialogs.
3. **ToolRegistry uses RLock** — Safe for concurrent access from Planner, GUI, and voice threads.
4. **No ToolRouter yet** — `orch._tool_executor` is wired but not yet used by the orchestrator. That's a Phase 4 integration.

## Recommended Next Phase (Phase 4)

1. **ToolRouter** — Route orchestrator intents through the tool executor
2. **Planner** — Register Planner as a managed component using ToolRegistry for tool discovery
3. **Awareness System** — Register AwarenessEngine, subscribe to screen/context events
4. **Active health probes** — Poll tool availability and auto-mark capabilities
5. **Async EventBus** — Layer async dispatch without changing event definitions