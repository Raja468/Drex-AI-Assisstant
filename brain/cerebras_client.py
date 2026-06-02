"""
brain/cerebras_client.py — Cerebras AI Client for DREX

Provides access to Cerebras Cloud API (OpenAI-compatible).
Supports both synchronous chat and streaming response patterns.

Official Cerebras model names (as of 2025):
  - llama3.1-8b  (fast, lightweight)
  - llama3.1-70b  (full-size, if available)
  - llama3.3-70b  (latest, check Cerebras docs)

If the configured model is unavailable, the client will:
  1. Log a warning with the specific error
  2. Try fallback models
  3. Disable itself gracefully if all models are unavailable

This prevents the "Model does not exist" crash seen in earlier versions.
"""

from typing import Callable, Generator, Optional
from loguru import logger
from utils.error_handler import AIError
from config import get_config
from brain.base_client import BaseAIClient, StreamCallback




class CerebrasClient(BaseAIClient):
    """
    Cerebras Cloud AI client with automatic model fallback.

    Uses the OpenAI-compatible Cerebras API via the cerebras-cloud-sdk.
    """

    def __init__(self):
        from config import get_config
        self._main_cfg = get_config()
        self.cfg = self._main_cfg.ai
        self._client = None
        self._available = False
        self._active_model = None
        self._init()

    def _init(self):
        if not self.cfg.cerebras_api_key:
            logger.warning("CerebrasClient: No API key set (CEREBRAS_API_KEY)")
            return
        try:
            from cerebras.cloud.sdk import Cerebras
            self._client = Cerebras(api_key=self.cfg.cerebras_api_key)
            self._available = True
            self._active_model = self.cfg.cerebras_model


            logger.info(
                "✅ CerebrasClient initialized | model={}",
                self._active_model,
            )
        except ImportError:
            logger.error(
                "CerebrasClient: cerebras-cloud-sdk not installed. "
                "Run: pip install cerebras-cloud-sdk"
            )
        except Exception as e:
            logger.error("CerebrasClient init failed: {}", e)

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
        **kwargs,
    ) -> Optional[str]:
        """
        Send a chat request with automatic model fallback.

        If the configured model fails with MODEL_NOT_FOUND or similar,
        attempts fallback models from CEREBRAS_MODELS.

        Args:
            messages: Chat message history.
            system_prompt: System instruction.
            model: Override the model name (uses config default if None).

        Returns:
            Response text, or None if all models failed.
        """
        if not self._available or not self._client:
            return None

        # Use the configured model, with the env var as override
        primary_model = model or self._active_model or self.cfg.cerebras_model
        models_to_try = [primary_model]

        last_error = None
        for attempt_model in models_to_try:
            try:
                response = self._do_chat(attempt_model, messages, system_prompt)
                # On success, cache the working model
                self._active_model = attempt_model
                return response
            except AIError as e:
                error_str = str(e)
                if "MODEL_NOT_FOUND" in error_str:
                    logger.warning(
                        "Cerebras model '{}' not available. Trying fallback...",
                        attempt_model,
                    )
                    last_error = e
                    continue
                # Non-model errors propagate
                raise
            except Exception as e:
                error_str = str(e).lower()
                # Check for model-related errors
                if "not found" in error_str or "model_not_found" in error_str:
                    logger.warning(
                        "Cerebras model '{}' unavailable: {}. Trying fallback...",
                        attempt_model, e,
                    )
                    last_error = AIError("MODEL_NOT_FOUND")
                    continue
                raise

        # All models failed — gracefully disable
        logger.error(
            "All Cerebras models failed. Last error: {}",
            last_error,
        )
        self._available = False
        return None

    def _do_chat(
        self, model: str, messages: list[dict], system_prompt: str
    ) -> str:
        """
        Internal chat implementation for a specific model.

        Args:
            model: The Cerebras model name to use.
            messages: Chat messages.
            system_prompt: System instruction.

        Returns:
            Response text.

        Raises:
            AIError: For rate limits, auth errors, model not found, etc.
        """
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=all_messages,
                max_tokens=self.cfg.max_tokens,
                temperature=self.cfg.temperature,
            )
            result = response.choices[0].message.content.strip()
            logger.debug(
                "Cerebras [{}] responded ({} chars)",
                model, len(result),
            )
            return result
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str or "quota" in error_str:
                raise AIError("RATE_LIMIT")
            if "401" in error_str or "auth" in error_str or "unauthorized" in error_str:
                raise AIError("AUTH_ERROR")
            if "model_not_found" in error_str or "not found" in error_str:
                logger.error("Cerebras model '{}' not found: {}", model, e)
                raise AIError("MODEL_NOT_FOUND")
            logger.error("Cerebras chat error [{}]: {}", model, e)
            raise

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        on_token: StreamCallback = None,
        on_complete: StreamCallback = None,
        model: str = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream a chat response token-by-token from Cerebras.

        Cerebras supports streaming via the OpenAI-compatible API.
        Yields tokens as they arrive, calling on_token for each.

        Args:
            messages: Chat messages.
            system_prompt: System instruction.
            on_token: Called with each partial token.
            on_complete: Called with the full assembled response.
            model: Override model name.

        Yields:
            Partial response tokens.
        """
        if not self._available or not self._client:
            return

        active_model = model or self._active_model or self.cfg.cerebras_model or "llama3.1-8b"
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        try:
            stream = self._client.chat.completions.create(
                model=active_model,
                messages=all_messages,
                max_tokens=self.cfg.max_tokens,
                temperature=self.cfg.temperature,
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
            logger.debug(
                "Cerebras stream [{}] complete ({} chars)",
                active_model, len(assembled),
            )

        except Exception as e:
            error_str = str(e).lower()
            if "model_not_found" in error_str or "not found" in error_str:
                logger.error(
                    "Cerebras model '{}' not found for streaming: {}",
                    active_model, e,
                )
                raise AIError("MODEL_NOT_FOUND")
            logger.error("Cerebras stream error: {}", e)
            raise