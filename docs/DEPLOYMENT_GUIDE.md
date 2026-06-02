# DREX Deployment Guide

## Overview

DREX is primarily a **desktop AI assistant** with an optional **SaaS web API** tier. This guide covers both deployment targets.

---

## Desktop Deployment

### Requirements

- **Windows 10/11** (primary target)
- **Python 3.9–3.12**
- **Microphone** (for voice features)
- **4GB+ RAM** recommended

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Raja468/Drex-AI-Assisstant.git
cd drex

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API keys
copy .env.example .env
# Edit .env with your API keys (at minimum, GEMINI_API_KEY)

# 5. Install optional dependencies (recommended)
python scripts/install_optional.py --all

# 6. Run health check
python scripts/healthcheck.py

# 7. Launch DREX
python main.py
```

### Command-Line Options

| Flag | Description |
|------|-------------|
| `--text` | Text-only CLI mode (no GUI) |
| `--debug` | Enable debug logging |
| `--test` | Run diagnostics |
| `--no-voice` | GUI without voice features |

### Building Executable (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "Drex" main.py
```

---

## Web / SaaS Deployment (Vercel)

### Architecture

```
Vercel (Edge Network)
    │
    ├── https://drex.vercel.app/   → FastAPI (api/index.py)
    │       └── Serves modern web UI with chat interface
    │
    ├── /api/chat                  → AI chat endpoint (POST)
    ├── /api/providers             → List available providers (GET)
    ├── /api/switch_provider       → Switch AI provider (POST)
    └── /health                    → Health check (GET)
```

### Deployment Steps

1. **Fork/clone to GitHub**

2. **Connect to Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Import your GitHub repository
   - Framework preset: **Other**
   - Root directory: `./`
   - Build command: *(leave empty)*
   - Output directory: *(leave empty)*

3. **Environment Variables**
   
   Add these in Vercel dashboard → Settings → Environment Variables:
   
   | Variable | Value |
   |----------|-------|
   | `GEMINI_API_KEY` | Your Gemini API key |
   | `GROQ_API_KEY` | Your Groq API key |
   | `OPENROUTER_API_KEY` | Your OpenRouter key |
   | `CEREBRAS_API_KEY` | Your Cerebras key |
   | `DREX_LOG_LEVEL` | `WARNING` (production) |
   | `DREX_GUI_ENABLED` | `false` |
   | `DREX_VOICE_ENABLED` | `false` |

4. **Deploy**
   - Vercel auto-detects `vercel.json`
   - Serverless function at `api/index.py`
   - Web UI served at root `/`

### Troubleshooting Web Deployment

**Issue: Blank page / Raw JSON**
- Check that `vercel.json` routes `/(.*)` to `api/index.py`
- Ensure you set environment variables in Vercel dashboard
- The root `/` returns HTML — `/api/*` returns JSON

**Issue: API returns 500**
- Check Vercel function logs
- Ensure all required environment variables are set
- The orchestrator lazy-loads — timeout may be an issue on cold starts
- Consider increasing Vercel function timeout (max 60s on Pro)

---

## Configuration Reference

All configuration is in `.env` file or environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `GROQ_API_KEY` | — | Groq API key |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `CEREBRAS_API_KEY` | — | Cerebras API key |
| `DEFAULT_AI` | `gemini` | Primary AI provider |
| `TTS_ENGINE` | `edge` | Text-to-speech engine |
| `DREX_VAD_ENABLED` | `true` | Voice Activity Detection |
| `DREX_WAKE_WORD` | `hey drex` | Wake word phrase |
| `DREX_LOG_LEVEL` | `INFO` | Logging verbosity |
| `DREX_PERSONALITY` | `jarvis` | Assistant personality |

---

## Health Check

```bash
# Quick startup validation
python scripts/healthcheck.py

# Full diagnostics report
python -m utils.debug_report

# Or use the built-in test mode
python main.py --test
```

---

## Project Verification

```bash
# 1. Verify all imports
python -c "from config import get_config; from brain.ai_router import AIRouter; from core.orchestrator import Orchestrator; print('OK')"

# 2. Quick AI test
python main.py --text

# 3. Database check
python -c "from memory.db_manager import DBManager; db=DBManager(); print(f'Sessions: {db.get_session_count()}'); db.close()"

# 4. Run all tests
python -m pytest tests/
```

## Production Checklist

- [ ] All 4 AI providers configured (or at least Gemini)
- [ ] `.env` contains valid API keys
- [ ] `python scripts/healthcheck.py` passes
- [ ] Microphone accessible (for voice features)
- [ ] Optional deps installed: `python scripts/install_optional.py`
- [ ] Logs directory writable
- [ ] Data directory writable
- [ ] VAD + wake word tested (if using voice)
- [ ] TTS engine tested (edge or pyttsx3)
- [ ] Streaming responses working
- [ ] Graceful shutdown works
- [ ] For web: Vercel env vars set, deployed successfully