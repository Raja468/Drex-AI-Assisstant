# 🤖 DREX — AI Assistant Runtime

A production-ready, voice-first AI desktop assistant with realtime streaming, floating UI, and intelligent automation.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Production--Ready-success.svg)

---

## ✨ Features

### 🎯 Core Capabilities
- **Voice-First Interaction** — Natural speech input/output with wake word support
- **Realtime Streaming** — See AI responses stream token-by-token
- **Multi-Provider AI** — Gemini, Groq, OpenRouter, Cerebras with automatic fallback
- **Smart Automation** — Launch apps, control system, browse web, manage files
- **Document Intelligence** — PDF extraction, OCR, document Q&A
- **Memory System** — Conversation history, user preferences, context awareness

### 🆕 Assistant Runtime (New!)
- **Floating Orb** — Always-on-top quick access widget
- **Agent Panel** — Compact assistant panel for quick interactions
- **System Tray** — Background operation with tray icon
- **Global Hotkeys** — System-wide shortcuts (Ctrl+Space to activate)
- **Speech Interruption** — Interrupt DREX while speaking (barge-in)
- **Echo Cancellation** — Prevents DREX from hearing itself
- **Streaming TTS** — Audio plays while response generates
- **Clipboard Integration** — Ask DREX about clipboard content
- **App Awareness** — Context-aware responses based on active window

### 🎨 UI Features
- **Modern Dark Theme** — Glassmorphism-inspired design
- **Markdown Rendering** — Rich text with headers, bold, code blocks
- **Code Highlighting** — Syntax highlighting for Python, JS, JSON, Bash
- **Typing Indicators** — Visual feedback during AI processing
- **State Animations** — Orb changes color based on assistant state

---

## 🚀 Quick Start

### Requirements
- **Python 3.11+** (3.12 recommended)
- **Windows 10/11** (for full feature support)
- **Microphone** (for voice features)

### Installation

```bash
# Clone the repository
git clone https://github.com/Raja468/Drex-AI-Assisstant.git
cd drex

# Create virtual environment
py -3.12 -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env
```

### Configuration

Edit `.env` and add your API keys:

```env
# Required: At least one AI provider
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
CEREBRAS_API_KEY=your_key_here

# Optional: Wake word detection
PICOVOICE_API_KEY=your_key_here
```

### Running DREX

```bash
# Normal mode (GUI + Voice)
python main.py

# Text-only mode (no microphone)
python main.py --text

# Run diagnostics first
python main.py --test

# Debug mode with verbose logging
python main.py --debug
```

---

## 🎮 Usage

### Voice Commands

| Say This | What Happens |
|----------|--------------|
| "Hey DREX" | Wake word activation |
| "Open Chrome" | Launches Google Chrome |
| "Search for Python" | Web search |
| "What time is it?" | Tells the time |
| "Take a screenshot" | Saves screenshot |
| "Volume up/down" | Adjust system volume |
| "Summarize this PDF" | Document analysis |
| "What's in my clipboard?" | Clipboard Q&A |
| "Goodbye" | Shut down DREX |

### Global Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl+Space` | Toggle listening |
| `Ctrl+Shift+Space` | Push-to-talk |
| `Ctrl+Shift+D` | Show/hide DREX |
| `Ctrl+Shift+M` | Mute/unmute |
| `Ctrl+Shift+A` | Switch to Agent mode |
| `Ctrl+Shift+C` | Switch to Chat mode |

### Assistant Modes

**Agent Mode** (Default)
- Voice-first interaction
- Floating orb UI
- Continuous listening
- Realtime responses

**Chat Mode**
- Text-first interaction
- Full chat window
- Markdown support
- Long-form reasoning

---

## 📁 Project Structure

