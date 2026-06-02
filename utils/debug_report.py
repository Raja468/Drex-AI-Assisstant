"""
debug_report.py — DREX Diagnostics & Debugging Report

Generates a comprehensive system diagnostics report covering:
  - Python environment
  - Dependencies
  - AI provider configuration
  - Microphone / audio
  - Database
  - Threading
  - Configuration
  - Streaming
  - Wake word / VAD
  - Environment validation

Outputs a clean, readable, professional report.

Usage:
    python -m utils.debug_report
    python main.py --test  (also runs diagnostics)
"""

import os
import sys
import time
import platform
import importlib
import subprocess
from datetime import datetime
from typing import Any, Callable


# ─────────────────────────────────────────────────────────────
#  REPORTING HELPERS
# ─────────────────────────────────────────────────────────────

class Section:
    """Diagnostics section builder."""

    def __init__(self, title: str):
        self.title = title
        self.checks: list[tuple[str, str]] = []

    def add(self, name: str, status: str):
        self.checks.append((name, status))

    def ok(self, name: str, detail: str = "OK"):
        self.add(name, f"✅ {detail}")

    def warn(self, name: str, detail: str):
        self.add(name, f"⚠️  {detail}")

    def fail(self, name: str, detail: str):
        self.add(name, f"❌ {detail}")

    def info(self, name: str, detail: str):
        self.add(name, f"ℹ️  {detail}")


def print_report(sections: list[Section]):
    """Print a formatted diagnostic report."""
    width = 72
    print()
    print("=" * width)
    print("  DREX — DIAGNOSTICS REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Platform:  {platform.platform()}")
    print(f"  Python:    {sys.version.split()[0]}")
    print("=" * width)
    print()

    for section in sections:
        if not section.checks:
            continue

        print(f"  [{section.title}]")
        print(f"  {'─' * (len(section.title) + 4)}")

        for name, status in section.checks:
            print(f"    {name:<30} {status}")

        print()

    total = sum(len(s.checks) for s in sections)
    passed = sum(
        1 for s in sections for _, st in s.checks
        if "✅" in st or "ℹ️" in st
    )
    warnings = sum(
        1 for s in sections for _, st in s.checks if "⚠️" in st
    )
    failures = sum(
        1 for s in sections for _, st in s.checks if "❌" in st
    )

    print(f"  {'─' * width}")
    print(f"  TOTAL: {total} checks  |  ✅ {passed} passed  |  "
          f"⚠️  {warnings} warnings  |  ❌ {failures} failures")

    if failures > 0:
        print(f"\n  ❌ {failures} FAILURES DETECTED — review above for details.")

    print()


# ─────────────────────────────────────────────────────────────
#  DIAGNOSTIC CHECKS
# ─────────────────────────────────────────────────────────────

def check_dependencies() -> Section:
    """Check required Python packages."""
    section = Section("Dependencies")

    required = [
        ("customtkinter", "GUI framework"),
        ("PIL", "Image support (Pillow)"),
        ("speech_recognition", "Speech-to-text"),
        ("pyaudio", "Audio capture"),
        ("groq", "Groq AI client"),
        ("google.genai", "Gemini AI client"),
        ("requests", "HTTP client"),
        ("python-dotenv", "Environment loader"),
        ("loguru", "Logging"),
        ("cerebras.cloud.sdk", "")  # Conditional
    ]

    for pkg, desc in required:
        try:
            importlib.import_module(pkg)
            section.ok(pkg, f"installed{f' — {desc}' if desc else ''}")
        except ImportError:
            if pkg == "cerebras.cloud.sdk":
                section.warn(pkg, "not installed (optional)")
            else:
                section.fail(pkg, f"MISSING — {desc}")

    # Check optional packages
    optional = [
        ("webrtcvad", "Voice activity detection"),
        ("pvporcupine", "Wake word (preferred)"),
        ("openwakeword", "Wake word (fallback)"),
        ("edge_tts", "Neural TTS"),
        ("playsound", "Audio playback"),
        ("pyttsx3", "Offline TTS"),
    ]
    for pkg, desc in optional:
        try:
            importlib.import_module(pkg)
            section.ok(pkg, f"installed ({desc})")
        except ImportError:
            section.warn(pkg, f"not installed ({desc} — optional)")

    return section


