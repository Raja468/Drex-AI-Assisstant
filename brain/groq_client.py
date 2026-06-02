"""
brain/groq_client.py — Groq API Client for DREX

Provides ultra-fast AI inference via Groq's LPU hardware.
Supports both synchronous chat and streaming responses.

FREE TIER LIMITS (as of 2024):
  - 14,400 requests/day free
  - Ultra-fast inference (LPU chips) — often <1 second
  - Get key at: https://console.groq.com
"""

from typing import Callable, Generator, Optional
from utils.logger import logger
from utils.error_handler import AIError
from brain.base_client import BaseAIClient, StreamCallback

try:
    from config import get_config
    cfg = get_config()
    GROQ_API_KEY = cfg.ai.groq_api_key
except ImportError:
    GROQ_API_KEY = ""
    cfg = None
    class AIConfig:
        MAX_TOKENS = 1024
        TEMPERATURE = 0.7
        GROQ_MODEL_FAST = "llama-3.1-8b-instant"
        GROQ_MODEL_SMART = "llama-3.1-70b-versatile"


class GroqClient(BaseAIClient):
    """
    Wrapper for the Groq API with streaming support.

    Groq is used for FAST responses — nearly instant even for large models.
    Perfect for Drex's quick-answer mode and realtime streaming.
    """

    def __init__(self):
        self._client = None
        self._available = False
        self._init()

    def _init(self) -> None:
        if not GROQ_API_KEY:
            logger.warning("⚠️ GROQ_API_KEY not set. Groq unavailable.")
            return
        try:
            from groq import Groq
            self._client = Groq(api_key=GROQ_API_KEY)
            self._available = True
            logger.info("✅ GroqClient initialized")
        except ImportError:
            logger.warning("groq library not installed. Run: pip install groq")
        except Exception as e:
            logger.error(f"Groq init failed: {e}")

    @property
    def is_available(self) -> bool:
        return self._available

    def generate(self, prompt: str, context: dict = None) -> str:
        """Legacy text prompt interface — delegates to chat()."""
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=(context or {}).get("system", ""),
        )

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> Optional[str]:
        """
        Send a conversation to Groq and get a full response.

        Args:
            messages: List of {"role": "user"/"assistant", "content": "..."}
            system_prompt: System instructions
            model: Model name (default: llama-3.1-8b-instant)
            temperature: Creativity 0.0-1.0
            max_tokens: Max response length

        Returns:
            Response text, or None if failed
        """
        if not self._available:
            return None

        model = model or (cfg.ai.groq_model if cfg else AIConfig.GROQ_MODEL_FAST)
        temp = temperature or (
            cfg.ai.temperature if cfg else AIConfig.TEMPERATURE
        )
        max_tok = max_tokens or (
            cfg.ai.max_tokens if cfg else AIConfig.MAX_TOKENS
        )

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            completion = self._client.chat.completions.create(
                model=model,
                messages=full_messages,
                temperature=temp,
                max_tokens=max_tok,
                stream=False,
            )
            text = completion.choices[0].message.content.strip()
            logger.info(
                "✅ Groq [{}] responded ({} chars)", model, len(text)
            )
            return text

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str.lower():
                logger.warning(f"Groq rate limit: {e}")
                raise AIError("RATE_LIMIT")
            if "401" in error_str or "invalid_api_key" in error_str.lower():
                logger.error(f"Groq auth error: {e}")
                raise AIError("AUTH_ERROR")
            logger.error(f"Groq chat failed: {e}")
            return None

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        on_token: StreamCallback = None,
        on_complete: StreamCallback = None,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> Generator[str, None, None]:
        """
        Stream a chat response token-by-token from Groq.

        Groq natively supports streaming via the OpenAI-compatible API.
        Yields tokens as they arrive, calling on_token for each.

        Args:
            messages: Chat messages.
            system_prompt: System instruction.
            on_token: Called with each partial token.
            on_complete: Called with the full assembled response.
            model: Override model name.
            temperature: Creativity 0.0-1.0.
            max_tokens: Max response length.

        Yields:
            Partial response tokens as they become available.
        """
        if not self._available:
            return

        model = model or (cfg.ai.groq_model if cfg else AIConfig.GROQ_MODEL_FAST)
        temp = temperature or (
            cfg.ai.temperature if cfg else AIConfig.TEMPERATURE
        )
        max_tok = max_tokens or (
            cfg.ai.max_tokens if cfg else AIConfig.MAX_TOKENS
        )

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            stream = self._client.chat.completions.create(
                model=model,
                messages=full_messages,
                temperature=temp,
                max_tokens=max_tok,
                stream=True,
            )

            full_response = []
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response.append(token)
                    if on_token:
                        on_token(token)
                    yield token

            assembled = "".join(full_response)
            if on_complete:
                on_complete(assembled)
            logger.info(
                "✅ Groq stream [{}] complete ({} chars)",
                model, len(assembled),
            )

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate_limit" in error_str:
                logger.warning(f"Groq stream rate limit: {e}")
                raise AIError("RATE_LIMIT")
            logger.error(f"Groq stream failed: {e}")
            raise

    def quick_ask(self, question: str, system: str = "") -> Optional[str]:
        """Fast one-shot question."""
        return self.chat(
            [{"role": "user", "content": question}],
            system_prompt=system,
            model=(cfg.ai.groq_model if cfg else AIConfig.GROQ_MODEL_FAST),
        )

    def smart_ask(self, question: str, system: str = "") -> Optional[str]:
        """Use the larger, smarter Groq model."""
        return self.chat(
            [{"role": "user", "content": question}],
            system_prompt=system,
            model=(cfg.ai.groq_model if cfg else AIConfig.GROQ_MODEL_SMART),
        )


if __name__ == "__main__":
    from utils.logger import setup_logger
    setup_logger()

    client = GroqClient()
    if client.is_available:
        response = client.quick_ask("Say 'Groq is working!' and nothing else.")
        print(f"Response: {response}")
    else:
        print("Groq not configured. Add GROQ_API_KEY to .env")