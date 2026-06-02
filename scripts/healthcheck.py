#!/usr/bin/env python3
"""
DREX — Startup Health Check & Verification Script

Runs before the main application starts to verify:
  - Python version compatibility
  - Critical dependencies installed
  - Environment file (.env) exists with keys
  - Database directory is writable
  - Microphone accessibility (warning only)
  - Configuration validity

Usage:
    python scripts/healthcheck.py           # Full check
    python scripts/healthcheck.py --minimal # Quick essential check only
    python scripts/healthcheck.py --json    # Output as JSON

Returns exit code 0 if healthy, 1 if critical issues found.
"""

import argparse
import json
import os
import platform
import sys
import importlib
from datetime import datetime


# ── Configuration ────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_PACKAGES = {
    "customtkinter": "GUI Framework",
    "PIL": "Image Support (Pillow)",
    "speech_recognition": "Speech-to-Text",
    "pyaudio": "Audio Capture",
    "groq": "Groq AI",
    "google.genai": "Gemini AI",
    "requests": "HTTP Client",
    "loguru": "Logging",
}

OPTIONAL_PACKAGES = {
    "webrtcvad": "Voice Activity Detection",
    "pvporcupine": "Wake Word (preferred)",
    "openwakeword": "Wake Word (fallback)",
    "edge_tts": "Neural TTS",
    "playsound": "Audio Playback",
    "pyttsx3": "Offline TTS",
    "cerebras.cloud.sdk": "Cerebras AI",
}

ENV_VARS = {
    "GEMINI_API_KEY": "Gemini AI",
    "GROQ_API_KEY": "Groq AI",
    "CEREBRAS_API_KEY": "Cerebras AI",
    "OPENROUTER_API_KEY": "OpenRouter AI",
}


