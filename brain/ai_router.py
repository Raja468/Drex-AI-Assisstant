# ============================================================
#  DREX - AI Desktop Assistant
#  brain/ai_router.py  —  AI Traffic Controller
#
#  ROUTING LOGIC:
#
#  Task Type    → Primary    → Fallback 1  → Fallback 2  → Fallback 3
#  ──────────────────────────────────────────────────────────────────
#  fast/simple  → Cerebras   → Groq        → Gemini      → OpenRouter
#  general      → Gemini     → Cerebras    → Groq        → OpenRouter
#  coding       → OpenRouter → Gemini      → Cerebras    → Groq
#  reasoning    → Cerebras   → Groq        → Gemini      → OpenRouter
#  creative     → Gemini     → OpenRouter  → Cerebras    → Groq
#  ──────────────────────────────────────────────────────────────────
# ============================================================

import re
import time
from typing import Optional
from utils.logger import logger
from brain.base_client import StreamCallback
from utils.error_handler import AIError
from brain.gemini_client import GeminiClient
from brain.groq_client import GroqClient
from brain.openrouter_client import OpenRouterClient
from brain.cerebras_client import CerebrasClient
from brain.prompt_builder import PromptBuilder

try:
    from config import AIConfig
except ImportError:
    class AIConfig:
        CONTEXT_WINDOW = 10
        MAX_TOKENS = 1024
        TEMPERATURE = 0.7
        FALLBACK_CHAIN = ["gemini", "groq", "openrouter", "cerebras"]


# ─────────────────────────────────────────────────────────────
#  TASK CLASSIFICATION KEYWORDS
# ─────────────────────────────────────────────────────────────

CODING_KEYWORDS = [
    "code", "program", "function", "class", "debug", "error",
    "python", "javascript", "java", "c++", "html", "css", "sql",
    "algorithm", "script", "api", "bug", "fix", "implement",
    "syntax", "loop", "array", "variable", "import", "library",
    "compile", "run", "execute", "deploy", "git", "github"
]

FAST_KEYWORDS = [
    "quick", "fast", "brief", "short", "simple", "just", "only",
    "what is", "what's", "who is", "when is", "where is",
    "define", "meaning", "translate", "convert", "calculate",
    "how many", "how much", "yes or no", "true or false"
]

REASONING_KEYWORDS = [
    "why", "explain", "analyze", "compare", "evaluate", "think",
    "pros and cons", "advantages", "disadvantages", "should i",
    "what do you think", "recommend", "suggest", "which is better",
    "step by step", "how does", "reason", "logic", "argument"
]

CREATIVE_KEYWORDS = [
    "write", "story", "poem", "creative", "imagine", "invent",
    "essay", "blog", "article", "describe", "narrate", "compose",
    "lyrics", "joke", "fiction", "character", "plot", "create a"
]


