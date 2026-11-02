# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/  —  Realtime Assistant Module
#
#  This module contains the core components for transforming
#  DREX from a chatbot into a realtime AI assistant runtime.
#
#  Components:
#  - StateEngine: Assistant state machine
#  - ModeManager: Agent/Chat mode switching
#  - InterruptionHandler: Speech interruption (barge-in)
#  - FloatingOrb: Floating overlay UI
#  - AgentPanel: Compact assistant panel
#  - SystemTray: System tray integration
#  - GlobalHotkey: Global hotkey support
#  - StreamingRenderer: Smooth token rendering
# ============================================================

from assistant.state_engine import (
    AssistantState,
    AssistantMode,
    StateEngine,
)
from assistant.mode_manager import ModeManager
from assistant.interruption_handler import InterruptionHandler

# UI components (optional - may fail without tkinter)
try:
    from assistant.floating_orb import FloatingOrb
    from assistant.agent_panel import AgentPanel
except ImportError:
    FloatingOrb = None
    AgentPanel = None

# System integration (optional dependencies)
try:
    from assistant.system_tray import SystemTray, is_tray_available
except ImportError as e:
    SystemTray = None
    is_tray_available = lambda: False
    logger = __import__('loguru').logger
    logger.warning(f"SystemTray not available: {e}")

try:
    from assistant.global_hotkey import GlobalHotkey, is_hotkey_available
except ImportError as e:
    GlobalHotkey = None
    is_hotkey_available = lambda: False
    logger = __import__('loguru').logger
    logger.warning(f"GlobalHotkey not available: {e}")

# Voice hardening
try:
    from assistant.echo_canceller import EchoCanceller
except ImportError as e:
    EchoCanceller = None
    logger = __import__('loguru').logger
    logger.warning(f"EchoCanceller not available: {e}")

try:
    from assistant.streaming_tts import StreamingTTS
except ImportError as e:
    StreamingTTS = None
    logger = __import__('loguru').logger
    logger.warning(f"StreamingTTS not available: {e}")

try:
    from assistant.silence_detector import SilenceDetector
except ImportError as e:
    SilenceDetector = None
    logger = __import__('loguru').logger
    logger.warning(f"SilenceDetector not available: {e}")

# Streaming UX
try:
    from assistant.streaming_renderer import StreamingRenderer
except ImportError as e:
    StreamingRenderer = None
    logger = __import__('loguru').logger
    logger.warning(f"StreamingRenderer not available: {e}")

# Chat Enhancement
try:
    from assistant.markdown_renderer import MarkdownRenderer
except ImportError as e:
    MarkdownRenderer = None
    logger = __import__('loguru').logger
    logger.warning(f"MarkdownRenderer not available: {e}")

try:
    from assistant.code_highlighter import CodeHighlighter, CodeBlock
except ImportError as e:
    CodeHighlighter = None
    CodeBlock = None
    logger = __import__('loguru').logger
    logger.warning(f"CodeHighlighter not available: {e}")

try:
    from assistant.document_analyzer import DocumentAnalyzer
except ImportError as e:
    DocumentAnalyzer = None
    logger = __import__('loguru').logger
    logger.warning(f"DocumentAnalyzer not available: {e}")

# OS Integration
try:
    from assistant.clipboard_manager import ClipboardManager, is_clipboard_available
except ImportError as e:
    ClipboardManager = None
    is_clipboard_available = lambda: False
    logger = __import__('loguru').logger
    logger.warning(f"ClipboardManager not available: {e}")

try:
    from assistant.app_awareness import AppAwareness, is_app_awareness_available
except ImportError as e:
    AppAwareness = None
    is_app_awareness_available = lambda: False
    logger = __import__('loguru').logger
    logger.warning(f"AppAwareness not available: {e}")

# Screen Understanding (JARVIS Vision)
try:
    from assistant.screen_capture import ScreenCapture
    # Helper functions that wrap the ScreenCapture class
    def capture_full_screen():
        sc = ScreenCapture()
        img = sc.capture_full()
        sc.close()
        return img
    def capture_active_window():
        sc = ScreenCapture()
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active:
                return sc.capture_window(active.title)
            return None
        except Exception:
            return None
        finally:
            sc.close()
    def is_screen_capture_available():
        return True
except ImportError as e:
    ScreenCapture = None
    capture_full_screen = None
    capture_active_window = None
    is_screen_capture_available = lambda: False
    logger = __import__('loguru').logger
    logger.warning(f"ScreenCapture not available: {e}")

try:
    from assistant.vision_analyzer import (
        VisionAnalyzer,
    )
except ImportError as e:
    VisionAnalyzer = None
    logger = __import__('loguru').logger
    logger.warning(f"VisionAnalyzer not available: {e}")

__all__ = [
    # Core
    "AssistantState",
    "AssistantMode",
    "StateEngine",
    "ModeManager",
    "InterruptionHandler",
    # UI
    "FloatingOrb",
    "AgentPanel",
    # System
    "SystemTray",
    "GlobalHotkey",
    "is_tray_available",
    "is_hotkey_available",
    # Voice
    "EchoCanceller",
    "StreamingTTS",
    "SilenceDetector",
    # Streaming
    "StreamingRenderer",
    # Chat
    "MarkdownRenderer",
    "CodeHighlighter",
    "CodeBlock",
    "DocumentAnalyzer",
    # OS Integration
    "ClipboardManager",
    "AppAwareness",
    "is_app_awareness_available",
    # Screen Understanding
    "ScreenCapture",
    "VisionAnalyzer",
    "capture_full_screen",
    "capture_active_window",
    "is_screen_capture_available",
]
