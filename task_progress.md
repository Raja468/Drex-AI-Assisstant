# DREX Phase 3 — Full Production Hardening

## Audit Findings (Pre-Fix)
- [x] .env has CEREBRAS_MODEL=llama3.3-70b (needs fix)
- [x] ai_router.py line 41 has CEREBRAS_LLAMA = "llama3.3-70b"
- [x] task_dispatcher.py duplicates orchestrator dispatch logic
- [x] db_manager.py uses unsafe check_same_thread=False
- [x] VAD exists but cfg.voice.vad_enabled defaults to False
- [x] Providers lack stream_chat() (except Cerebras)
- [x] Memory modules are stubs

## Priority 1 — Realtime Voice System (enable VAD, fix lifecycle)
- [ ] Fix VAD default: enable by default, proper wiring
- [ ] Add detailed voice lifecycle logging to listener
- [ ] Ensure microphone reconnect after failures
- [ ] Ensure daemon-safe thread management

## Priority 2 — Streaming AI Responses (all providers)
- [x] Add stream_chat() to GroqClient
- [x] Add stream_chat() to GeminiClient
- [x] Add stream_chat() to OpenRouterClient
- [x] Ensure orchestrator uses streaming path (generate_stream + GUI tokens)

## Priority 3 — Cerebras Model Fix (all references)
- [ ] Fix .env CEREBRAS_MODEL default
- [ ] Fix ai_router.py CEREBRAS_LLAMA reference
- [ ] Fix docs/PROJECT_REPORT.md references

## Priority 4 — SQLite Threading Fix
- [ ] Rewrite db_manager.py with WAL mode + thread-safe connection pool

## Priority 5 — Remove Duplicate Architecture
- [ ] Consolidate task_dispatcher.py into orchestrator dispatch
- [ ] Remove duplicate fallback logic in ai_router.py

## Priority 6 — Smart Memory Foundation
- [ ] Implement memory/context_builder.py
- [ ] Implement memory/conversation_store.py
- [ ] Implement memory/user_preferences.py

## Priority 7 — Tool Execution Intelligence
- [ ] Add timeout handling to automation
- [ ] Add confirmation system for dangerous ops
- [ ] Add operation tracking

## Priority 8 — Document Understanding
- [ ] Wire document_extractor into automation commands

## Priority 9 — Production Hardening
- [ ] Add retry logic throughout
- [ ] Add thread pool management
- [ ] Add resource cleanup

## Priority 10 — Launch Readiness
- [ ] Improve startup diagnostics
- [ ] Add dependency health checks