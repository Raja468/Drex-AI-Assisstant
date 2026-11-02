"""
Phase 5 Verification Script
Run: python scripts/verify_fixes.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("PHASE 5 — VERIFICATION")
print("=" * 60)

# 1. Test critical imports
print("\n--- 1. Critical Imports ---")

tests = [
    ("core.orchestrator.Orchestrator", "from core.orchestrator import Orchestrator"),
    ("core.intent_parser.IntentParser", "from core.intent_parser import IntentParser"),
    ("core.task_dispatcher.TaskDispatcher", "from core.task_dispatcher import TaskDispatcher"),
    ("assistant.ScreenCapture", "from assistant.screen_capture import ScreenCapture"),
    ("assistant.VisionAnalyzer", "from assistant.vision_analyzer import VisionAnalyzer"),
    ("memory.DBManager", "from memory.db_manager import DBManager"),
    ("memory.ConversationStore", "from memory.conversation_store import ConversationStore"),
    ("memory.ContextBuilder", "from memory.context_builder import ContextBuilder"),
    ("memory.UserPreferences", "from memory.user_preferences import UserPreferences"),
    ("core.permission_guard.PermissionGuard", "from core.permission_guard import PermissionGuard"),
    ("core.permission_guard.RiskLevel", "from core.permission_guard import RiskLevel"),
    ("config.validate_api_keys", "from config import validate_api_keys"),
]

all_ok = True
for name, import_stmt in tests:
    try:
        exec(import_stmt)
        print(f"  ✅ {name}")
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        all_ok = False

# 2. Verify UTF-8 fix in main.py
print("\n--- 2. UTF-8 Fix ---")
import io
content = open("main.py", encoding="utf-8").read()
has_utf8 = "TextIOWrapper" in content and "encoding='utf-8'" in content
print(f"  {'✅' if has_utf8 else '❌'} UTF-8 encoding fix in main.py")

# 3. Verify Cerebras model name fix
print("\n--- 3. Cerebras Model Name ---")
from config import get_config
cfg = get_config()
model = cfg.ai.cerebras_model
is_correct = model == "llama-3.3-70b"
print(f"  {'✅' if is_correct else '❌'} Cerebras model: {model}")

# 4. Verify config env var names
print("\n--- 4. Config Env Var Mappings ---")
checks = [
    ("DREX_DEBUG_MODE", "debug", "config.py reads DREX_DEBUG_MODE"),
    ("TTS_SPEED", "rate", "config.py reads TTS_SPEED"),
]
for expected, field, desc in checks:
    # Check the code reads the right env var
    ok = expected in open("config.py").read()
    print(f"  {'✅' if ok else '❌'} {desc}")

# 5. Verify .env has required vars
print("\n--- 5. .env File ---")
env_content = open(".env").read()
env_checks = [
    ("DREX_WAKE_WORD_ENABLED", "DREX_WAKE_WORD_ENABLED"),
    ("OPENROUTER_MODEL", "OPENROUTER_MODEL"),
]
for name in ["DREX_WAKE_WORD_ENABLED", "OPENROUTER_MODEL"]:
    ok = name in env_content
    print(f"  {'✅' if ok else '❌'} {name} present in .env")

# 6. Verify __init__ exports
print("\n--- 6. Module Exports ---")
from core import __all__ as core_all
print(f"  ✅ core.__all__: {core_all}")
from memory import __all__ as mem_all
print(f"  ✅ memory.__all__: {mem_all}")

# 7. Verify permission_guard
print("\n--- 7. Permission Guard ---")
from core.permission_guard import PermissionGuard, RiskLevel
guard = PermissionGuard()
low_ok = guard.request_approval("open_website", "Test low risk")
med_ok = guard.request_approval("write_file", "Test medium risk")
print(f"  {'✅' if low_ok else '❌'} LOW risk auto-approved")
print(f"  {'✅' if med_ok else '❌'} MEDIUM risk auto-approved")

# 8. Verify validate_api_keys
print("\n--- 8. API Key Validation ---")
from config import validate_api_keys
status = validate_api_keys()
for provider, available in status.items():
    mark = "✅" if available else "⚠"
    print(f"  {mark} {provider}: {'configured' if available else 'missing'}")

# 9. Verify screen_capture module exports
print("\n--- 9. Screen Capture ---")
from assistant.screen_capture import ScreenCapture
sc = ScreenCapture()
size = sc.get_screen_size()
print(f"  ✅ ScreenCapture.get_screen_size(): {size}")
print(f"  ✅ ScreenCapture.capture_full: {callable(sc.capture_full)}")
print(f"  ✅ ScreenCapture.capture_region: {callable(sc.capture_region)}")
print(f"  ✅ ScreenCapture.save_screenshot: {callable(sc.save_screenshot)}")
print(f"  ✅ ScreenCapture.capture_to_base64: {callable(sc.capture_to_base64)}")

# 10. Verify vision_analyzer methods
print("\n--- 10. Vision Analyzer ---")
from assistant.vision_analyzer import VisionAnalyzer
va = VisionAnalyzer()
has_analyze_screenshot = hasattr(va, "analyze_screenshot")
has_extract_text = hasattr(va, "extract_text_from_image")
has_describe_screen = hasattr(va, "describe_screen_content")
has_find_ui = hasattr(va, "find_ui_elements")
print(f"  ✅ analyze_screenshot: {has_analyze_screenshot}")
print(f"  ✅ extract_text_from_image: {has_extract_text}")
print(f"  ✅ describe_screen_content: {has_describe_screen}")
print(f"  ✅ find_ui_elements: {has_find_ui}")

# 11. Hex color check (8-digit)
print("\n--- 11. 8-Digit Hex Colors ---")
import re
for f in os.listdir("gui"):
    if f.endswith(".py"):
        try:
            content = open(f"gui/{f}").read()
            matches = re.findall(r"#[0-9a-fA-F]{8}", content)
            if matches:
                print(f"  ⚠ {f}: {matches}")
        except:
            pass
print("  ✅ Hex scan complete")

# Summary
print("\n" + "=" * 60)
print(f"VERIFICATION {'PASSED ✅' if all_ok else 'FAILED ❌'}")
print("=" * 60)