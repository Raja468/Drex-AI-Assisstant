# DREX — AI Desktop Assistant | Master Context Document
# Version: 3.0 | Last Updated: May 2026
# Copy this ENTIRE file and paste to any AI chatbot to instantly continue work

---

## Project Overview
Drex is a Python-based Jarvis-style AI desktop assistant for Windows.
- **Location:** D:\drex\
- **Python:** 3.11.6
- **Venv:** D:\drex\venv\ (activate: venv\Scripts\activate)
- **Status:** Core system working — GUI, voice, text, automation all functional
- **Current Sprint:** Phase 1 — Personality Engine, Long-Term Memory, Ollama, edge-tts

---

## How to Run
```powershell
cd D:\drex
venv\Scripts\activate
python main.py             # Normal GUI mode
python main.py --test      # Diagnostics (14/14 passing)
python main.py --text      # Text-only CLI
python main.py --no-voice  # GUI without voice
python main.py --debug     # Debug logging
```

---

## Tech Stack
| Component     | Technology                                      | Status        |
|---------------|-------------------------------------------------|---------------|
| GUI           | CustomTkinter 5.2.2                             | Working       |
| AI Provider 1 | Google Gemini 2.0 Flash (google-genai SDK)      | Working       |
| AI Provider 2 | Groq — Llama 3.3 70b versatile                  | Working       |
| AI Provider 3 | OpenRouter — GPT-4o-mini                        | Working       |
| Voice STT     | SpeechRecognition 3.16.1 + PyAudio              | Working       |
| Voice TTS     | pyttsx3 2.99 (offline)                          | Working       |
| Voice TTS 2   | edge-tts 7.2.8 (installed, not wired yet)       | Ready         |
| Memory        | SQLite3 via db_manager.py                       | Working       |
| Logging       | Loguru 0.7.3                                    | Working       |
| Config        | python-dotenv + dataclasses                     | Working       |
| Automation    | pyautogui, psutil, pygetwindow, subprocess      | Working       |

---

## Complete Folder Structure (exact, verified May 2026)
```
D:\drex\
├── main.py                          # Entry point — args, banner, validation, GUI/text launch
├── config.py                        # DrexConfig dataclass — AppConfig, VoiceConfig, AIConfig
├── .env                             # API keys
├── .gitignore
├── .python-version
├── requirements.txt                 # All packages locked
├── README.md
├── TODO.md
│
├── .vscode\
│   └── settings.json                # VS Code — venv auto-activate, formatter on save
│
├── brain\
│   ├── ai_router.py                 # Routes to Gemini/Groq/OpenRouter with fallback (WORKING)
│   ├── prompt_builder.py            # Builds system prompt + injects memory/facts (WORKING)
│   ├── gemini_client.py             # google-genai SDK client (WORKING)
│   ├── groq_client.py               # Groq SDK client (WORKING)
│   ├── openrouter_client.py         # OpenRouter via requests (WORKING)
│   ├── base_client.py               # Base class (minimal, exists)
│   └── __init__.py
│
├── core\
│   ├── orchestrator.py              # Central controller — wires all modules (WORKING)
│   ├── intent_parser.py             # Regex-based intent detection (WORKING)
│   ├── task_dispatcher.py           # Exists, not actively used
│   └── __init__.py
│
├── memory\
│   ├── db_manager.py                # SQLite CRUD — conversations, facts, preferences, sessions (WORKING)
│   ├── context_builder.py           # EMPTY — needs implementation
│   ├── conversation_store.py        # EMPTY — needs implementation
│   ├── user_preferences.py          # EMPTY — needs implementation
│   └── __init__.py
│
├── voice\
│   ├── listener.py                  # Mic + STT, continuous + single, Google + Sphinx fallback (WORKING)
│   ├── speaker.py                   # pyttsx3 TTS, threaded queue worker, markdown cleaner (WORKING)
│   ├── config.py                    # Voice config (exists)
│   ├── wake_word.py                 # EMPTY — needs implementation
│   └── __init__.py
│
├── automation\
│   ├── task_handler.py              # Routes all automation intents (WORKING)
│   ├── app_launcher.py              # Opens/closes apps via subprocess (WORKING)
│   ├── browser_control.py           # Opens URLs, searches, YouTube, maps (WORKING)
│   ├── system_control.py            # Volume, brightness, screenshot, lock, shutdown (WORKING)
│   ├── file_manager.py              # File find, open, create, delete (WORKING)
│   ├── clipboard_manager.py         # EMPTY
│   └── __init__.py
│
├── gui\
│   ├── app.py                       # Main CTk window, connects orchestrator (WORKING)
│   ├── chat_panel.py                # Chat bubbles UI (WORKING)
│   ├── sidebar.py                   # Navigation — Chat, Memory, Settings, Help (WORKING)
│   ├── input_bar.py                 # Text input + mic button (WORKING)
│   ├── settings_modal.py            # Settings panel (partial — save/load has errors)
│   ├── status_bar.py                # Top status bar (WORKING)
│   ├── theme.py                     # Colors, fonts, CTk theme (WORKING)
│   ├── widgets.py                   # Custom widgets (WORKING)
│   ├── assets\icons\                # Icons folder (empty)
│   └── __init__.py
│
├── plugins\
│   ├── plugin_base.py               # EMPTY — base class needed
│   ├── plugin_loader.py             # EMPTY — loader needed
│   ├── built_in\
│   │   ├── calculator_plugin.py     # EXISTS (not tested)
│   │   ├── news_plugin.py           # EXISTS (not tested)
│   │   └── weather_plugin.py        # EXISTS (not tested)
│   └── __init__.py
│
├── utils\
│   ├── logger.py                    # Loguru setup — console + file (WORKING)
│   ├── error_handler.py             # safe_execute decorator (WORKING)
│   ├── helpers.py                   # EMPTY
│   ├── validators.py                # EMPTY
│   └── __init__.py
│
├── tests\
│   ├── test_ai_router.py            # EXISTS (not verified)
│   ├── test_ai_router_status.py     # EXISTS (not verified)
│   ├── test_automation.py           # EXISTS (not verified)
│   ├── test_memory.py               # EXISTS (not verified)
│   └── test_voice.py                # EXISTS (not verified)
│
├── docs\
│   ├── api_setup.md
│   ├── architecture.md
│   └── roadmap.md
│
├── data\
│   └── drex_memory.db               # SQLite database (auto-created on first run)
│
├── logs\
│   ├── drex.log
│   └── drex_errors.log
│
└── screenshots\                     # Empty
```

