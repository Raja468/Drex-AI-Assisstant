#!/usr/bin/env python3
# ============================================================
#  DREX - AI Assistant Runtime
#  scripts/verify_assistant.py  —  Assistant Module Verification
#
#  Verifies that all assistant module components are properly
#  installed and functioning.
#
#  Usage:
#    python scripts/verify_assistant.py
#    python scripts/verify_assistant.py --verbose
# ============================================================

import sys
import os
import importlib
from typing import Tuple

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ANSI colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text: str):
    """Print a section header."""
    print(f"\n{BLUE}{BOLD}{'='*60}{RESET}")
    print(f"{BLUE}{BOLD}  {text}{RESET}")
    print(f"{BLUE}{BOLD}{'='*60}{RESET}\n")


def print_result(name: str, success: bool, message: str = ""):
    """Print a test result."""
    status = f"{GREEN}✓ PASS{RESET}" if success else f"{RED}✗ FAIL{RESET}"
    print(f"  {status}  {name}")
    if message and not success:
        print(f"         {YELLOW}→ {message}{RESET}")


def check_import(module_path: str, class_name: str = None) -> Tuple[bool, str]:
    """Check if a module/class can be imported."""
    try:
        module = importlib.import_module(module_path)
        if class_name:
            getattr(module, class_name)
        return True, ""
    except ImportError as e:
        return False, f"Import error: {e}"
    except AttributeError as e:
        return False, f"Class not found: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def check_optional_dependency(package_name: str) -> Tuple[bool, str]:
    """Check if an optional dependency is available."""
    try:
        importlib.import_module(package_name)
        return True, ""
    except ImportError:
        return False, f"{package_name} not installed"


def verify_core_components():
    """Verify core assistant components."""
    print_header("Core Components")
    
    components = [
        ("assistant.state_engine", "StateEngine"),
        ("assistant.state_engine", "AssistantState"),
        ("assistant.state_engine", "AssistantMode"),
        ("assistant.mode_manager", "ModeManager"),
        ("assistant.interruption_handler", "InterruptionHandler"),
    ]
    
    passed = 0
    for module_path, class_name in components:
        success, message = check_import(module_path, class_name)
        print_result(f"{module_path}.{class_name}", success, message)
        if success:
            passed += 1
    
    return passed, len(components)


def verify_ui_components():
    """Verify UI components."""
    print_header("UI Components")
    
    components = [
        ("assistant.floating_orb", "FloatingOrb"),
        ("assistant.agent_panel", "AgentPanel"),
    ]
    
    passed = 0
    for module_path, class_name in components:
        success, message = check_import(module_path, class_name)
        print_result(f"{module_path}.{class_name}", success, message)
        if success:
            passed += 1
    
    return passed, len(components)


def verify_system_components():
    """Verify system integration components."""
    print_header("System Integration")
    
    components = [
        ("assistant.system_tray", "SystemTray"),
        ("assistant.global_hotkey", "GlobalHotkey"),
    ]
    
    passed = 0
    for module_path, class_name in components:
        success, message = check_import(module_path, class_name)
        print_result(f"{module_path}.{class_name}", success, message)
        if success:
            passed += 1
    
    return passed, len(components)


def verify_voice_components():
    """Verify voice hardening components."""
    print_header("Voice Hardening")
    
    components = [
        ("assistant.echo_canceller", "EchoCanceller"),
        ("assistant.streaming_tts", "StreamingTTS"),
        ("assistant.silence_detector", "SilenceDetector"),
    ]
    
    passed = 0
    for module_path, class_name in components:
        success, message = check_import(module_path, class_name)
        print_result(f"{module_path}.{class_name}", success, message)
        if success:
            passed += 1
    
    return passed, len(components)


def verify_streaming_components():
    """Verify streaming UX components."""
    print_header("Streaming UX")
    
    components = [
        ("assistant.streaming_renderer", "StreamingRenderer"),
    ]
    
    passed = 0
    for module_path, class_name in components:
        success, message = check_import(module_path, class_name)
        print_result(f"{module_path}.{class_name}", success, message)
        if success:
            passed += 1
    
    return passed, len(components)


def verify_chat_components():
    """Verify chat enhancement components."""
    print_header("Chat Enhancement")
    
    components = [
        ("assistant.markdown_renderer", "MarkdownRenderer"),
        ("assistant.code_highlighter", "CodeHighlighter"),
        ("assistant.document_analyzer", "DocumentAnalyzer"),
    ]
    
    passed = 0
    for module_path, class_name in components:
        success, message = check_import(module_path, class_name)
        print_result(f"{module_path}.{class_name}", success, message)
        if success:
            passed += 1
    
    return passed, len(components)


