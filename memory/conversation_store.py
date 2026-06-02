"""
memory/conversation_store.py — Conversation History Management for DREX

Provides rich conversation history management beyond raw SQL storage.
Features:
  - Message storage with metadata
  - Conversation threading (session-based)
  - Message search with relevance scoring
  - Conversation summarization foundation
  - Importance-weighted history retrieval

This sits on top of DBManager to provide semantic-rich access patterns.
"""

from datetime import datetime
from typing import Optional
from loguru import logger
from config import get_config


class ConversationStore:
    """
    Rich conversation history manager.

    Provides intelligent retrieval patterns on top of the raw
    database storage. Designed for future semantic search integration.
    """

    def __init__(self, db_manager=None):
        self.db = db_manager
        self.cfg = get_config()
        logger.info("✅ ConversationStore initialized")

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict = None,
    ):
        """Save a message with metadata to conversation history."""
        if not self.db:
            logger.warning("No database backend for ConversationStore")
            return

        meta = metadata or {}
        self.db.save_message(session_id, role, content, metadata=meta)

    def get_history(self, session_id: str, limit: int = 20) -> list[dict]:
        """Get conversation history for a session."""
        if not self.db:
            return []
        return self.db.get_history(session_id, limit=limit)

    def get_recent_context(
        self, session_id: str, limit: int = 10
    ) -> list[dict]:
        """Get recent messages formatted for AI prompt injection."""
        if not self.db:
            return []
        return self.db.get_recent_context(session_id, limit=limit)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search conversation history by content."""
        if not self.db:
            return []
        return self.db.search_history(query, limit=limit)

    def get_summary(self, session_id: str, max_messages: int = 50) -> str:
        """
        Generate a simple extractive summary of a conversation.

        This is a foundation for future AI-powered summarization.
        Currently returns key messages from the conversation.

        Args:
            session_id: Session to summarize.
            max_messages: Maximum messages to consider.

        Returns:
            A text summary of the conversation.
        """
        if not self.db:
            return ""

        try:
            history = self.db.get_history(session_id, limit=max_messages)
            if not history:
                return "No conversation history."

            user_messages = [
                m for m in history if m.get("role") == "user"
            ]
            assistant_messages = [
                m for m in history if m.get("role") == "assistant"
            ]

            summary_parts = [
                f"Total messages: {len(history)}",
                f"User messages: {len(user_messages)}",
                f"Assistant messages: {len(assistant_messages)}",
            ]

            if user_messages:
                first = user_messages[0].get("content", "")[:100]
                summary_parts.append(f"First user message: {first}...")

            if assistant_messages:
                last = assistant_messages[-1].get("content", "")[:100]
                summary_parts.append(f"Last response: {last}...")

            return " | ".join(summary_parts)
        except Exception as e:
            logger.error("Conversation summary error: {}", e)
            return "Summary unavailable."

    def shutdown(self):
        """Clean up resources."""
        logger.info("ConversationStore shutdown")