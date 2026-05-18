# ============================================================
#  DREX - AI Desktop Assistant
#  core/task_dispatcher.py  —  Complete Task Router
#
#  WHAT IT DOES:
#  Takes a parsed Intent from IntentParser and routes it to
#  the correct handler:
#    - Automation intents → TaskHandler (automation module)
#    - System intents → SystemControl
#    - Conversation/AI intents → AIRouter
#    - Memory intents → MemoryManager
#
#  This keeps the Orchestrator clean — it just calls dispatch()
#  and gets back a response string.
# ============================================================

from datetime import datetime
from typing import Optional
from utils.logger import logger
from core.intent_parser import Intent


class TaskDispatcher:
    """
    Central dispatcher that connects intents to implementations.
    All handler modules are injected via constructor (dependency injection).
    """

    def __init__(
        self,
        task_handler=None,
        ai_router=None,
        memory=None,
        speaker=None,
    ):
        self.task_handler = task_handler    # automation.task_handler.TaskHandler
        self.ai_router    = ai_router       # brain.ai_router.AIRouter
        self.memory       = memory          # memory.db_manager.MemoryManager
        self.speaker      = speaker         # voice.speaker.Speaker

        self._session_id  = self._generate_session_id()
        self._confirm_shutdown = False      # Tracks shutdown confirmation state

        logger.info(f"✅ TaskDispatcher ready | Session: {self._session_id[:12]}...")

    @staticmethod
    def _generate_session_id() -> str:
        """Generate a unique session ID based on start time."""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # ──────────────────────────────────────────────────────────
    #  MAIN DISPATCH METHOD
    # ──────────────────────────────────────────────────────────

    def dispatch(self, intent: Intent) -> str:
        """
        Route an intent to the correct handler.

        Args:
            intent: Parsed Intent object from IntentParser

        Returns:
            Response string to speak/display to user
        """
        logger.debug(f"Dispatching: {intent.type}:{intent.sub_type}")

        # Save user message to memory
        self._save_user_input(intent.raw, intent.type)

        # Route based on intent type
        if intent.type == "system":
            response = self._dispatch_system(intent)
        elif intent.type == "automation":
            response = self._dispatch_automation(intent)
        elif intent.type == "memory":
            response = self._dispatch_memory(intent)
        elif intent.type == "conversation":
            response = self._dispatch_conversation(intent)
        else:
            response = self._dispatch_unknown(intent)

        # Save Drex's response to memory
        self._save_assistant_response(response, intent.type)

        return response

    # ──────────────────────────────────────────────────────────
    #  SYSTEM INTENT HANDLERS
    # ──────────────────────────────────────────────────────────

    def _dispatch_system(self, intent: Intent) -> str:
        sub = intent.sub_type
        text = intent.raw.lower()

        # ── Conversational responses (no external module needed) ──
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

        if sub == "help":
            return self._get_help_text()

        # ── Shutdown confirmation flow ─────────────────────────
        if sub == "shutdown":
            self._confirm_shutdown = True
            return "Are you sure you want to shut down? Say 'yes confirm shutdown' to proceed."

        if "yes confirm shutdown" in text and self._confirm_shutdown:
            self._confirm_shutdown = False
            if self.task_handler:
                return self.task_handler.handle_system_action("confirm_shutdown", intent)
            return "Shutdown triggered."

        if "cancel" in text and self._confirm_shutdown:
            self._confirm_shutdown = False
            return "Shutdown cancelled."

        # ── System actions via TaskHandler ────────────────────
        SYSTEM_ACTIONS = [
            "volume_up", "volume_down", "mute", "screenshot",
            "lock", "sleep", "restart", "system_info",
            "clipboard_read", "cancel_shutdown"
        ]

        if sub in SYSTEM_ACTIONS and self.task_handler:
            return self.task_handler.handle_system_action(sub, intent)

        return f"System command '{sub}' not yet implemented."

    # ──────────────────────────────────────────────────────────
    #  AUTOMATION INTENT HANDLERS
    # ──────────────────────────────────────────────────────────

    def _dispatch_automation(self, intent: Intent) -> str:
        if self.task_handler:
            return self.task_handler.handle(intent)

        # Fallback if TaskHandler not loaded
        return "Automation module not available."

    # ──────────────────────────────────────────────────────────
    #  MEMORY INTENT HANDLERS
    # ──────────────────────────────────────────────────────────

    def _dispatch_memory(self, intent: Intent) -> str:
        if not self.memory:
            return "Memory system not available yet."

        text = intent.raw.lower()

        # "What's my name?" / "Do you know my name?"
        if "name" in text:
            name = self.memory.preferences.get("user_name")
            if name:
                return f"Your name is {name}."
            return "I don't know your name yet. You can tell me!"

        # Recent conversation recall
        history = self.memory.conversations.get_recent_history(
            self._session_id, limit=5
        )
        if history:
            summary = f"In our recent conversation, you said: '{history[0]['content']}'"
            return summary

        return "I don't have any previous conversation context to recall."

    # ──────────────────────────────────────────────────────────
    #  CONVERSATION / AI INTENT HANDLERS
    # ──────────────────────────────────────────────────────────

    def _dispatch_conversation(self, intent: Intent) -> str:
        # Handle simple built-in responses without calling AI
        sub = intent.sub_type
        text = intent.raw.lower()

        if sub == "greeting":
            return self._get_greeting()

        if sub == "thanks":
            import random
            return random.choice([
                "You're welcome!", "Happy to help!", "Of course!"
            ])

        if sub == "help":
            return self._get_help_text()

        # ── "Remember my name is X" ────────────────────────────
        if "my name is" in text or "i'm called" in text or "call me" in text:
            name = self._extract_name(text)
            if name and self.memory:
                self.memory.preferences.set("user_name", name)
                self.memory.facts.save_fact(
                    f"User's name is {name}",
                    category="personal",
                    source="self-introduction"
                )
                return f"Got it! I'll remember that your name is {name}."

        # ── Real AI response ───────────────────────────────────
        if self.ai_router:
            return self.ai_router.route(
                user_input=intent.raw,
                session_id=self._session_id,
                intent=intent,
            )

        # Phase 1 fallback
        return (
            "I'd love to answer that, but AI integration isn't set up yet. "
            "Add your API keys to .env and I'll be much smarter!"
        )

    def _dispatch_unknown(self, intent: Intent) -> str:
        return (
            "I'm not sure how to help with that. "
            "Try asking me to open an app, search the web, or ask me a question!"
        )

    # ──────────────────────────────────────────────────────────
    #  MEMORY HELPERS
    # ──────────────────────────────────────────────────────────

    def _save_user_input(self, text: str, intent_type: str) -> None:
        """Save user's message to conversation history."""
        if self.memory and text:
            try:
                self.memory.conversations.save_message(
                    session_id=self._session_id,
                    role="user",
                    content=text,
                    intent_type=intent_type
                )
            except Exception as e:
                logger.error(f"Failed to save user message: {e}")

    def _save_assistant_response(self, response: str, intent_type: str) -> None:
        """Save Drex's response to conversation history."""
        if self.memory and response:
            try:
                self.memory.conversations.save_message(
                    session_id=self._session_id,
                    role="assistant",
                    content=response,
                    intent_type=intent_type
                )
            except Exception as e:
                logger.error(f"Failed to save assistant response: {e}")

    # ──────────────────────────────────────────────────────────
    #  STATIC RESPONSE BUILDERS
    # ──────────────────────────────────────────────────────────

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
            stored_name = self.memory.preferences.get("user_name")
            if stored_name:
                name = f", {stored_name}"

        return f"Good {time_of_day}{name}! How can I help you today?"

    def _get_help_text(self) -> str:
        return (
            "Here's what I can do:\n"
            "• Open apps — 'Open Chrome', 'Launch Spotify'\n"
            "• Web search — 'Search for Python tutorials'\n"
            "• YouTube — 'Search YouTube for lo-fi music'\n"
            "• System — 'Take a screenshot', 'Volume up', 'What time is it'\n"
            "• Questions — 'What is machine learning?'\n"
            "• Remember things — 'My name is Ahmed'\n"
            "• Files — 'Open my downloads folder'\n"
            "• Weather — 'Weather in London'"
        )

    @staticmethod
    def _extract_name(text: str) -> Optional[str]:
        """Extract a name from 'my name is X' patterns."""
        import re
        patterns = [
            r"my name is (\w+)",
            r"i'm called (\w+)",
            r"call me (\w+)",
            r"i am (\w+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text.lower())
            if m:
                return m.group(1).capitalize()
        return None