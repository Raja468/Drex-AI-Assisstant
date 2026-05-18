# 🤖 Drex — AI Desktop Assistant

A production-level voice-controlled AI desktop assistant for Windows.

## ✨ Features (Phase 1)
- 🎤 Voice input (speech-to-text)
- 🔊 Voice output (text-to-speech)
- 🧠 Intent parsing (understands what you want)
- 🖥️ App launching and system control
- 🌐 Web search via voice
- 💬 Text-mode fallback

## 🚀 Quick Start

### Python version
Use Python `3.12.x` for this project.

The current voice stack in Drex is not compatible with Python `3.13+`.

### 1. Clone / Download the project
```bash
cd drex
```

### 2. Create a virtual environment
```bash
py -3.12 -m venv venv
venv\Scripts\activate        # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

> **Note:** If `pyaudio` fails, download the wheel from:
> https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
> Then: `pip install PyAudio‑0.2.14‑cp311‑cp311‑win_amd64.whl`

### 4. Add API keys
Open `.env` and add your API keys.

### 5. Run Drex
```bash
python main.py               # Normal mode
python main.py --text        # Text-only (no microphone needed)
python main.py --test        # Run diagnostics first
python main.py --debug       # Debug mode
```

## 🗣️ Voice Commands (Phase 1)

| Say This              | What Happens                  |
|-----------------------|-------------------------------|
| "Open Chrome"         | Opens Google Chrome           |
| "Search for Python"   | Googles "Python"              |
| "What time is it?"    | Tells you the time            |
| "Take a screenshot"   | Saves a screenshot            |
| "Volume up"           | Increases system volume       |
| "Close Notepad"       | Closes Notepad                |
| "Help"                | Lists available commands      |
| "Goodbye"             | Shuts down Drex               |

## 📁 Project Structure
```
drex/
├── main.py              ← Start here
├── config.py            ← All settings
├── .env                 ← Your API keys
├── core/
│   ├── orchestrator.py  ← Master controller
│   └── intent_parser.py ← Understands commands
├── voice/
│   ├── listener.py      ← Microphone → text
│   └── speaker.py       ← Text → speech
└── utils/
    ├── logger.py         ← Logging system
    └── error_handler.py  ← Error management
```

## 🔧 Development Phases

- ✅ **Phase 1** — Voice system + basic commands (this file)
- 🔜 **Phase 2** — Full automation module
- 🔜 **Phase 3** — AI integration (Gemini, Groq, OpenRouter)
- 🔜 **Phase 4** — GUI with CustomTkinter
- 🔜 **Phase 5** — Plugins, memory, wake word

## 🐛 Troubleshooting

**Microphone not working?**
```bash
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
```

**pyaudio install fails?**
```bash
pip install pipwin
pipwin install pyaudio
```

**"No module found" errors?**
```bash
pip install -r requirements.txt --upgrade
```

**Python 3.13 error like `No module named 'aifc'`?**
```bash
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Check everything is working:**
```bash
python main.py --test
```