def verify_os_components():
    """Verify OS integration components."""
    print_header("OS Integration")
    
    components = [
        ("assistant.clipboard_manager", "ClipboardManager"),
        ("assistant.app_awareness", "AppAwareness"),
    ]
    
    passed = 0
    for module_path, class_name in components:
        success, message = check_import(module_path, class_name)
        print_result(f"{module_path}.{class_name}", success, message)
        if success:
            passed += 1
    
    return passed, len(components)


def verify_optional_dependencies():
    """Verify optional dependencies."""
    print_header("Optional Dependencies")
    
    dependencies = [
        ("pystray", "System tray support"),
        ("keyboard", "Global hotkey support"),
        ("pygetwindow", "Active window detection"),
        ("pyperclip", "Clipboard access"),
        ("PIL", "Image processing"),
    ]
    
    passed = 0
    for package, description in dependencies:
        success, message = check_optional_dependency(package)
        status = f"{GREEN}✓{RESET}" if success else f"{YELLOW}○{RESET}"
        print(f"  {status}  {package:20} ({description})")
        if not success:
            print(f"         {YELLOW}→ Install with: pip install {package}{RESET}")
        if success:
            passed += 1
    
    return passed, len(dependencies)


def verify_state_engine():
    """Verify StateEngine functionality."""
    print_header("StateEngine Functionality")
    
    try:
        from assistant.state_engine import StateEngine, AssistantState, AssistantMode
        
        # Create instance
        engine = StateEngine()
        print_result("StateEngine instantiation", True)
        
        # Check initial state
        assert engine.state == AssistantState.IDLE, "Initial state should be IDLE"
        print_result("Initial state is IDLE", True)
        
        # Check initial mode
        assert engine.mode == AssistantMode.AGENT, "Initial mode should be AGENT"
        print_result("Initial mode is AGENT", True)
        
        # Test state transition
        engine.state = AssistantState.LISTENING
        assert engine.state == AssistantState.LISTENING, "State should be LISTENING"
        print_result("State transition to LISTENING", True)
        
        # Test mode switch
        engine.switch_mode(AssistantMode.CHAT)
        assert engine.mode == AssistantMode.CHAT, "Mode should be CHAT"
        print_result("Mode switch to CHAT", True)
        
        # Test state queries
        assert engine.can_listen() == False, "Should not be able to listen while in CHAT mode"
        print_result("State query methods", True)
        
        return 6, 6
        
    except Exception as e:
        print_result("StateEngine functionality", False, str(e))
        return 0, 6


def main():
    """Run all verification tests."""
    print(f"\n{BOLD}DREX Assistant Module Verification{RESET}")
    print(f"{'='*60}\n")
    
    total_passed = 0
    total_tests = 0
    
    # Run all verification sections
    sections = [
        verify_core_components,
        verify_ui_components,
        verify_system_components,
        verify_voice_components,
        verify_streaming_components,
        verify_chat_components,
        verify_os_components,
        verify_optional_dependencies,
        verify_state_engine,
    ]
    
    for section in sections:
        try:
            passed, tests = section()
            total_passed += passed
            total_tests += tests
        except Exception as e:
            print(f"\n{RED}Error in {section.__name__}: {e}{RESET}")
    
    # Print summary
    print_header("Summary")
    
    percentage = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    if percentage >= 90:
        color = GREEN
        status = "EXCELLENT"
    elif percentage >= 70:
        color = YELLOW
        status = "GOOD"
    else:
        color = RED
        status = "NEEDS ATTENTION"
    
    print(f"  Tests Passed: {color}{BOLD}{total_passed}/{total_tests}{RESET} ({percentage:.1f}%)")
    print(f"  Status: {color}{BOLD}{status}{RESET}")
    
    if total_passed < total_tests:
        print(f"\n  {YELLOW}Some components are missing or have issues.{RESET}")
        print(f"  {YELLOW}Install missing dependencies with:{RESET}")
        print(f"  {BLUE}pip install -r requirements.txt{RESET}")
    
    print()
    
    # Return exit code
    return 0 if percentage >= 70 else 1


if __name__ == "__main__":
    sys.exit(main())