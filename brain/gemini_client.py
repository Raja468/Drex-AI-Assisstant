# ============================================================
#  DREX - AI Desktop Assistant
#  brain/gemini_client.py  —  Google Gemini API Client
#  Uses NEW google-genai SDK: pip install google-genai
# ============================================================

import time
import random
from typing import Callable, Generator, Optional
from utils.logger import logger
from utils.error_handler import AIError
from brain.base_client import BaseAIClient, StreamCallback

try:
    from config import get_config
    cfg = get_config()
    GEMINI_API_KEY = cfg.ai.gemini_api_key
except ImportError:
    GEMINI_API_KEY = ""
    cfg = None
    class AIConfig:
        MAX_TOKENS = 1024
        TEMPERATURE = 0.7
        GEMINI_MODEL = "gemini-2.0-flash"


class GeminiClient(BaseAIClient):
    """Wrapper for Google Gemini API using the new google-genai SDK."""

    def __init__(self):
        self._client = None
        self._available = False
        self._active_model = None
        self._init()

    def _init(self) -> None:
        if not GEMINI_API_KEY:
            logger.warning("⚠️  GEMINI_API_KEY not set. Gemini unavailable.")
            return
        try:
            from google import genai
            self._client = genai.Client(api_key=GEMINI_API_KEY)
            self._genai = genai
            self._available = True
            self._active_model = cfg.ai.gemini_model if cfg else AIConfig.GEMINI_MODEL
            logger.info("✅ GeminiClient initialized (google-genai SDK)")
        except ImportError:
            logger.warning("google-genai not installed. Run: pip install google-genai")
        except Exception as e:
            logger.error(f"Gemini init failed: {e}")

    @property
    def is_available(self) -> bool:
        return self._available

    def chat(
        self,
        messages: list,
        system_prompt: str = "",
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> Optional[str]:
        if not self._available:
            return None

        model   = model       or (cfg.ai.gemini_model if cfg else AIConfig.GEMINI_MODEL)
        temp    = temperature or (cfg.ai.temperature if cfg else AIConfig.TEMPERATURE)
        max_tok = max_tokens  or (cfg.ai.max_tokens if cfg else AIConfig.MAX_TOKENS)

        # Retry with exponential backoff for rate limits and transient errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                from google.genai import types

                contents = []
                for msg in messages:
                    role = "model" if msg["role"] == "assistant" else "user"
                    contents.append(
                        types.Content(
                            role=role,
                            parts=[types.Part(text=msg["content"])]
                        )
                    )

                config = types.GenerateContentConfig(
                    temperature=temp,
                    max_output_tokens=max_tok,
                    system_instruction=system_prompt if system_prompt else None,
                )

                response = self._client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )

                text = response.text.strip()
                logger.info(f"✅ Gemini [{model}] responded ({len(text)} chars)")
                return text

            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "rate" in error_str:
                    if attempt < max_retries - 1:
                        wait = (2 ** attempt) + random.uniform(0, 1)  # exp backoff + jitter
                        logger.warning(
                            "Gemini rate limited (attempt {}/{}). Retrying in {:.1f}s...",
                            attempt + 1, max_retries, wait
                        )
                        time.sleep(wait)
                        continue
                    raise AIError("RATE_LIMIT")
                if "api_key" in error_str or "401" in error_str or "403" in error_str:
                    raise AIError("AUTH_ERROR")
                # Non-retryable or final attempt error
                if attempt < max_retries - 1 and any(
                    t in error_str for t in ["deadline_exceeded", "unavailable", "internal"]
                ):
                    wait = (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "Gemini transient error (attempt {}/{}). Retrying in {:.1f}s...",
                        attempt + 1, max_retries, wait
                    )
                    time.sleep(wait)
                    continue
                logger.error(f"Gemini chat failed: {e}")
                return None

        logger.error("Gemini exhausted all retries")
        return None

    def generate(self, prompt: str, context: dict = None) -> str:
        """Legacy text prompt interface — delegates to chat()."""
        result = self.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=(context or {}).get("system", ""),
        )
        return result or ""

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
        Stream a chat response token-by-token from Gemini.

        Uses the Google genai SDK's streaming support.
        Yields tokens as they arrive.

        Args:
            messages: Chat messages.
            system_prompt: System instruction.
            on_token: Called with each partial token.
            on_complete: Called with the full assembled response.
            model: Override model name.
            temperature: Creativity 0.0-1.0.
            max_tokens: Max response length.

        Yields:
            Partial response tokens.
        """
        if not self._available:
            return

        model = model or self._active_model or (cfg.ai.gemini_model if cfg else AIConfig.GEMINI_MODEL)
        temp = temperature or (
            cfg.ai.temperature if cfg else AIConfig.TEMPERATURE
        )
        max_tok = max_tokens or (
            cfg.ai.max_tokens if cfg else AIConfig.MAX_TOKENS
        )

        try:
            from google.genai import types

            contents = []
            for msg in messages:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=msg["content"])],
                    )
                )

            config = types.GenerateContentConfig(
                temperature=temp,
                max_output_tokens=max_tok,
                system_instruction=system_prompt if system_prompt else None,
            )

            stream = self._client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )

            full_response = []
            for chunk in stream:
                if chunk.text:
                    token = chunk.text
                    full_response.append(token)
                    if on_token:
                        on_token(token)
                    yield token

            assembled = "".join(full_response)
            if on_complete:
                on_complete(assembled)
            logger.info(
                "✅ Gemini stream [{}] complete ({} chars)",
                model, len(assembled),
            )

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "rate" in error_str:
                raise AIError("RATE_LIMIT")
            if "api_key" in error_str or "401" in error_str or "403" in error_str:
                raise AIError("AUTH_ERROR")
            logger.error(f"Gemini stream failed: {e}")
            raise

    def quick_ask(self, question: str, system: str = "") -> Optional[str]:
        return self.chat([{"role": "user", "content": question}], system_prompt=system)


if __name__ == "__main__":
    from utils.logger import setup_logger
    setup_logger()
    client = GeminiClient()
    if client.is_available:
        print(client.quick_ask("Say exactly: Gemini is working!"))
    else:
        print("Add GEMINI_API_KEY to .env")
