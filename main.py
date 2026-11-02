#!/usr/bin/env python3
"""DREX - AI Desktop Assistant | main entry point"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import argparse
import os
from dotenv import load_dotenv

from loguru import logger
logger.add(
    "logs/drex.log",
    level=os.getenv("DREX_LOG_LEVEL", "INFO"),
    rotation="10 MB",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

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
        if not ai.cerebras_api_key or ai.cerebras_api_key == "your_cerebras_key_here":
            warnings.append("  ⚠  CEREBRAS_API_KEY not set in .env")
        if len(warnings) == 4:
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


def run_gui(orchestrator, auto_voice=True, supervisor=None):
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
            if hasattr(app, "chat_panel") and hasattr(app.chat_panel, "add_message"):
                app.chat_panel.add_message("assistant", greeting)
        except Exception:
            pass

    app.after(400, show_welcome)
    app.run()


# ── Runtime supervisor helpers ─────────────────────────────────

def create_runtime(orchestrator):
    """
    Create the RuntimeSupervisor, registering the orchestrator,
    VoiceEngine, and core capabilities for lifecycle tracking.

    This is additive — the existing startup flow is unchanged. The
    supervisor wraps existing systems without replacing them.
    """
    from runtime import CapabilityRegistry, RuntimeSupervisor
    from runtime.capability_registry import CORE_CAPABILITIES
    from voice.voice_engine import VoiceEngine

    supervisor = RuntimeSupervisor()

    # ── 1. Register the orchestrator as a managed component ──
    supervisor.register_component(
        "orchestrator",
        orchestrator,
        autostart=False,
        metadata={"role": "core_controller"},
    )

    # ── 2. Create VoiceEngine and hand it to the orchestrator ──
    voice_engine = VoiceEngine(event_bus=supervisor.event_bus)
    supervisor.register_component(
        "voice_engine",
        voice_engine,
        autostart=True,
        metadata={"role": "voice_subsystem"},
    )

    # Wire VoiceEngine into the orchestrator so it becomes the
    # source of truth for speaker / listener / wake word.
    orchestrator._voice_engine = voice_engine

    # Also wire VoiceEngine into orchestrator's voice state
    # so VoiceState delegates to VoiceEngine instead of running
    # a duplicate local state machine.
    if hasattr(orchestrator, 'voice_state') and hasattr(orchestrator.voice_state, 'set_voice_engine'):
        orchestrator.voice_state.set_voice_engine(voice_engine)

    # ── 3. Create and register ToolRegistry with tool adapters ──
    from runtime.tools import ToolRegistry, ToolExecutor, PermissionEvaluator
    from runtime.tools.adapters import (
        BrowserTool,
        ClipboardTool,
        AppLauncherTool,
        ScreenshotTool,
        FileTool,
        SystemTool,
    )

    tool_registry = ToolRegistry()
    tool_evaluator = PermissionEvaluator(auto_approve_safe=True)
    tool_executor = ToolExecutor(
        registry=tool_registry,
        evaluator=tool_evaluator,
        event_bus=supervisor.event_bus,
    )

    # Register all tool adapters, linking to capability registry
    cap_reg = supervisor._components.get("capability_registry", None)
    cap_reg_instance = cap_reg.instance if cap_reg else None

    for tool_cls in (
        BrowserTool,
        ClipboardTool,
        AppLauncherTool,
        ScreenshotTool,
        FileTool,
        SystemTool,
    ):
        try:
            tool_instance = tool_cls()
            tool_registry.register_tool(tool_instance, capability_registry=cap_reg_instance)
        except Exception as e:
            logger.warning("Tool registration skipped for {}: {}", tool_cls.__name__, e)

    supervisor.register_component(
        "tool_registry",
        tool_registry,
        autostart=False,
        metadata={"role": "tool_runtime"},
    )
    supervisor.register_component(
        "tool_executor",
        tool_executor,
        autostart=False,
        metadata={"role": "tool_execution"},
    )

    # Wire tool_executor into orchestrator for ToolRouter integration
    orchestrator._tool_executor = tool_executor

    # ── 3b. Create IntentService, ToolRouter, ResponseService ──
    from core.intent_service import IntentService
    from core.tool_router import ToolRouter
    from core.response_service import ResponseService

    intent_service = IntentService(orchestrator.intent_parser)
    tool_router = ToolRouter(tool_registry, tool_executor, intent_service)
    response_service = ResponseService(voice_mode=bool(orchestrator._voice_mode))

    # Wire into orchestrator (checked on None before use in process())
    orchestrator._intent_service = intent_service
    orchestrator._tool_router = tool_router
    orchestrator._response_service = response_service

    logger.info("Tool runtime initialized | tools={}", tool_registry.count())

    # ── 3c. Create TaskManager and register as runtime component ──
    from runtime.tasks import TaskManager
    task_manager = TaskManager(event_bus=supervisor.event_bus)
    supervisor.register_component(
        "task_manager",
        task_manager,
        autostart=True,
        metadata={"role": "task_management"},
    )
    logger.info("TaskManager registered | autostart=true")

    # ── 3d. Create Planner and register as runtime component ──
    from runtime.planning import GoalDecomposer, Planner
    goal_decomposer = GoalDecomposer()
    planner = Planner(event_bus=supervisor.event_bus, goal_decomposer=goal_decomposer)
    supervisor.register_component(
        "planner",
        planner,
        autostart=True,
        metadata={"role": "planning"},
    )
    logger.info("Planner registered | autostart=true")

    # Wire planner into orchestrator (no behavior changes to process())
    orchestrator.planner = planner

    # ── 3e. Create ExecutionEngine and register as runtime component ──
    from runtime.execution import ExecutionEngine
    execution_engine = ExecutionEngine(
        event_bus=supervisor.event_bus,
        task_manager=task_manager,
        tool_router=tool_router,
        intent_service=intent_service,
        response_service=response_service
    )
    supervisor.register_component(
        "execution_engine",
        execution_engine,
        autostart=True,
        metadata={"role": "task_execution"},
    )
    logger.info("ExecutionEngine registered | autostart=true")

    # Wire execution engine into orchestrator
    orchestrator.execution_engine = execution_engine

    # ── 3f. Create AwarenessEngine and register as runtime component ──
    from runtime.awareness import AwarenessEngine
    awareness_engine = AwarenessEngine(event_bus=supervisor.event_bus)
    supervisor.register_component(
        "awareness_engine",
        awareness_engine,
        autostart=True,
        metadata={"role": "environment_awareness"},
    )
    logger.info("AwarenessEngine registered | autostart=true")

    # Wire awareness engine into orchestrator (read-only query)
    orchestrator.awareness_engine = awareness_engine

    # ── 4. Create and register a capability registry ──
    registry = CapabilityRegistry()
    registry.register_many(CORE_CAPABILITIES)

    # Update actual availability from orchestrator state
    registry.register("voice", available=bool(orchestrator._voice_mode))
    registry.register("automation", available=True)
    registry.register("task_management", available=task_manager.is_running)
    registry.register("planning", available=planner.is_running)
    registry.register("execution", available=execution_engine.is_running)
    registry.register("awareness", available=True)
    registry.register("screen_awareness", available=True)

    supervisor.register_component(
        "capability_registry",
        registry,
        autostart=False,
        metadata={"role": "capability_tracking"},
    )

    logger.info("Runtime supervisor created")
    return supervisor


def initialize_runtime(orchestrator):
    """Set up and start the runtime supervisor (additive, non-breaking)."""
    supervisor = create_runtime(orchestrator)
    supervisor.start()
    logger.info("Runtime lifecycle started")
    return supervisor


def shutdown_runtime(supervisor):
    """Gracefully shut down the runtime supervisor."""
    if supervisor is not None:
        try:
            supervisor.stop()
            logger.info("Runtime lifecycle stopped")
        except Exception as e:
            logger.error("Runtime shutdown error: {}", e)


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

    # ── Initialize runtime supervisor (additive, non-breaking) ──
    runtime_supervisor = None
    try:
        runtime_supervisor = initialize_runtime(orch)
        print("  ✓ Runtime supervisor initialized")
    except Exception as e:
        logger.warning("Runtime supervisor init skipped (non-critical): {}", e)

    try:
        if args.text:
            run_text_loop(orch)
        else:
            run_gui(orch, auto_voice=not args.no_voice, supervisor=runtime_supervisor)
    except Exception as e:
        print(f"❌ Fatal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            orch.shutdown()
        except Exception:
            pass
        # ── Shut down runtime supervisor ──
        if runtime_supervisor is not None:
            try:
                shutdown_runtime(runtime_supervisor)
            except Exception as e:
                logger.error("Runtime supervisor shutdown error: {}", e)

    print("\n✅ DREX exited cleanly.")


if __name__ == "__main__":
    main()