class AIRouter:
    """
    Routes AI requests to the best available model.
    Providers: Gemini, Groq, OpenRouter, Cerebras
    """

    def __init__(self, memory_manager=None):
        logger.info("🧠 Initializing AI Router...")

        # Initialize all AI clients
        self.gemini = GeminiClient()
        self.groq = GroqClient()
        self.openrouter = OpenRouterClient()
        self.cerebras = CerebrasClient()

        # Prompt builder
        self.prompt_builder = PromptBuilder(memory_manager)

        # Track health of each provider
        self._api_health = {
            "gemini": self.gemini.is_available,
            "groq": self.groq.is_available,
            "openrouter": self.openrouter.is_available,
            "cerebras": self.cerebras.is_available,
        }

        available = [k for k, v in self._api_health.items() if v]
        unavailable = [k for k, v in self._api_health.items() if not v]

        if available:
            logger.info("✅ AI Router ready | Available: {}", available)
        if unavailable:
            logger.warning("⚠️  Unavailable APIs: {} (check .env keys)", unavailable)
        if not available:
            logger.error("❌ NO AI APIs are configured! Add keys to .env")

    # ──────────────────────────────────────────────────────────
    #  MAIN ROUTING METHOD
    # ──────────────────────────────────────────────────────────

    def route(
        self,
        user_input: str,
        session_id: str = "default",
        intent=None,
        force_provider: Optional[str] = None
    ) -> str:
        if not any(self._api_health.values()):
            return (
                "I don't have any AI APIs configured yet. "
                "Please add your API keys to the .env file. "
                "I can still help with automation tasks like opening apps!"
            )

        task_type = self._classify_task(user_input, intent)
        logger.info("🎯 Task classified as: '{}'", task_type)

        prompt = self.prompt_builder.build(
            user_input=user_input,
            session_id=session_id,
            task_type=task_type,
        )

        if force_provider and self._api_health.get(force_provider):
            provider_order = [force_provider] + [
                p for p in self._get_provider_order(task_type)
                if p != force_provider
            ]
        else:
            provider_order = self._get_provider_order(task_type)

        response = self._call_with_fallback(
            prompt=prompt,
            task_type=task_type,
            provider_order=provider_order
        )

        if response:
            return response

        return (
            "I'm having trouble reaching my AI services right now. "
            "Please check your internet connection and API keys."
        )

    # ──────────────────────────────────────────────────────────
    #  GENERATE METHOD (called by Orchestrator)
    # ──────────────────────────────────────────────────────────

    def generate(
        self,
        messages: list[dict],
        system_prompt: str,
        user_input: str,
        intent=None,
        force_provider: Optional[str] = None,
    ) -> tuple[str, str]:
        if not any(self._api_health.values()):
            return (
                "I don't have any AI APIs configured yet. "
                "Please add your API keys to the .env file.",
                "none",
            )

        task_type = self._classify_task(user_input, intent)
        logger.info("🎯 Task classified as: '{}'", task_type)

        if force_provider and self._api_health.get(force_provider):
            provider_order = [force_provider] + [
                p for p in self._get_provider_order(task_type)
                if p != force_provider
            ]
        else:
            provider_order = self._get_provider_order(task_type)

        for provider in provider_order:
            logger.info("🤖 Trying provider: {}", provider)
            try:
                response = self._call_provider(
                    provider=provider,
                    messages=messages,
                    system=system_prompt,
                    task_type=task_type,
                )
                if response:
                    return response, provider

            except AIError as e:
                error_code = str(e)
                if "RATE_LIMIT" in error_code:
                    logger.warning("⏱️ {} rate limited. Trying next...", provider)
                    time.sleep(0.5)
                    continue
                if "AUTH_ERROR" in error_code:
                    logger.error("🔑 {} auth failed. Skipping...", provider)
                    self._api_health[provider] = False
                    continue
                if "CONNECTION_ERROR" in error_code or "TIMEOUT_ERROR" in error_code:
                    logger.warning("🌐 {} network issue ({}). Trying next...", provider, error_code)
                    time.sleep(1.0)
                    continue
                if "MODEL_NOT_FOUND" in error_code:
                    logger.error("🔥 {} model config error. Skipping...", provider)
                    continue
                logger.error("❌ {} error: {}", provider, e)
                continue

            except Exception as e:
                logger.error("Unexpected error with {}: {}", provider, e)
                continue

        logger.error("All AI providers failed!")
        return (
            "I'm having trouble reaching my AI services right now. "
            "Please check your internet connection and API keys.",
            "none",
        )

    def generate_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        user_input: str,
        on_token: StreamCallback = None,
        intent=None,
        force_provider: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Stream tokens via on_token while assembling the full response.
        Uses the same routing and fallback logic as generate().
        """
        if not any(self._api_health.values()):
            return (
                "I don't have any AI APIs configured yet. "
                "Please add your API keys to the .env file.",
                "none",
            )

        task_type = self._classify_task(user_input, intent)
        logger.info("🎯 Task classified as: '{}' (streaming)", task_type)

        if force_provider and self._api_health.get(force_provider):
            provider_order = [force_provider] + [
                p for p in self._get_provider_order(task_type)
                if p != force_provider
            ]
        else:
            provider_order = self._get_provider_order(task_type)

        for provider in provider_order:
            logger.info("🤖 Streaming via provider: {}", provider)
            try:
                response = self._stream_provider(
                    provider=provider,
                    messages=messages,
                    system=system_prompt,
                    on_token=on_token,
                )
                if response:
                    return response, provider

            except AIError as e:
                if not self._handle_stream_error(provider, e):
                    continue

            except Exception as e:
                logger.error("Unexpected stream error with {}: {}", provider, e)
                continue

        logger.error("All AI providers failed (streaming)!")
        return (
            "I'm having trouble reaching my AI services right now. "
            "Please check your internet connection and API keys.",
            "none",
        )

    def _handle_stream_error(self, provider: str, e: AIError) -> bool:
        """Apply fallback policy for streaming errors. Returns True if fatal to chain."""
        error_code = str(e)
        if "RATE_LIMIT" in error_code:
            logger.warning("⏱️ {} rate limited. Trying next...", provider)
            time.sleep(0.5)
            return False
        if "AUTH_ERROR" in error_code:
            logger.error("🔑 {} auth failed. Skipping...", provider)
            self._api_health[provider] = False
            return False
        if "CONNECTION_ERROR" in error_code or "TIMEOUT_ERROR" in error_code:
            logger.warning("🌐 {} network issue ({}). Trying next...", provider, error_code)
            time.sleep(1.0)
            return False
        if "MODEL_NOT_FOUND" in error_code:
            logger.error("🔥 {} model config error. Skipping...", provider)
            return False
        logger.error("❌ {} stream error: {}", provider, e)
        return False

    # ──────────────────────────────────────────────────────────
    #  TASK CLASSIFIER
    # ──────────────────────────────────────────────────────────

    def _classify_task(self, text: str, intent=None) -> str:
        text_lower = text.lower()
        scores = {
            "coding": sum(1 for k in CODING_KEYWORDS if k in text_lower),
            "fast": sum(1 for k in FAST_KEYWORDS if k in text_lower),
            "reasoning": sum(1 for k in REASONING_KEYWORDS if k in text_lower),
            "creative": sum(1 for k in CREATIVE_KEYWORDS if k in text_lower),
        }
        best = max(scores, key=scores.get)
        if scores[best] >= 2:
            return best
        if scores[best] == 1:
            return best
        if len(text.split()) <= 6:
            return "fast"
        return "general"

    # ──────────────────────────────────────────────────────────
    #  PROVIDER ORDER SELECTION
    # ──────────────────────────────────────────────────────────

    def _get_provider_order(self, task_type: str) -> list[str]:
        routing_table = {
            "fast":      ["cerebras", "groq",       "gemini",     "openrouter"],
            "general":   ["gemini",   "cerebras",   "groq",       "openrouter"],
            "coding":    ["openrouter", "gemini",   "cerebras",   "groq"],
            "reasoning": ["cerebras", "groq",       "gemini",     "openrouter"],
            "creative":  ["gemini",   "openrouter", "cerebras",   "groq"],
        }
        order = routing_table.get(task_type, routing_table["general"])
        available_order = [p for p in order if self._api_health.get(p, False)]
        if not available_order:
            available_order = [p for p, v in self._api_health.items() if v]
        logger.debug("Provider order for [{}]: {}", task_type, available_order)
        return available_order

    # ──────────────────────────────────────────────────────────
    #  CALL WITH FALLBACK
    # ──────────────────────────────────────────────────────────

    def _call_with_fallback(
        self,
        prompt: dict,
        task_type: str,
        provider_order: list[str]
    ) -> Optional[str]:
        system = prompt.get("system", "")
        messages = prompt.get("messages", [])

        for provider in provider_order:
            logger.info("🤖 Trying provider: {}", provider)
            try:
                response = self._call_provider(
                    provider=provider,
                    messages=messages,
                    system=system,
                    task_type=task_type
                )
                if response:
                    return response
            except AIError as e:
                error_code = str(e)
                if "RATE_LIMIT" in error_code:
                    logger.warning("⏱️ {} rate limited. Trying next...", provider)
                    time.sleep(0.5)
                    continue
                elif "AUTH_ERROR" in error_code:
                    logger.error("🔑 {} auth failed. Skipping...", provider)
                    self._api_health[provider] = False
                    continue
                elif "CONNECTION_ERROR" in error_code or "TIMEOUT_ERROR" in error_code:
                    logger.warning("🌐 {} network issue ({}). Trying next...", provider, error_code)
                    # Transient — do not permanently disable
                    time.sleep(1.0)
                    continue
                elif "MODEL_NOT_FOUND" in error_code:
                    logger.error("🔥 {} model config error. Skipping...", provider)
                    continue
                else:
                    logger.error("❌ {} error: {}", provider, e)
                    continue
            except Exception as e:
                logger.error("Unexpected error with {}: {}", provider, e)
                continue

        logger.error("All AI providers failed!")
        return None

    def _get_client(self, provider: str):
        return {
            "gemini": self.gemini,
            "groq": self.groq,
            "openrouter": self.openrouter,
            "cerebras": self.cerebras,
        }.get(provider)

    def _call_provider(
        self,
        provider: str,
        messages: list[dict],
        system: str,
        task_type: str
    ) -> Optional[str]:
        client = self._get_client(provider)
        if not client:
            return None
        return client.chat(messages=messages, system_prompt=system)

    def _stream_provider(
        self,
        provider: str,
        messages: list[dict],
        system: str,
        on_token: StreamCallback = None,
    ) -> Optional[str]:
        client = self._get_client(provider)
        if not client or not client.is_available:
            return None

        parts: list[str] = []

        def _token_cb(token: str):
            parts.append(token)
            if on_token:
                on_token(token)

        for _token in client.stream_chat(
            messages=messages,
            system_prompt=system,
            on_token=_token_cb,
        ):
            pass

        assembled = "".join(parts)
        return assembled if assembled else None

    # ──────────────────────────────────────────────────────────
    #  STATUS & UTILITIES
    # ──────────────────────────────────────────────────────────

    def reset_status(self):
        self._api_health = {
            "gemini": self.gemini.is_available,
            "groq": self.groq.is_available,
            "openrouter": self.openrouter.is_available,
            "cerebras": self.cerebras.is_available,
        }

    def get_status(self) -> dict:
        from config import get_config
        cfg = get_config()
        fallback_chain = ["gemini", "groq", "openrouter", "cerebras"]
        default_provider = cfg.ai.default_provider.lower()
        if not self._api_health.get(default_provider, False):
            default_provider = next(
                (p for p in fallback_chain if self._api_health.get(p)),
                "none"
            )
        return {
            "providers": {
                "gemini": {
                    "available": self._api_health.get("gemini", False),
                    "configured": bool(cfg.ai.gemini_api_key),
                    "model": cfg.ai.gemini_model,
                },
                "groq": {
                    "available": self._api_health.get("groq", False),
                    "configured": bool(cfg.ai.groq_api_key),
                    "model": cfg.ai.groq_model,
                },
                "openrouter": {
                    "available": self._api_health.get("openrouter", False),
                    "configured": bool(cfg.ai.openrouter_api_key),
                    "model": cfg.ai.openrouter_model,
                },
                "cerebras": {
                    "available": self._api_health.get("cerebras", False),
                    "configured": bool(cfg.ai.cerebras_api_key),
                    "model": cfg.ai.cerebras_model,
                },
            },
            "available_count": sum(self._api_health.values()),
            "primary": next(
                (p for p in fallback_chain if self._api_health.get(p)),
                "none"
            ),
            "default": default_provider,
        }

    def get_status_text(self) -> str:
        parts = []
        for provider, available in self._api_health.items():
            icon = "✅" if available else "❌"
            parts.append(f"{icon} {provider.capitalize()}")
        return " | ".join(parts)