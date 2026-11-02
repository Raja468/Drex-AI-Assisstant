"""
voice/conversation_mode.py - Continuous voice-chat helper.

This is a thin facade over :class:`VoiceManager.start_conversation`
kept as its own module for clarity and to satisfy the Sprint-4 layout.
"""

from __future__ import annotations

from typing import Callable, Optional

from loguru import logger

from voice.voice_manager import VoiceManager


class ConversationMode:
    """
    Wraps a :class:`VoiceManager` and exposes ``start`` / ``stop``.
    The actual loop lives in :meth:`VoiceManager._conversation_loop`.
    """

    def __init__(self, manager: VoiceManager):
        self._mgr = manager

    def start(
        self,
        on_user_text: Callable[[str], str],
        on_assistant_text: Optional[Callable[[str], None]] = None,
    ) -> bool:
        logger.info("Entering conversation mode")
        return self._mgr.start_conversation(on_user_text, on_assistant_text)

    def stop(self) -> None:
        logger.info("Leaving conversation mode")
        self._mgr.stop_conversation()

    @property
    def is_active(self) -> bool:
        return self._mgr.is_in_conversation
