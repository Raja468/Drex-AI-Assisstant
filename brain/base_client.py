# ============================================================
#  DREX - AI Desktop Assistant
#  brain/base_client.py  —  Abstract Base AI Client
#
#  All AI providers (Gemini, Groq, OpenRouter, Cerebras)
#  inherit from this class.
#
#  This ensures consistent interfaces for:
#    - chat()           — Send messages, get full response
#    - generate()       — Legacy text prompt
#    - stream_chat()    — Streaming token-by-token response
#    - quick_ask()      — Fast one-shot question
#    - is_available     — Check if provider is configured
# ============================================================

from abc import ABC, abstractmethod
from typing import Callable, Generator, Optional

# Type alias for streaming callbacks
StreamCallback = Callable[[str], None]


class BaseAIClient(ABC):
    """
    Abstract base class for all AI provider clients.

    Each provider must implement:
      - chat()           — Full response
      - generate()       — Legacy text prompt
      - stream_chat()    — Streaming response with callbacks
      - is_available     — Property returning bool
    """

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> Optional[str]:
        """
        Send a conversation and get a full response.

        Args:
            messages: List of {"role": "user"/"assistant", "content": "..."}
            system_prompt: System-level instructions
            model: Model name override
            temperature: Creativity (0.0 to 1.0)
            max_tokens: Max response length

        Returns:
            Response text, or None if failed
        """
        ...

    @abstractmethod
    def generate(self, prompt: str, context: dict = None) -> str:
        """
        Legacy text prompt interface.

        Args:
            prompt: User's text prompt
            context: Optional context dict (e.g. {"system": "..."})

        Returns:
            Response text, or empty string if failed
        """
        ...

    @abstractmethod
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
        Stream a chat response token-by-token.

        Args:
            messages: Chat messages
            system_prompt: System instructions
            on_token: Called with each partial token
            on_complete: Called with the full assembled response
            model: Model name override
            temperature: Creativity (0.0 to 1.0)
            max_tokens: Max response length

        Yields:
            Partial response tokens
        """
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is configured and initialized."""
        ...

    def quick_ask(self, question: str, system: str = "") -> Optional[str]:
        """
        Fast one-shot question.

        Args:
            question: User's question
            system: Optional system prompt

        Returns:
            Response text or None
        """
        return self.chat(
            [{"role": "user", "content": question}],
            system_prompt=system,
        )

    def reset(self):
        """Reset any internal state. Override in subclass if needed."""
        pass