def check_providers() -> Section:
    """Check AI provider configuration."""
    section = Section("AI Providers")

    try:
        from config import get_config
        cfg = get_config()

        providers = {
            "Gemini":    ("gemini_api_key", "gemini_model", cfg.ai.gemini_api_key, cfg.ai.gemini_model),
            "Groq":      ("groq_api_key", "groq_model", cfg.ai.groq_api_key, cfg.ai.groq_model),
            "OpenRouter": ("openrouter_api_key", "openrouter_model", cfg.ai.openrouter_api_key, cfg.ai.openrouter_model),
            "Cerebras":  ("cerebras_api_key", "cerebras_model", cfg.ai.cerebras_api_key, cfg.ai.cerebras_model),
        }

        configured_count = 0
        for name, (key_name, model_key, key_val, model_val) in providers.items():
            if key_val:
                configured_count += 1
                section.ok(name, f"configured | model={model_val}")
            else:
                section.warn(name, f"NOT configured — set {key_name} in .env")

        section.info("Default provider", cfg.ai.default_provider)
        section.info("Temperature", str(cfg.ai.temperature))
        section.info("Max tokens", str(cfg.ai.max_tokens))

        # Try actually importing the clients
        from brain.ai_router import AIRouter
        router = AIRouter()
        status = router.get_status()
        section.info("Available providers", f"{status['available_count']}/4")
        for pname, info in status["providers"].items():
            if info["available"]:
                section.ok(f"  {pname}", "online")
            elif info["configured"]:
                section.warn(f"  {pname}", "configured but init failed")
            else:
                section.warn(f"  {pname}", "not configured")

    except Exception as e:
        section.fail("Provider check", str(e))

    return section


def check_microphone() -> Section:
    """Check microphone availability."""
    section = Section("Microphone & Audio")

    # Check speech_recognition mic access
    try:
        import speech_recognition as sr
        mics = sr.Microphone.list_microphone_names()
        if mics:
            section.ok("Microphones", f"{len(mics)} detected")
            for i, m in enumerate(mics[:3]):
                section.info(f"  Mic {i}", m)
            if len(mics) > 3:
                section.info(f"  ...", f"{len(mics) - 3} more")
        else:
            section.warn("Microphones", "none detected by speech_recognition")
    except Exception as e:
        section.fail("Microphone check", str(e))

    # Check pyaudio
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        host_count = pa.get_host_api_count()
        dev_count = pa.get_device_count()
        section.ok("PyAudio", f"{dev_count} devices, {host_count} host APIs")
        pa.terminate()
    except Exception as e:
        section.fail("PyAudio", str(e))

    # Check TTS
    try:
        from voice.speaker import Speaker
        sp = Speaker()
        if sp.is_available:
            section.ok("TTS (Speaker)", "available")
        else:
            section.warn("TTS (Speaker)", "not available")
    except Exception as e:
        section.warn("TTS (Speaker)", str(e))

    return section


def check_config() -> Section:
    """Check configuration consistency."""
    section = Section("Configuration")

    try:
        from config import get_config
        cfg = get_config()

        # Verify critical settings
        section.info("App name", cfg.app.name)
        section.info("Version", cfg.app.version)
        section.info("Log level", cfg.app.log_level)
        section.info("Log file", cfg.app.log_file)
        section.info("DB path", cfg.app.db_path)
        section.info("Theme", cfg.app.theme)
        section.info("Personality", cfg.app.personality)

        # Verify VAD setting
        if cfg.voice.vad_enabled:
            section.ok("VAD enabled", "Voice Activity Detection is ON")
        else:
            section.warn("VAD enabled", "Voice Activity Detection is OFF")

        # Verify wake word setting
        if cfg.app.wake_word_enabled:
            section.ok("Wake word", f"'{cfg.app.wake_word}' (enabled)")
        else:
            section.info("Wake word", "disabled")

        # Verify TTS engine
        section.info("TTS engine", cfg.voice.tts_engine)
        section.info("STT engine", "google (speech_recognition)")

        # Check for consistency between env and config
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_file):
            section.ok(".env file", "present")
        else:
            section.warn(".env file", "MISSING — create from .env.example")

    except Exception as e:
        section.fail("Config load", str(e))

    return section


def check_threads() -> Section:
    """Check running threads."""
    section = Section("Threading")

    try:
        import threading
        main_thread = threading.main_thread()
        all_threads = threading.enumerate()

        section.info("Total threads", str(len(all_threads)))
        section.info("Main thread", main_thread.name)

        # Look for DREX threads
        drex_threads = [t for t in all_threads if "drex" in t.name.lower()]
        if drex_threads:
            for t in drex_threads:
                daemon = "daemon" if t.daemon else "foreground"
                alive = "alive" if t.is_alive() else "dead"
                section.ok(f"  {t.name}", f"{alive} ({daemon})")
        else:
            section.info("DREX threads", "none active (not started yet)")

    except Exception as e:
        section.fail("Thread check", str(e))

    return section


