#!/usr/bin/env python3
"""DREX - AI Desktop Assistant | main entry point"""
import sys
import argparse
import os
from dotenv import load_dotenv


load_dotenv()

if sys.version_info < (3, 9):
    print("Requires Python 3.9+")
    sys.exit(1)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)
os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)


def parse_args():
    p = argparse.ArgumentParser(description="DREX AI Desktop Assistant")
    p.add_argument("--text",     action="store_true", help="Text-only CLI mode")
    p.add_argument("--debug",    action="store_true", help="Debug logging")
    p.add_argument("--test",     action="store_true", help="Run diagnostics")
    p.add_argument("--no-voice", action="store_true", help="GUI without voice")
    return p.parse_args()


def print_banner():
    print("""
╔══════════════════════════════════════════════════╗
║        ◈  DREX - AI Desktop Assistant           ║
║   Voice  •  Automation  •  AI  •  Memory        ║
╚══════════════════════════════════════════════════╝""")


def validate_config():
    warnings = []
    try:
        from config import get_config
        cfg = get_config()
        ai = cfg.ai
        if not ai.gemini_api_key or ai.gemini_api_key == "your_gemini_key_here":
            warnings.append("  ⚠  GEMINI_API_KEY not set in .env")
        if not ai.groq_api_key or ai.groq_api_key == "your_groq_key_here":
            warnings.append("  ⚠  GROQ_API_KEY not set in .env")
        if not ai.openrouter_api_key or ai.openrouter_api_key == "your_openrouter_key_here":
            warnings.append("  ⚠  OPENROUTER_API_KEY not set in .env")
        if len(warnings) == 3:
            warnings.append("  ✖  No AI provider configured — needs at least one API key!")
    except Exception as e:
        warnings.append(f"  ✖  Config error: {e}")
    return warnings


def run_text_loop(orchestrator):
    print("\n💬 TEXT MODE — type 'quit' to exit\n")
    while True:
        try:
            text = input("👤 You: ").strip()
            if not text:
                continue
            if text.lower() in ("quit", "exit", "q"):
                orchestrator.shutdown()
                break
            response = orchestrator.process(text, voice_response=False)
            print(f"🤖 DREX: {response}\n")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            orchestrator.shutdown()
            break


def run_gui(orchestrator, auto_voice=True):
    try:
        from gui.app import DrexApp
    except ImportError as e:
        print(f"\n⚠  GUI unavailable: {e}")
        print("Falling back to text mode.\n")
        run_text_loop(orchestrator)
        return

    app = DrexApp(orchestrator=orchestrator)

    def show_welcome():
        try:
            from config import get_config
            cfg = get_config()
            name = orchestrator._user_name or ""
            greeting = (
                f"Hello{', ' + name if name else ''}! "
                f"I'm {cfg.app.name}, your AI desktop assistant. "
                f"How can I help you today?"
            )
            if hasattr(app, "add_message"):
                app.add_message("assistant", greeting)
        except Exception:
            pass

    app.after(400, show_welcome)
    app.run()


def run_test():
    print("\n🧪 Running diagnostics...\n")
    results = []
    cfg = __import__("config").get_config()
    checks = [
        ("Python",        lambda: sys.version.split()[0]),
        ("Config",        lambda: cfg and "OK"),
        ("IntentParser",  lambda: __import__("core.intent_parser", fromlist=["x"]).IntentParser() and "OK"),
        ("DBManager",     lambda: __import__("memory.db_manager", fromlist=["x"]).DBManager().close() or "OK"),
        ("PromptBuilder", lambda: __import__("brain.prompt_builder", fromlist=["x"]).PromptBuilder() and "OK"),
        ("AIRouter",      lambda: str(__import__("brain.ai_router", fromlist=["x"]).AIRouter().get_status())),
        ("Speaker",       lambda: "OK" if __import__("voice.speaker", fromlist=["x"]).Speaker().is_available else "No TTS"),
        ("Listener",      lambda: "OK" if __import__("voice.listener", fromlist=["x"]).Listener().is_available else "No mic"),
        ("CustomTkinter", lambda: __import__("customtkinter") and "OK"),
        ("PyAudio",       lambda: __import__("pyaudio") and "OK"),
        ("SpeechRecog.",  lambda: __import__("speech_recognition") and "OK"),
        ("Gemini SDK",    lambda: __import__("google.genai") and "OK"),
        ("Groq SDK",      lambda: __import__("groq") and "OK"),
        (
            "OpenAI SDK",
            lambda: __import__("openai") and "OK"
            if cfg.ai.default_provider == "openai"
            else "not required"
        ),
    ]
    for name, fn in checks:
        try:
            result = fn()
            results.append((name, f"✅ {result}"))
        except Exception as e:
            results.append((name, f"❌ {e}"))
    for n, s in results:
        print(f"  {n:<20} {s}")
    passed = sum(1 for _, s in results if "✅" in s)
    print(f"\n  {passed}/{len(checks)} checks passed\n")
    try:
        from brain.ai_router import AIRouter
        status = AIRouter().get_status()
        print("  AI Provider Status:")
        for provider, info in status.get("providers", {}).items():
            mark = "✅" if info.get("available") else ("⚙" if info.get("configured") else "❌")
            print(f"    {mark} {provider:<14} {info.get('model','')}")
        print(f"\n  Default: {status.get('default','unknown')}\n")
    except Exception as e:
        print(f"  ❌ Could not check AI providers: {e}\n")


def main():
    args = parse_args()
    print_banner()

    if args.debug:
        os.environ["DREX_DEBUG"] = "true"
        os.environ["DREX_LOG_LEVEL"] = "DEBUG"

    try:
        from utils.logger import setup_logger
        setup_logger()
    except ImportError:
        from loguru import logger
        logger.add(
            "logs/drex.log",
            level=os.getenv("DREX_LOG_LEVEL", "INFO"),
            rotation="10 MB",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        )

    if args.test:
        run_test()
        sys.exit(0)

    warnings = validate_config()
    for w in warnings:
        print(w)

    if any("needs at least one" in w for w in warnings):
        print("\n  Add at least one API key to your .env file and restart.\n")
        sys.exit(1)

    from config import get_config
    cfg = get_config()
    print(f"\n🚀 Starting {cfg.app.name} v{cfg.app.version}...")

    if args.no_voice:
        cfg.app.voice_enabled = False

    try:
        from core.orchestrator import Orchestrator
        orch = Orchestrator()
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    try:
        if args.text:
            run_text_loop(orch)
        else:
            run_gui(orch, auto_voice=not args.no_voice)
    except Exception as e:
        print(f"❌ Fatal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            orch.shutdown()
        except Exception:
            pass

    print("\n✅ DREX exited cleanly.")


if __name__ == "__main__":
    main()