# ============================================================
#  DREX - AI Desktop Assistant
#  brain/groq_client.py  —  Groq API Client
#
#  FREE TIER LIMITS (as of 2024):
#  - 14,400 requests/day free
#  - Ultra-fast inference (LPU chips) — often <1 second!
#  - Get key at: https://console.groq.com
# ============================================================

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
    GROQ_API_KEY = cfg.ai.groq_api_key
except ImportError:
    GROQ_API_KEY = ""
    AIModels = None
    cfg = None
    class AIConfig:
        MAX_TOKENS  = 1024
        TEMPERATURE = 0.7

if AIModels is None:
    class AIModels:
        GROQ_LLAMA_FAST  = "llama-3.1-8b-instant"
        GROQ_LLAMA_SMART = "llama-3.3-70b-versatile"


class GroqClient:
    """
    Wrapper for the Groq API.
    Groq is used for FAST responses — nearly instant even for large models.
    Perfect for Drex's quick-answer mode.
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

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> Optional[str]:
        """
        Send a conversation to Groq and get a response.

        Args:
            messages:      List of {"role": "user"/"assistant", "content": "..."}
            system_prompt: System instructions
            model:         Model name (default: llama-3.1-8b-instant)
            temperature:   Creativity 0.0-1.0
            max_tokens:    Max response length

        Returns:
            Response text, or None if failed
        """
        if not self._available:
            return None

        model   = model       or AIModels.GROQ_LLAMA_FAST
        temp    = temperature or (cfg.ai.temperature if cfg else AIConfig.TEMPERATURE)
        max_tok = max_tokens  or (cfg.ai.max_tokens if cfg else AIConfig.MAX_TOKENS)

        # Prepend system message (Groq uses OpenAI-compatible format)
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
            logger.info(f"✅ Groq [{model}] responded ({len(text)} chars)")
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

    def quick_ask(self, question: str, system: str = "") -> Optional[str]:
        """Fast one-shot question."""
        return self.chat(
            [{"role": "user", "content": question}],
            system_prompt=system,
            model=AIModels.GROQ_LLAMA_FAST,
        )

    def smart_ask(self, question: str, system: str = "") -> Optional[str]:
        """Use the larger, smarter Groq model."""
        return self.chat(
            [{"role": "user", "content": question}],
            system_prompt=system,
            model=AIModels.GROQ_LLAMA_SMART,
        )


# ─────────────────────────────────────────────────────────────
#  QUICK TEST
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from utils.logger import setup_logger
    setup_logger()

    client = GroqClient()
    if client.is_available:
        response = client.quick_ask("Say 'Groq is working!' and nothing else.")
        print(f"Response: {response}")
    else:
        print("Groq not configured. Add GROQ_API_KEY to .env")
