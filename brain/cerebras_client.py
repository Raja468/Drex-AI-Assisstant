# ============================================================
#  DREX - AI Desktop Assistant
#  brain/cerebras_client.py  —  Cerebras AI Client
#
#  Model: llama-3.3-70b  (same as Groq but 20x faster)
#  API:   OpenAI-compatible
#  Free:  Yes — cloud.cerebras.ai
# ============================================================

from loguru import logger
from config import get_config


class CerebrasClient:
    def __init__(self):
        self.cfg = get_config().ai
        self._client = None
        self.is_available = False
        self._init()

    def _init(self):
        if not self.cfg.cerebras_api_key:
            logger.warning("CerebrasClient: No API key set (CEREBRAS_API_KEY)")
            return
        try:
            from cerebras.cloud.sdk import Cerebras
            self._client = Cerebras(api_key=self.cfg.cerebras_api_key)
            self.is_available = True
            logger.info("✅ CerebrasClient initialized (llama-3.3-70b)")
        except ImportError:
            logger.error("CerebrasClient: cerebras-cloud-sdk not installed. Run: pip install cerebras-cloud-sdk")
        except Exception as e:
            logger.error("CerebrasClient init failed: {}", e)

    def chat(self, messages: list[dict], system_prompt: str = "") -> str:
        if not self.is_available or not self._client:
            raise RuntimeError("Cerebras client not available")

        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        try:
            response = self._client.chat.completions.create(
                model=self.cfg.cerebras_model,
                messages=all_messages,
                max_tokens=self.cfg.max_tokens,
                temperature=self.cfg.temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Cerebras chat error: {}", e)
            raise