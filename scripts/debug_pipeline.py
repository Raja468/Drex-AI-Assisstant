"""
DREX Response Pipeline Debug Script
====================================
Traces the COMPLETE execution flow:
GUI input → orchestrator → AI router → provider → stream callback → final response

Usage:
    python scripts/debug_pipeline.py
"""

import sys, os, time, json, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
logger.remove()  # Remove default handler for clean output

from dotenv import load_dotenv
load_dotenv(override=True)

from config import get_config
cfg = get_config()

RESULTS = []


def log(level, msg):
    prefix = {"info": "ℹ️", "ok": "✅", "warn": "⚠️", "err": "❌", "debug": "🔍"}.get(level, "")
    print(f"{prefix} {msg}", flush=True)
    if level == "ok":
        RESULTS.append(("PASS", msg))
    elif level == "err":
        RESULTS.append(("FAIL", msg))


print("\n" + "="*60)
print("  DREX RESPONSE PIPELINE DEBUG")
print("="*60, flush=True)

# ── 1. Config check ──────────────────────────────────────────
log("info", "STEP 1: Config check")
log("info", f"  Personality: {cfg.app.personality}")
log("info", f"  Default AI: {cfg.ai.default_provider}")
log("info", f"  Gemini key: {'SET' if cfg.ai.gemini_api_key else 'MISSING'}")
log("info", f"  Groq key: {'SET' if cfg.ai.groq_api_key else 'MISSING'}")
log("info", f"  OpenRouter key: {'SET' if cfg.ai.openrouter_api_key else 'MISSING'}")
log("info", f"  Cerebras key: {'SET' if cfg.ai.cerebras_api_key else 'MISSING'}")
log("ok", "Config loaded")

# ── 2. Provider clients ───────────────────────────────────────
log("info", "\nSTEP 2: Provider client initialization")

from brain.gemini_client import GeminiClient
g = GeminiClient()
log("ok" if g.is_available else "warn", f"GeminiClient: available={g.is_available}")

from brain.groq_client import GroqClient
gr = GroqClient()
log("ok" if gr.is_available else "warn", f"GroqClient: available={gr.is_available}")

from brain.openrouter_client import OpenRouterClient
o = OpenRouterClient()
log("ok" if o.is_available else "warn", f"OpenRouterClient: available={o.is_available}")

from brain.cerebras_client import CerebrasClient
cr = CerebrasClient()
log("ok" if cr.is_available else "warn", f"CerebrasClient: available={cr.is_available}")

# ── 3. Direct provider test ───────────────────────────────────
log("info", "\nSTEP 3: Direct provider chat test")

test_prompt = "Say exactly: [Provider working] and nothing else."

for name, client in [("Gemini", g), ("Groq", gr), ("OpenRouter", o), ("Cerebras", cr)]:
    if client.is_available:
        try:
            start = time.time()
            resp = client.quick_ask(test_prompt)
            elapsed = time.time() - start
            if resp and len(resp) > 5:
                log("ok", f"{name}: responded in {elapsed:.1f}s ({len(resp)} chars)")
            else:
                log("warn", f"{name}: returned empty/None in {elapsed:.1f}s")
        except Exception as e:
            log("err", f"{name}: exception — {e}")
    else:
        log("warn", f"{name}: skipped (not available)")

# ── 4. Orchestrator pipeline ──────────────────────────────────
log("info", "\nSTEP 4: Orchestrator pipeline test")

from core.orchestrator import Orchestrator

# Collect stream tokens
stream_tokens = []
def on_stream_token(token):
    stream_tokens.append(token)

def on_response(text, provider):
    log("ok", f"on_response: provider={provider}, text_len={len(text)}, preview={text[:60]!r}")

def on_status(s):
    pass

orch = Orchestrator(
    on_response=on_response,
    on_status=on_status,
    on_stream_token=on_stream_token,
)

# Test 4a: greeting
log("info", "\n  Test 4a: Greeting 'hi'")
stream_tokens.clear()
resp = orch.process("Say exactly: Hello from DREX pipeline test")
log("info", f"  Response: {resp[:100]!r}...")
log("info", f"  Stream tokens received: {len(stream_tokens)}")
if resp and len(resp) > 10:
    log("ok", "Greeting produced a real response")
else:
    log("err", "Greeting response was empty or too short")

# Test 4b: small_talk "how are you"
log("info", "\n  Test 4b: 'how are you'")
stream_tokens.clear()
resp = orch.process("how are you")
log("info", f"  Response: {resp[:100]!r}...")
log("info", f"  Stream tokens received: {len(stream_tokens)}")
if resp and len(resp) > 5:
    log("ok", "Small talk produced real response")
else:
    log("err", "Small talk response was empty or too short")

# Test 4c: automation
log("info", "\n  Test 4c: Automation 'open Chrome'")
resp = orch.process("open Chrome")
log("info", f"  Response: {resp[:100]!r}...")
if resp:
    log("ok", "Automation handler works")

# Test 4d: hello in hacker mode
log("info", "\n  Test 4d: Hacker mode greeting")
orch.prompt_builder.set_personality("hacker")
stream_tokens.clear()
resp = orch.process("hi")
log("info", f"  Response: {resp!r}")
if "HELLO" in resp or ">>" in resp:
    log("ok", "Hacker mode terminal response preserved")
else:
    log("warn", "Hacker mode response unexpected")

# Reset to jarvis
orch.prompt_builder.set_personality("jarvis")

orch.shutdown()

# ── 5. Summary ───────────────────────────────────────────────
print("\n" + "="*60)
print("  RESULTS SUMMARY")
print("="*60)
pass_count = sum(1 for r in RESULTS if r[0] == "PASS")
fail_count = sum(1 for r in RESULTS if r[0] == "FAIL")
for status, msg in RESULTS:
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon} {msg}")
print(f"\n  {pass_count} passed, {fail_count} failed out of {len(RESULTS)} checks")
print("="*60)