---

## .env Keys
```
GEMINI_API_KEY
GROQ_API_KEY
OPENROUTER_API_KEY
DREX_NAME
DREX_DEBUG_MODE
DREX_LOG_LEVEL
STT_ENGINE
TTS_ENGINE
TTS_SPEED
DEFAULT_AI
FAST_AI
```

---

## Database Schema (data/drex_memory.db)
```sql
conversations (id, session_id, role, content, timestamp, metadata)
preferences   (key, value, updated_at)
facts         (id, category, key, value, confidence, created_at)
sessions      (id, started_at, ended_at, summary)
```

---

## Key Classes & Methods

### config.py
```python
get_config() -> DrexConfig
DrexConfig.app    # AppConfig: name, version, debug, db_path, wake_word,
                  #            voice_enabled, theme, window_width, window_height
DrexConfig.voice  # VoiceConfig: rate, volume, voice_index, language,
                  #              energy_threshold, pause_threshold, timeout
DrexConfig.ai     # AIConfig: default_provider, gemini/groq/openrouter keys+models,
                  #           max_tokens, temperature, max_history
```

### core/orchestrator.py
```python
orchestrator.process(user_input, voice_response=None) -> str
orchestrator.start_voice_listening()
orchestrator.stop_voice_listening()
orchestrator.listen_once() -> str
orchestrator.switch_ai_provider(name)    # gemini / groq / openrouter
orchestrator.get_ai_status() -> dict
orchestrator.set_voice_mode(enabled)
orchestrator.get_session_info() -> dict
orchestrator.register_response_callback(fn)
orchestrator.register_status_callback(fn)
orchestrator.shutdown()
```

### memory/db_manager.py
```python
db.save_message(session_id, role, content, metadata)
db.get_history(session_id, limit) -> list[dict]
db.get_recent_context(session_id, limit) -> list[dict]
db.search_history(query, limit) -> list[dict]
db.set_preference(key, value)
db.get_preference(key, default) -> any
db.get_all_preferences() -> dict
db.save_fact(category, key, value, confidence)
db.get_facts(category=None) -> list[dict]
db.get_fact(category, key) -> str
db.start_session(session_id)
db.end_session(session_id, summary)
db.get_session_count() -> int
```

