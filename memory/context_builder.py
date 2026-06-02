"""
memory/context_builder.py — Conversation Context Builder for DREX

Builds context for AI prompts by aggregating:
  - Recent conversation history (smart window)
  - User preferences / profile
  - Stored facts
  - Session summary (if available)

Architecture:
  - Sliding window of last N messages (configurable via DREX_MAX_HISTORY)
  - Importance scoring for memory retention (higher score = retained longer)
  - Automatic session summarization on shutdown
"""

import json
import time
from datetime import datetime
from typing import Optional
from loguru import logger
from config import get_config


class ContextBuilder:
    """
    Builds conversation context for AI prompts.

    Manages sliding window of recent history and integrates
    stored facts, preferences, and session summaries.
    """

    def __init__(self, memory_manager=None):
        self.cfg = get_config()
        self.memory = memory_manager
        self._max_history = self.cfg.ai.max_history
        self._session_summary: Optional[str] = None
        self._topic_tracker: dict[str, int] = {}  # topic -> mention count
        logger.debug("ContextBuilder initialized | max_history={}", self._max_history)

    def set_memory(self, memory_manager):
        """Set or update the memory manager reference."""
        self.memory = memory_manager

    def build_context(
        self,
        user_input: str,
        session_id: str = "default",
        task_type: str = "general",
        extra_context: str = "",
    ) -> dict:
        """
        Build a complete context dict for the AI prompt.

        Args:
            user_input: The user's current input text.
            session_id: Current session identifier.
            task_type: Type of task (general, coding, fast, etc.).
            extra_context: Additional context (e.g., automation results).

        Returns:
            dict with 'system', 'messages', and metadata keys.
        """
        system_parts = []

        # 1. Personality instructions
        personality = self._get_personality_instructions()
        if personality:
            system_parts.append(personality)

        # 2. User preferences / profile
        if self.memory:
            prefs = self.memory.get_all_preferences()
            user_name = prefs.get("user_name", "")
            if user_name:
                system_parts.append(f"The user's name is {user_name}.")
        else:
            user_name = ""

        # 3. Stored facts (context-relevant)
        facts = self._get_relevant_facts(user_input) if self.memory else []
        if facts:
            fact_text = "\n".join(f"- {f['key']}: {f['value']}" for f in facts[:5])
            system_parts.append(f"Known facts:\n{fact_text}")

        # 4. Session summary (if available)
        if self._session_summary:
            system_parts.append(f"Session context: {self._session_summary}")

        # 5. Extra context
        if extra_context:
            system_parts.append(f"Additional context: {extra_context}")

        # 6. Task-specific instructions
        task_instructions = self._get_task_instructions(task_type)
        if task_instructions:
            system_parts.append(task_instructions)

        system_prompt = "\n\n".join(system_parts) if system_parts else (
            "You are DREX, an AI desktop assistant. "
            "Respond helpfully and conversationally."
        )

        # 7. Messages (sliding window)
        messages = self._build_messages(user_input, session_id)

        # Track topics for importance scoring
        self._track_topics(user_input)

        return {
            "system": system_prompt,
            "messages": messages,
            "personality": personality or "default",
            "user_name": user_name,
        }

    def _build_messages(self, user_input: str, session_id: str) -> list[dict]:
        """
        Build conversation messages from recent history + current input.

        Uses a sliding window of the last N messages to prevent
        token overflow while maintaining conversation coherence.
        """
        messages = []

        if self.memory:
            # Get recent conversation history (last N exchanges)
            history = self.memory.get_recent_history(
                session_id, limit=self._max_history
            )
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        # Add current user input
        messages.append({"role": "user", "content": user_input})

        return messages

    def _get_relevant_facts(self, user_input: str) -> list[dict]:
        """
        Get facts relevant to the current user input.

        Simple keyword matching for now — can be upgraded to
        vector similarity search for semantic memory.
        """
        if not self.memory:
            return []

        all_facts = self.memory.get_facts()
        if not all_facts:
            return []

        input_lower = user_input.lower()
        scored_facts = []

        for fact in all_facts:
            key = fact.get("key", "").lower()
            value = fact.get("value", "").lower()
            score = 0
            if key in input_lower or value in input_lower:
                score += 2
            # Check each word in the fact key
            for word in key.split():
                if word in input_lower and len(word) > 2:
                    score += 1
            if score > 0:
                scored_facts.append((score, fact))

        # Return highest-scoring facts
        scored_facts.sort(key=lambda x: -x[0])
        return [f for _, f in scored_facts[:5]]

    def _get_personality_instructions(self) -> str:
        """Get system instructions for the current personality mode."""
        if not self.memory:
            return ""
        mode = self.memory.get_preference("personality_mode", "jarvis")

        personalities = {
            "jarvis": (
                "You are JARVIS — an AI butler. "
                "You are calm, precise, efficient, and well-spoken. "
                "Use proper grammar and speak with quiet confidence. "
                "Address the user respectfully and concisely."
            ),
            "friendly": (
                "You are a friendly AI assistant. "
                "You are warm, enthusiastic, and supportive. "
                "Use emojis occasionally. Be approachable and kind."
            ),
            "hacker": (
                "You are a cyberpunk-style AI. "
                "You speak in a technical, edgy tone. "
                "Use symbols like >> and | in responses. "
                "Be direct and efficient like a computer system."
            ),
            "calm": (
                "You are a calm, mindful AI assistant. "
                "You speak softly and thoughtfully. "
                "Keep responses simple and peaceful."
            ),
        }
        return personalities.get(mode, personalities["jarvis"])

    def _get_task_instructions(self, task_type: str) -> str:
        """Get task-specific system instructions."""
        instructions = {
            "coding": (
                "Provide code examples when relevant. "
                "Use markdown code blocks with language tags."
            ),
            "fast": (
                "Keep responses brief and direct. "
                "One paragraph maximum unless code is needed."
            ),
            "reasoning": (
                "Think step by step. "
                "Break down complex problems into clear parts."
            ),
            "creative": (
                "Be creative and expressive. "
                "Use rich language and vivid descriptions."
            ),
        }
        return instructions.get(task_type, "")

    def _track_topics(self, user_input: str):
        """Track mentioned topics for importance scoring."""
        # Simple keyword frequency tracking
        important_words = [
            "remember", "important", "favorite", "love", "hate",
            "always", "never", "project", "work", "study",
        ]
        input_lower = user_input.lower()
        for word in important_words:
            if word in input_lower:
                self._topic_tracker[word] = self._topic_tracker.get(word, 0) + 1

    def get_topic_summary(self) -> str:
        """Get a summary of frequently discussed topics."""
        if not self._topic_tracker:
            return ""
        sorted_topics = sorted(
            self._topic_tracker.items(), key=lambda x: -x[1]
        )[:5]
        topics = ", ".join(f"{t} ({c}x)" for t, c in sorted_topics)
        return f"Frequent topics: {topics}."

    def generate_session_summary(
        self, session_id: str, conversation: list[dict]
    ) -> str:
        """
        Generate a concise session summary from conversation history.

        Args:
            session_id: Session identifier.
            conversation: List of message dicts from this session.

        Returns:
            A brief summary string.
        """
        if not conversation:
            return ""

        # Extract key information
        user_messages = [m for m in conversation if m.get("role") == "user"]
        ai_messages = [m for m in conversation if m.get("role") == "assistant"]

        if not user_messages:
            return ""

        # Build a summary from:
        # - Number of exchanges
        # - Key topics from the topic tracker
        # - First user message (context)
        exchange_count = len(user_messages)
        first_topic = user_messages[0].get("content", "")[:80]
        topic_info = self.get_topic_summary()

        summary_parts = [
            f"{exchange_count} exchange(s).",
            f"Started with: '{first_topic}'",
        ]
        if topic_info:
            summary_parts.append(topic_info)

        self._session_summary = " | ".join(summary_parts)

        # Store summary in memory
        if self.memory:
            try:
                self.memory.save_fact(
                    "session_summary",
                    f"session_{session_id}",
                    self._session_summary,
                )
            except Exception:
                pass

        logger.info("Session summary generated: {}", self._session_summary)
        return self._session_summary

    def get_importance_score(self, user_input: str) -> float:
        """
        Calculate an importance score (0.0-1.0) for a user input.

        Higher scores indicate content that should be remembered longer.
        Factors:
          - Contains explicit memory commands
          - Mentions user identity (name, preferences)
          - Contains important keywords
          - Is part of a frequently discussed topic
        """
        score = 0.0
        input_lower = user_input.lower()

        # Explicit memory commands
        if any(phrase in input_lower for phrase in [
            "remember", "don't forget", "save this", "my name is"
        ]):
            score += 0.4

        # Identity statements
        if any(phrase in input_lower for phrase in [
            "i am", "i'm", "my name", "i like", "i love", "i hate"
        ]):
            score += 0.2

        # Important keywords
        important = ["project", "deadline", "important", "urgent", "favorite"]
        if any(w in input_lower for w in important):
            score += 0.2

        # Repeated topics (frequently discussed)
        for topic, count in self._topic_tracker.items():
            if topic in input_lower and count > 2:
                score += 0.1

        return min(score, 1.0)

    def reset(self):
        """Reset context builder state."""
        self._session_summary = None
        self._topic_tracker = {}
        logger.debug("ContextBuilder reset")