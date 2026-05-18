# ============================================================
#  DREX - AI Desktop Assistant
#  brain/gemini_client.py  —  Google Gemini API Client
#  Uses NEW google-genai SDK: pip install google-genai
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
    GEMINI_API_KEY = cfg.ai.gemini_api_key
except ImportError:
    GEMINI_API_KEY = ""
    AIModels = None
    cfg = None
    class AIConfig:
        MAX_TOKENS = 1024
        TEMPERATURE = 0.7

if AIModels is None:
    class AIModels:
        GEMINI_FLASH = "gemini-1.5-flash"


class GeminiClient:
    """Wrapper for Google Gemini API using the new google-genai SDK."""

    def __init__(self):
        self._client = None
        self._available = False
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

        model   = model       or AIModels.GEMINI_FLASH
        temp    = temperature or (cfg.ai.temperature if cfg else AIConfig.TEMPERATURE)
        max_tok = max_tokens  or (cfg.ai.max_tokens if cfg else AIConfig.MAX_TOKENS)

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
                raise AIError("RATE_LIMIT")
            if "api_key" in error_str or "401" in error_str or "403" in error_str:
                raise AIError("AUTH_ERROR")
            logger.error(f"Gemini chat failed: {e}")
            return None

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
