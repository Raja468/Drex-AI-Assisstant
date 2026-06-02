"""
core/task_dispatcher.py — Simplified Task Dispatch Facade

This module is a compatibility facade that delegates to the
Orchestrator's dispatch system. Previously this module duplicated
routing logic — now it's a thin wrapper that preserves the API
for any code that imports TaskDispatcher directly.

The single source of truth for dispatch logic is now Orchestrator.process().
"""

from datetime import datetime
from typing import Optional
from utils.logger import logger
from core.intent_parser import Intent


class TaskDispatcher:
    """
    Task dispatch facade (DEPRECATED — use Orchestrator.process()).

    Preserved for backward compatibility. All dispatch logic
    now lives in core.orchestrator.Orchestrator.process().
    """

    def __init__(
        self,
        task_handler=None,
        ai_router=None,
        memory=None,
        speaker=None,
    ):
        self.task_handler = task_handler
        self.ai_router = ai_router
        self.memory = memory
        self.speaker = speaker
        self._session_id = self._generate_session_id()
        logger.info(
            "✅ TaskDispatcher ready (compat mode) | Session: {}...",
            self._session_id[:12],
        )

    @staticmethod
    def _generate_session_id() -> str:
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def dispatch(self, intent: Intent) -> str:
        """
        Route an intent to the correct handler.

        Delegates to the appropriate handler based on intent type.
        This is kept for backward compatibility.
        """
        logger.debug("Dispatching: {}:{}", intent.type, intent.sub_type)

        if intent.type == "system":
            return self._dispatch_system(intent)
        elif intent.type == "automation":
            return self._dispatch_automation(intent)
        elif intent.type == "memory":
            return self._dispatch_memory(intent)
        elif intent.type == "conversation":
            return self._dispatch_conversation(intent)
        else:
            return "I'm not sure how to help with that."

    def _dispatch_system(self, intent: Intent) -> str:
        sub = intent.sub_type

        if sub == "greeting":
            return self._get_greeting()
        if sub == "farewell":
            return "Goodbye! Have a great day!"
        if sub == "thanks":
            import random
            return random.choice([
                "You're welcome! Anything else?",
                "Happy to help! What else can I do?",
                "Of course! Let me know if you need anything.",
            ])

        if sub in ("shutdown", "volume_up", "volume_down", "mute",
                   "screenshot", "lock", "sleep", "restart", "system_info"):
            if self.task_handler:
                return self.task_handler.handle_system_action(sub, intent)
            return f"System command '{sub}' not available."

        return f"System command '{sub}' not yet implemented."

    def _dispatch_automation(self, intent: Intent) -> str:
        if self.task_handler:
            return self.task_handler.handle(intent)
        return "Automation module not available."

    def _dispatch_memory(self, intent: Intent) -> str:
        if not self.memory:
            return "Memory system not available."
        return f"Memory operation received for: {intent.raw[:80]}"

    def _dispatch_conversation(self, intent: Intent) -> str:
        sub = intent.sub_type

        if sub == "greeting":
            return self._get_greeting()
        if sub == "thanks":
            import random
            return random.choice([
                "You're welcome!", "Happy to help!", "Of course!"
            ])

        if self.ai_router:
            return self.ai_router.route(
                user_input=intent.raw,
                session_id=self._session_id,
                intent=intent,
            )
        return "AI integration not available. Add API keys to .env."

    def _get_greeting(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            time_of_day = "morning"
        elif hour < 17:
            time_of_day = "afternoon"
        else:
            time_of_day = "evening"

        name = ""
        if self.memory:
            stored_name = self.memory.get_preference("user_name")
            if stored_name:
                name = f", {stored_name}"

        return f"Good {time_of_day}{name}! How can I help you today?"