```
drex/
├── main.py                 # Entry point
├── config.py               # Configuration
├── .env                    # API keys (create from .env.example)
│
├── assistant/              # 🆕 Assistant Runtime Module
│   ├── state_engine.py     # State machine (IDLE, LISTENING, SPEAKING...)
│   ├── mode_manager.py     # Agent/Chat mode switching
│   ├── interruption_handler.py  # Speech interruption (barge-in)
│   ├── floating_orb.py     # Floating orb widget
│   ├── agent_panel.py      # Compact assistant panel
│   ├── system_tray.py      # System tray integration
│   ├── global_hotkey.py    # Global hotkey support
│   ├── echo_canceller.py   # Prevent self-hearing
│   ├── streaming_tts.py    # Streaming text-to-speech
│   ├── silence_detector.py # Advanced silence detection
│   ├── streaming_renderer.py # Smooth token rendering
│   ├── markdown_renderer.py  # Markdown in chat
│   ├── code_highlighter.py   # Syntax highlighting
│   ├── document_analyzer.py  # PDF/OCR analysis
│   ├── clipboard_manager.py  # Clipboard integration
│   └── app_awareness.py      # Active window detection
│
├── brain/                  # AI Provider Clients
│   ├── ai_router.py        # Provider routing & fallback
│   ├── gemini_client.py    # Google Gemini
│   ├── groq_client.py      # Groq (Llama)
│   ├── openrouter_client.py # OpenRouter
│   ├── cerebras_client.py  # Cerebras
│   └── base_client.py      # Base AI client class
│
├── core/                   # Core Orchestration
│   ├── orchestrator.py     # Master controller
│   ├── intent_parser.py    # Command understanding
│   └── task_dispatcher.py  # Task routing
│
├── voice/                  # Voice Pipeline
│   ├── listener.py         # Speech-to-text
│   ├── speaker.py          # Text-to-speech
│   ├── vad.py              # Voice activity detection
│   └── wake_word.py        # Wake word detection
│
├── memory/                 # Memory System
│   ├── db_manager.py       # SQLite database
│   ├── conversation_store.py # Chat history
│   ├── user_preferences.py # User settings
│   └── context_builder.py  # Context assembly
│
├── gui/                    # Desktop GUI
│   ├── app.py              # Main window
│   ├── chat_panel.py       # Chat display
│   ├── sidebar.py          # Navigation sidebar
│   ├── settings_modal.py   # Settings dialog
│   └── theme.py            # Theme configuration
│
├── automation/             # System Automation
│   ├── app_launcher.py     # Launch applications
│   ├── browser_control.py  # Web automation
│   ├── system_control.py   # System commands
│   └── file_manager.py     # File operations
│
└── utils/                  # Utilities
    ├── logger.py           # Logging system
    ├── document_extractor.py # PDF/OCR extraction
    └── error_handler.py    # Error management
```

---

## 🔧 Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test module
python -m pytest tests/test_ai_router.py

# Run with coverage
python -m pytest tests/ --cov=.
```

### Health Check

```bash
# Run diagnostics
python scripts/healthcheck.py

# Or via main.py
python main.py --test
```

### Installing Optional Dependencies

```bash
# Wake word detection
pip install pvporcupine

# Voice activity detection
pip install webrtcvad

# Document extraction
pip install pytesseract pymupdf python-docx
```

---

## 🌐 Web Deployment

DREX includes a FastAPI backend for web deployment:

```bash
# Run API server
uvicorn api.index:app --reload --port 8000

# Or for production
uvicorn api.index:app --host 0.0.0.0 --port 8000
```

See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for Vercel deployment instructions.

---

## 🐛 Troubleshooting

### Microphone Issues

```bash
# List available microphones
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
```

### PyAudio Installation (Windows)

```bash
# If pip install fails, use pipwin
pip install pipwin
pipwin install pyaudio

# Or download wheel from:
# https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
```

### Python Version Issues

```bash
# DREX requires Python 3.11+
# For Python 3.12:
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Check Everything

```bash
python main.py --test
```

---

## 📊 Status

| Component | Status |
|-----------|--------|
| Voice Pipeline | ✅ Production |
| AI Providers | ✅ Production |
| Streaming | ✅ Production |
| GUI | ✅ Production |
| Memory System | ✅ Production |
| Automation | ✅ Production |
| Assistant Runtime | ✅ Production |
| Web API | ✅ Production |

---

## 🗺️ Roadmap

- [x] Phase 1: Foundation (State Engine, Mode Manager)
- [x] Phase 2: Floating UI (Orb, Panel, Tray, Hotkeys)
- [x] Phase 3: Voice Hardening (Echo, Streaming TTS, Silence)
- [x] Phase 4: Streaming UX (Token Rendering)
- [x] Phase 5: Chat Enhancement (Markdown, Code, Documents)
- [x] Phase 6: OS Integration (Clipboard, App Awareness)
- [x] Phase 7: Polish & Launch

**Next:**
- [ ] PyInstaller packaging
- [ ] Installer generation
- [ ] Plugin system expansion
- [ ] Multi-language support

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- AI Providers: Google Gemini, Groq, OpenRouter, Cerebras
- TTS: edge-tts, pyttsx3
- UI: CustomTkinter
- Icons: Emoji icons from OpenMoji

---

**Built with ❤️ for the AI assistant community**