def check_database() -> Section:
    """Check database connectivity."""
    section = Section("Database")

    try:
        from memory.db_manager import DBManager
        db = DBManager()

        # Check sessions
        session_count = db.get_session_count()
        section.ok("DB connection", "connected")
        section.info("Sessions", str(session_count))

        # Check facts stored
        facts = db.get_facts()
        section.info("Facts stored", str(len(facts)))

        db.close()
        section.ok("DB close", "clean")

    except Exception as e:
        section.fail("Database", str(e))

    return section


def check_streaming() -> Section:
    """Check streaming infrastructure."""
    section = Section("Streaming")

    try:
        from brain.base_client import BaseAIClient, StreamCallback
        # Verify that stream_chat method exists on clients
        from brain.gemini_client import GeminiClient
        from brain.groq_client import GroqClient
        from brain.openrouter_client import OpenRouterClient
        from brain.cerebras_client import CerebrasClient

        clients = [
            ("Gemini", GeminiClient),
            ("Groq", GroqClient),
            ("OpenRouter", OpenRouterClient),
            ("Cerebras", CerebrasClient),
        ]

        for name, cls in clients:
            try:
                instance = cls()
                if instance.is_available:
                    if hasattr(instance, "stream_chat"):
                        section.ok(f"  {name}", "stream_chat available")
                    else:
                        section.warn(f"  {name}", "no stream_chat method")
                else:
                    section.info(f"  {name}", "not configured — skip streaming check")
            except Exception as e:
                section.warn(f"  {name}", str(e))

    except Exception as e:
        section.fail("Streaming infrastructure", str(e))

    return section


def check_wake_word() -> Section:
    """Check wake word detection."""
    section = Section("Wake Word & VAD")

    try:
        # Check VAD
        try:
            import webrtcvad
            vad = webrtcvad.Vad(1)
            section.ok("WebRTC VAD", "available (mode=1)")
        except ImportError:
            section.warn("WebRTC VAD", "not installed — pip install webrtcvad")

        # Wake word detectors
        try:
            import pvporcupine
            section.ok("Porcupine", "installed (preferred wake word)")
        except ImportError:
            section.warn("Porcupine", "not installed")

        try:
            import openwakeword
            section.ok("OpenWakeWord", "installed (fallback)")
        except ImportError:
            pass  # Not required

        # Check config integration
        from config import get_config
        cfg = get_config()

        if cfg.voice.vad_enabled:
            section.ok("VAD in config", "enabled")
        else:
            section.warn("VAD in config", "disabled")

        section.info("VAD mode", str(cfg.voice.vad_mode))
        section.info("VAD silence", f"{cfg.voice.vad_silence_duration}s")
        section.info("Wake sensitivity", str(cfg.app.wake_word_sensitivity))

    except Exception as e:
        section.fail("Wake word/VAD check", str(e))

    return section


def check_environment() -> Section:
    """Check environment variables and paths."""
    section = Section("Environment")

    required_vars = [
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "CEREBRAS_API_KEY",
    ]

    set_count = 0
    for var in required_vars:
        val = os.getenv(var, "")
        if val and val not in ("your_key_here", "your_gemini_key_here", ""):
            set_count += 1
            section.ok(var, f"set ({'*' * min(len(val)-4, 20)}{val[-4:]})")
        else:
            section.warn(var, "NOT set — add to .env")

    section.info("API keys configured", f"{set_count}/{len(required_vars)}")

    # Check critical paths
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = {
        ".env": os.path.join(root, ".env"),
        "logs": os.path.join(root, "logs"),
        "data": os.path.join(root, "data"),
    }
    for name, p in paths.items():
        if os.path.exists(p):
            section.ok(f"Path: {name}", p)
        else:
            section.warn(f"Path: {name}", f"MISSING — {p}")

    # Virtual env check
    venv = os.environ.get("VIRTUAL_ENV", "")
    if venv:
        section.ok("Virtual env", os.path.basename(venv))
    else:
        section.info("Virtual env", "none detected")

    return section


# ─────────────────────────────────────────────────────────────
#  MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────

def run_all_checks() -> list[Section]:
    """Run all diagnostic checks and return sections."""
    sections = [
        check_environment(),
        check_config(),
        check_dependencies(),
        check_providers(),
        check_microphone(),
        check_database(),
        check_threads(),
        check_streaming(),
        check_wake_word(),
    ]
    return sections


def main():
    """Run the full debug report."""
    sections = run_all_checks()
    print_report(sections)
    return sections


if __name__ == "__main__":
    # Add project root to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    main()