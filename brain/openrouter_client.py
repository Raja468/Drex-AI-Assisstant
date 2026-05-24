# ============================================================
#  DREX - AI Desktop Assistant
#  brain/openrouter_client.py  —  OpenRouter API Client
#
#  WHAT IS OPENROUTER:
#  A single API that gives access to 100+ AI models,
#  including many completely FREE models.
#
#  FREE MODELS AVAILABLE:
#  - meta-llama/llama-3.1-8b-instruct:free
#  - mistralai/mistral-7b-instruct:free
#  - google/gemma-2-9b-it:free
#  - microsoft/phi-3-mini-128k-instruct:free
#
#  Get key at: https://openrouter.ai
# ============================================================

import requests
import json
import time
from typing import Optional
from utils.logger import logger
from utils.error_handler import AIError

try:
    from config import get_config
    try:
        from config import AIModels
    except ImportError:
        AIModels = None
    cfg = get_config()
    OPENROUTER_API_KEY = cfg.ai.openrouter_api_key
except ImportError:
    OPENROUTER_API_KEY = ""
    AIModels = None
    cfg = None
    class AIConfig:
        MAX_TOKENS  = 1024
        TEMPERATURE = 0.7

if AIModels is None:
    class AIModels:
        OPENROUTER_MISTRAL = "mistralai/mistral-7b-instruct:free"
        OPENROUTER_LLAMA   = "meta-llama/llama-3.1-8b-instruct:free"
        OPENROUTER_GEMMA   = "google/gemma-2-9b-it:free"

OPENROUTER_BASE_URL = "https://api.openrouter.ai/v1/chat/completions"


class OpenRouterClient:
    """
    Wrapper for the OpenRouter API.
    Provides access to many free AI models through a single interface.
    """

    def __init__(self):
        self._available = False
        self._headers = {}
        self._init()

    def _init(self) -> None:
        if not OPENROUTER_API_KEY:
            logger.warning("⚠️ OPENROUTER_API_KEY not set. OpenRouter unavailable.")
            return

        self._headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://drex-assistant.local",
            "X-Title":       "Drex AI Assistant",
        }
        self._available = True
        logger.info("✅ OpenRouterClient initialized")

    @property
    def is_available(self) -> bool:
        return self._available

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> Optional[str]:
        """
        Send a conversation to OpenRouter and get a response.

        Args:
            messages:      List of {"role": "user"/"assistant", "content": "..."}
            system_prompt: System instructions
            model:         Model name (any OpenRouter model)
            temperature:   Creativity 0.0-1.0
            max_tokens:    Max response length

        Returns:
            Response text, or None if failed
        """
        if not self._available:
            return None

        model   = model       or AIModels.OPENROUTER_MISTRAL
        temp    = temperature or (cfg.ai.temperature if cfg else AIConfig.TEMPERATURE)
        max_tok = max_tokens  or (cfg.ai.max_tokens if cfg else AIConfig.MAX_TOKENS)

        # Build full messages list with system prompt
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model":       model,
            "messages":    full_messages,
            "temperature": temp,
            "max_tokens":  max_tok,
        }

        # Retry with backoff for transient failures (DNS, connection, timeouts)
        max_retries = 2
        last_error = None
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    OPENROUTER_BASE_URL,
                    headers=self._headers,
                    json=payload,
                    timeout=30
                )

                if response.status_code == 429:
                    logger.warning("OpenRouter rate limit hit")
                    raise AIError("RATE_LIMIT")

                if response.status_code in (401, 403):
                    logger.error("OpenRouter auth error — check API key")
                    raise AIError("AUTH_ERROR")

                response.raise_for_status()
                data = response.json()

                text = data["choices"][0]["message"]["content"].strip()
                logger.info(f"✅ OpenRouter [{model}] responded ({len(text)} chars)")
                return text

            except AIError:
                raise
            except requests.exceptions.ConnectionError as e:
                logger.warning(
                    "OpenRouter connection error (attempt {}/{}): {}",
                    attempt + 1, max_retries, e
                )
                last_error = AIError("CONNECTION_ERROR")
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))  # linear backoff
                    continue
            except requests.Timeout as e:
                logger.warning(
                    "OpenRouter timeout (attempt {}/{}): {}",
                    attempt + 1, max_retries, e
                )
                last_error = AIError("TIMEOUT_ERROR")
                if attempt < max_retries - 1:
                    time.sleep(1.0)
                    continue
            except Exception as e:
                logger.error(f"OpenRouter chat failed: {e}")
                return None

        # All retries exhausted
        if isinstance(last_error, AIError):
            raise last_error
        return None

    def quick_ask(self, question: str, system: str = "") -> Optional[str]:
        """Fast one-shot question using a small free model."""
        return self.chat(
            [{"role": "user", "content": question}],
            system_prompt=system,
            model=AIModels.OPENROUTER_MISTRAL,
        )


# ─────────────────────────────────────────────────────────────
#  QUICK TEST
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from utils.logger import setup_logger
    setup_logger()

    client = OpenRouterClient()
    if client.is_available:
        response = client.quick_ask("Say 'OpenRouter is working!' and nothing else.")
        print(f"Response: {response}")
    else:
        print("OpenRouter not configured. Add OPENROUTER_API_KEY to .env")