class HealthCheck:
    """Performs system health checks and reports results."""

    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "checks": [],
            "passed": 0,
            "warnings": 0,
            "failures": 0,
        }

    def add(self, name: str, status: str, detail: str = ""):
        self.results["checks"].append({
            "name": name,
            "status": status,
            "detail": detail,
        })
        if status == "PASS":
            self.results["passed"] += 1
        elif status == "WARN":
            self.results["warnings"] += 1
        elif status == "FAIL":
            self.results["failures"] += 1

    def check_python_version(self):
        """Check Python version >= 3.9."""
        v = sys.version_info
        if v.major >= 3 and v.minor >= 9:
            self.add("Python Version", "PASS", f"{v.major}.{v.minor}.{v.micro}")
        else:
            self.add("Python Version", "FAIL",
                      f"Requires 3.9+, got {v.major}.{v.minor}")

    def check_environment_file(self):
        """Check .env file exists."""
        env_path = os.path.join(PROJECT_ROOT, ".env")
        if os.path.exists(env_path):
            self.add(".env file", "PASS", env_path)
        else:
            self.add(".env file", "FAIL",
                     "Missing! Copy .env.example to .env and add API keys")

    def check_api_keys(self):
        """Check required environment variables."""
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
        except Exception:
            pass

        configured = 0
        for var, label in ENV_VARS.items():
            val = os.getenv(var, "")
            if val and not val.startswith("your_") and len(val) > 8:
                configured += 1
                self.add(f"API: {label}", "PASS", f"{var} configured")
            else:
                self.add(f"API: {label}", "WARN",
                         f"{var} not set — {label} unavailable")

        if configured == 0:
            self.add("API Keys Summary", "FAIL",
                     "No AI providers configured — add API keys to .env")
        else:
            self.add("API Keys Summary", "PASS",
                     f"{configured}/{len(ENV_VARS)} configured")

    def check_packages(self, packages: dict, category: str):
        """Check if Python packages are installed."""
        for pkg, label in packages.items():
            try:
                mod = importlib.import_module(pkg)
                if hasattr(mod, "__version__"):
                    self.add(f"{label}", "PASS", f"{pkg} v{mod.__version__}")
                else:
                    self.add(f"{label}", "PASS", f"{pkg} installed")
            except ImportError:
                if category == "required":
                    self.add(f"{label}", "FAIL", f"{pkg} NOT INSTALLED")
                else:
                    self.add(f"{label}", "WARN", f"{pkg} not installed (optional)")

    def check_directories(self):
        """Check required data directories exist or can be created."""
        dirs = [
            ("logs", os.path.join(PROJECT_ROOT, "logs")),
            ("data", os.path.join(PROJECT_ROOT, "data")),
        ]
        for name, path in dirs:
            try:
                os.makedirs(path, exist_ok=True)
                if os.access(path, os.W_OK):
                    self.add(f"Directory: {name}", "PASS", path)
                else:
                    self.add(f"Directory: {name}", "FAIL",
                             f"{path} not writable")
            except Exception as e:
                self.add(f"Directory: {name}", "FAIL", str(e))

    def check_config(self):
        """Verify config loads correctly."""
        try:
            sys.path.insert(0, PROJECT_ROOT)
            from config import get_config
            cfg = get_config()
            self.add("Configuration", "PASS",
                     f"{cfg.app.name} v{cfg.app.version}")
            self.add("Default AI", "PASS", cfg.ai.default_provider)
            self.add("Wake Word", "PASS" if cfg.app.wake_word_enabled else "WARN",
                     f"'{cfg.app.wake_word}' (enabled={cfg.app.wake_word_enabled})")
            self.add("VAD", "PASS" if cfg.voice.vad_enabled else "WARN",
                     f"enabled={cfg.voice.vad_enabled}")
            self.add("TTS Engine", "PASS", cfg.voice.tts_engine)
        except Exception as e:
            self.add("Configuration", "FAIL", str(e))

    def check_microphone(self):
        """Check microphone availability (warning only)."""
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            count = pa.get_device_count()
            input_devices = 0
            for i in range(count):
                info = pa.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    input_devices += 1
            pa.terminate()
            if input_devices > 0:
                self.add("Microphone", "PASS",
                         f"{input_devices} input device(s) detected")
            else:
                self.add("Microphone", "WARN",
                         "No microphone input devices found")
        except ImportError:
            self.add("Microphone", "WARN", "pyaudio not installed")
        except Exception as e:
            self.add("Microphone", "WARN", str(e))

    def check_database(self):
        """Check database connectivity."""
        try:
            sys.path.insert(0, PROJECT_ROOT)
            from memory.db_manager import DBManager
            db = DBManager()
            count = db.get_session_count()
            facts = len(db.get_facts())
            db.close()
            self.add("Database", "PASS",
                     f"connected, {count} sessions, {facts} facts")
        except Exception as e:
            self.add("Database", "FAIL", str(e))

    def run_all(self, minimal: bool = False):
        """Run all health checks."""
        self.check_python_version()
        self.check_environment_file()
        self.check_api_keys()
        self.check_packages(REQUIRED_PACKAGES, "required")
        self.check_directories()
        self.check_config()

        if not minimal:
            self.check_packages(OPTIONAL_PACKAGES, "optional")
            self.check_microphone()
            self.check_database()

        return self.results

    def print_report(self, minimal: bool = False):
        """Print a readable health report."""
        results = self.run_all(minimal)
        width = 60

        print()
        print("=" * width)
        print("  DREX — Health Check Report")
        print(f"  {results['timestamp']}")
        print("=" * width)
        print()

        for check in results["checks"]:
            icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}.get(
                check["status"], "ℹ️"
            )
            name = check["name"]
            detail = check["detail"]
            if detail:
                print(f"  {icon} {name:<30} {detail}")
            else:
                print(f"  {icon} {name}")

        print()
        print(f"  Results: ✅ {results['passed']} passed | "
              f"⚠️  {results['warnings']} warnings | "
              f"❌ {results['failures']} failures")
        print()

        if results["failures"] > 0:
            print("  ❌ Critical issues found — fix before launching.")
            print()
            return False
        elif results["warnings"] > 0:
            print("  ⚠️  Non-critical warnings — DREX will run with limited features.")
            print()
            return True
        else:
            print("  ✅ All checks passed — DREX is ready!")
            print()
            return True

    def to_json(self) -> str:
        """Return results as JSON."""
        results = self.run_all(False)
        return json.dumps(results, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="DREX — Startup Health Check"
    )
    parser.add_argument("--minimal", action="store_true",
                        help="Quick essential check only")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    args = parser.parse_args()

    hc = HealthCheck()

    if args.json:
        print(hc.to_json())
        return 0

    healthy = hc.print_report(minimal=args.minimal)
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())