### core/intent_parser.py
```python
# Intent.type values:
"open_app", "close_app", "system_control", "browser",
"file_manager", "memory", "small_talk", "media",
"weather", "time_date", "ai_query"

# Intent fields:
intent.type, intent.action, intent.target, intent.params, intent.raw

# Methods:
parser.parse(text) -> Intent
parser.is_automation(intent) -> bool
parser.is_ai_query(intent) -> bool
parser.is_memory_op(intent) -> bool
parser.requires_confirmation(intent) -> bool
```

### brain/prompt_builder.py
```python
prompt_builder.build(user_input, session_id, task_type, extra_context) -> dict
# Returns: {"system": "...", "messages": [...]}
# task_type options: "general", "coding", "creative", "reasoning", "fast"
prompt_builder.build_simple(user_input, task_type) -> dict
prompt_builder.extract_facts_from_response(user_input, response) -> list
# NOTE: extract_facts_from_response always returns [] — not implemented yet
```

### automation/task_handler.py
```python
handler.execute(intent) -> str    # Main entry (alias for handle)
handler.handle(intent) -> str
handler.handle_system_action(sub_type, intent) -> str
```

---

## Known Issues / Bug Tracker
| # | Issue | Status |
|---|-------|--------|
| 1 | Voice mic button not working | ✅ FIXED |
| 2 | Memory panel SQL error (no column 'key') | ✅ FIXED |
| 3 | DBManager missing 'preferences' attribute | ✅ FIXED |
| 4 | orchestrator start/stop_voice_listening missing | ✅ FIXED |
| 5 | settings_modal save/load errors | 🔴 Open |
| 6 | context_builder.py empty | 🔴 Open |
| 7 | conversation_store.py empty | 🔴 Open |
| 8 | user_preferences.py empty | 🔴 Open |
| 9 | wake_word.py empty | 🔴 Open |
| 10 | plugin_base.py / plugin_loader.py empty | 🔴 Open |
| 11 | extract_facts_from_response() always returns [] | 🔴 Open |
| 12 | edge-tts installed but not wired to speaker | 🔴 Open |
| 13 | clipboard_manager.py empty | 🔴 Open |
| 14 | helpers.py / validators.py empty | 🔴 Open |
| 15 | plugins built_in files not tested | ⚠️ Unknown |

---

## Phase 1 Goals (Current Sprint)
1. **Personality Engine** — Jarvis/Hacker/Professional/Calm modes
2. **Long-Term Memory** — implement context_builder.py + conversation_store.py
3. **Ollama Offline Mode** — add brain/ollama_client.py
4. **edge-tts integration** — wire edge-tts into voice/speaker.py

## Phase 2 Goals (Next Sprint)
1. Multi-Agent Team System
2. Autonomous Coding Mode
3. Project Awareness System
4. Proactive AI suggestions
5. Wake word detection

## Phase 3 Goals (Future)
1. AI Computer Vision
2. Self-Improving AI
3. Emotion/Context Awareness
4. AI Cybersecurity Assistant
5. Hybrid Cloud + Local Intelligence

---

## Coding Rules — MUST FOLLOW
1. **Always provide COMPLETE file content** — never partial snippets
2. **4-space indentation strictly** — #1 cause of errors
3. All new modules must:
   - Import loguru logger
   - Use get_config() for settings
   - Log: logger.info("✅ ModuleName initialized")
4. New AI clients → brain\
5. New automation → automation\
6. Config values → config.py / .env only, never hardcoded
7. Never hardcode API keys
8. When fixing a bug → only change what is broken

---

## Standard Module Template
```python
# folder/module_name.py
from loguru import logger
from config import get_config


class ModuleName:
    def __init__(self):
        self.cfg = get_config()
        logger.info("✅ ModuleName initialized")

    def some_method(self):
        pass
```

---

## Instructions for AI Assistant
You are helping Raja build Drex — a Jarvis-style agentic AI desktop assistant for Windows.

Rules:
- Always give COMPLETE file contents — never say "add this snippet"
- Follow 4-space Python indentation strictly
- Follow the exact folder structure above
- Raja is an intermediate Python developer — brief explanations only
- Current sprint is Phase 1 — focus on those 4 goals
- When Raja says "implement X" — write the full ready-to-use file
- When updating master context — keep ALL sections, only update what changed