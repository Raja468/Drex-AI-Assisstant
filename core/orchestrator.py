import uuid
from datetime import datetime
from typing import Optional, Callable
from loguru import logger

from config import get_config
from memory.db_manager import DBManager
from brain.prompt_builder import PromptBuilder
from brain.ai_router import AIRouter
from core.intent_parser import IntentParser, Intent


class Orchestrator:
    """
    Central controller for DREX.
    Wires: voice -> intent -> automation/AI -> memory -> response -> voice/GUI
    """

    def register_response_callback(self, callback: Callable[[str, str], None]):
        self.on_response = callback
        logger.debug("Response callback registered")

    def register_status_callback(self, callback: Callable[[str], None]):
        self.on_status = callback
        logger.debug("Status callback registered")

    def __init__(self, on_response: Callable[[str, str], None] = None,
                 on_status: Callable[[str], None] = None):
        self.cfg = get_config()
        self.session_id = str(uuid.uuid4())[:8]
        self.on_response = on_response
        self.on_status = on_status

        # Core modules
        self.db = DBManager()
        self.prompt_builder = PromptBuilder(memory_manager=self.db)
        self.ai_router = AIRouter()
        self.intent_parser = IntentParser()

        # Optional modules (lazy init)
        self._speaker = None
        self._listener = None
        self._automation = None

        # State
        self._running = False
        self._voice_mode = self.cfg.app.voice_enabled
        self._user_name = self.db.get_preference("user_name", "User")

        # Restore saved personality
        saved_personality = self.db.get_preference("personality_mode", "jarvis")
        self.prompt_builder.set_personality(saved_personality)

        # Start session
        self.db.start_session(self.session_id)
        self._setup_logging()
        logger.info("DREX Orchestrator started. Session: {}", self.session_id)

    def _setup_logging(self):
        import os
        os.makedirs(os.path.dirname(self.cfg.app.log_file), exist_ok=True)
        logger.add(
            self.cfg.app.log_file,
            level=self.cfg.app.log_level,
            rotation="10 MB",
            retention="7 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        )

    # ── Lazy module loaders ────────────────────────────────

    @property
    def speaker(self):
        if self._speaker is None and self._voice_mode:
            try:
                from voice.speaker import Speaker
                self._speaker = Speaker()
            except Exception as e:
                logger.error("Speaker init failed: {}", e)
        return self._speaker

    @property
    def listener(self):
        if self._listener is None and self._voice_mode:
            try:
                from voice.listener import Listener
                self._listener = Listener()
            except Exception as e:
                logger.error("Listener init failed: {}", e)
        return self._listener

    @property
    def automation(self):
        if self._automation is None:
            try:
                from automation.task_handler import TaskHandler
                self._automation = TaskHandler()
            except Exception as e:
                logger.error("Automation init failed: {}", e)
        return self._automation

    # ── Main entry point ───────────────────────────────────

    def process(self, user_input: str, voice_response: bool = None) -> str:
        if not user_input or not user_input.strip():
            return ""

        user_input = user_input.strip()
        use_voice = voice_response if voice_response is not None else self._voice_mode

        logger.info("Processing: '{}'", user_input[:100])
        self._emit_status("Thinking...")

        self.db.save_message(self.session_id, "user", user_input)

        intent = self.intent_parser.parse(user_input)
        logger.debug("Intent: {} / {}", intent.type, intent.action)

        response = ""
        provider = "system"

        try:
            if intent.type == "personality":
                response = self._handle_personality(intent)

            elif self.intent_parser.is_automation(intent):
                response = self._handle_automation(intent)
                if response and len(user_input) > 30:
                    ai_comment, provider = self._get_ai_response(user_input, context=response)
                    if ai_comment:
                        response = ai_comment

            elif self.intent_parser.is_memory_op(intent):
                response = self._handle_memory(intent)

            elif intent.type == "small_talk":
                response = self._handle_small_talk(intent)

            elif intent.type == "time_date":
                response = self._handle_time_date(intent)

            else:
                response, provider = self._get_ai_response(user_input)

        except Exception as e:
            logger.error("Processing error: {}", e)
            response = f"I encountered an error: {str(e)[:100]}. Please try again."

        if not response:
            response = "I'm not sure how to respond to that. Could you rephrase?"

        self.db.save_message(self.session_id, "assistant", response,
                             metadata={"provider": provider})

        facts = self.prompt_builder.extract_facts_from_response(user_input, response)
        for fact in facts:
            self.db.save_fact(fact["category"], fact["key"], fact["value"])
            if fact["category"] == "identity" and fact["key"] == "name":
                self._user_name = fact["value"]
                self.db.set_preference("user_name", fact["value"])

        if self.on_response:
            self.on_response(response, provider)

        if use_voice and self.speaker:
            self.speaker.speak(response)

        self._emit_status("Ready")
        return response

    # ── Handlers ───────────────────────────────────────────

    def _handle_personality(self, intent: Intent) -> str:
        """Handle personality mode switching."""
        mode = intent.target.lower().strip()
        result = self.prompt_builder.set_personality(mode)
        self.db.set_preference("personality_mode", self.prompt_builder.get_personality())
        return result

    def _get_ai_response(self, user_input: str, context: str = None) -> tuple[str, str]:
        prompt = self.prompt_builder.build(
            user_input=user_input,
            session_id=self.session_id,
            extra_context=context if context else ""
        )
        self._emit_status("Generating response...")
        response, provider = self.ai_router.generate(
            messages=prompt["messages"],
            system_prompt=prompt["system"],
            user_input=user_input,
        )
        logger.info("AI response via {}: {}...", provider, response[:80])
        return response, provider

    def _handle_automation(self, intent: Intent) -> str:
        if not self.automation:
            return f"Automation module not available. I would have: {intent.action} {intent.target}"
        self._emit_status(f"Running: {intent.action} {intent.target}...")
        try:
            result = self.automation.execute(intent)
            return result
        except Exception as e:
            logger.error("Automation failed: {}", e)
            return f"I tried to {intent.action} {intent.target} but encountered an error: {e}"

    def _handle_memory(self, intent: Intent) -> str:
        if intent.action == "remember":
            self.db.save_fact("user_notes", intent.target[:50], intent.target)
            return f"Got it, I'll remember that: {intent.target}"

        elif intent.action == "recall":
            facts = self.db.get_facts()
            history = self.db.search_history(intent.target, limit=3)
            if facts or history:
                parts = []
                if facts:
                    parts.append("Here's what I know: " +
                                 ", ".join(f"{f['key']}: {f['value']}" for f in facts[:5]))
                if history:
                    parts.append("From our conversation: " +
                                 " | ".join(h["content"][:80] for h in history))
                return " ".join(parts)
            return "I don't have any saved information about that."

        elif intent.action == "set_name":
            name = intent.target.strip().split()[0].capitalize()
            self._user_name = name
            self.db.set_preference("user_name", name)
            self.db.save_fact("identity", "name", name)
            return f"Got it! I'll call you {name} from now on."

        elif intent.action == "forget":
            return "I've noted that. Memory management is being improved in a future update."

        return "Memory operation processed."

    def _handle_small_talk(self, intent: Intent) -> str:
        personality = self.prompt_builder.get_personality()

        greetings = {
            "jarvis":   f"Good day, {self._user_name}. How may I assist you?",
            "friendly": f"Hey {self._user_name}! Great to see you! What can I do for you? 😊",
            "hacker":   f">> HELLO {self._user_name.upper()} | READY",
            "calm":     f"Hello, {self._user_name}. I'm here.",
        }
        farewells = {
            "jarvis":   "Until next time. Stay productive.",
            "friendly": "Bye! Talk soon! 👋",
            "hacker":   ">> SESSION TERMINATED | GOODBYE",
            "calm":     "Goodbye. Take care.",
        }
        how_are_you = {
            "jarvis":   "All systems operational. Ready to assist.",
            "friendly": "I'm doing great, thanks for asking! 😄 Ready to help!",
            "hacker":   ">> STATUS: OPTIMAL | AWAITING INPUT",
            "calm":     "I am well. Thank you. How are you?",
        }

        responses = {
            "greeting":    greetings.get(personality, greetings["jarvis"]),
            "farewell":    farewells.get(personality, farewells["jarvis"]),
            "thanks":      "Happy to help!",
            "how_are_you": how_are_you.get(personality, how_are_you["jarvis"]),
            "identity":    f"I'm DREX — your AI desktop assistant. Currently in {self.prompt_builder.get_personality_display()}.",
            "capabilities": (
                "I can help you with:\n"
                "• Answering questions and conversations\n"
                "• Opening apps, websites, and files\n"
                "• System controls (volume, brightness, shutdown)\n"
                "• Searching the web\n"
                "• Remembering things for you\n"
                "• Writing, coding, analysis\n"
                "• Switching personality modes — try: 'switch to hacker mode'"
            ),
        }
        return responses.get(intent.action,
                             f"Hey {self._user_name}! What can I help you with?")

    def _handle_time_date(self, intent: Intent) -> str:
        now = datetime.now()
        if intent.action == "current_time":
            return f"It's {now.strftime('%I:%M %p')}."
        elif intent.action == "current_date":
            return f"Today is {now.strftime('%A, %B %d, %Y')}."
        return f"It's {now.strftime('%A, %B %d, %Y at %I:%M %p')}."

    # ── Voice loop ─────────────────────────────────────────

    def start_voice_loop(self):
        if not self.listener or not self.listener.is_available:
            logger.warning("Voice loop unavailable — microphone not accessible")
            return

        def on_speech(text: str):
            if text:
                self.process(text, voice_response=True)

        self.listener.start_continuous(callback=on_speech)
        self._running = True
        logger.info("Voice loop started")

    def stop_voice_loop(self):
        if self.listener:
            self.listener.stop_continuous()
        self._running = False

    def start_voice_listening(self):
        """Alias for GUI compatibility."""
        self.start_voice_loop()

    def stop_voice_listening(self):
        """Alias for GUI compatibility."""
        self.stop_voice_loop()

    def listen_once(self) -> Optional[str]:
        if not self.listener or not self.listener.is_available:
            return None
        self._emit_status("Listening...")
        text = self.listener.listen_once()
        self._emit_status("Ready")
        if text:
            self.process(text, voice_response=True)
        return text

    # ── Utilities ──────────────────────────────────────────

    def _emit_status(self, msg: str):
        if self.on_status:
            self.on_status(msg)

    def get_ai_status(self) -> dict:
        return self.ai_router.get_status()

    def get_session_info(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_name": self._user_name,
            "voice_mode": self._voice_mode,
            "personality": self.prompt_builder.get_personality(),
            "started": datetime.now().isoformat(),
            "total_sessions": self.db.get_session_count(),
        }

    def set_voice_mode(self, enabled: bool):
        self._voice_mode = enabled
        if not enabled and self.listener:
            self.listener.stop_continuous()

    def switch_ai_provider(self, provider: str):
        self.cfg.ai.default_provider = provider
        self.ai_router.reset_status()
        logger.info("AI provider switched to: {}", provider)

    def shutdown(self):
        logger.info("DREX shutting down...")
        self.stop_voice_loop()
        self.db.end_session(self.session_id, summary="User ended session")
        self.db.close()
        if self._speaker:
            self._speaker.shutdown()
        if self._listener:
            self._listener.shutdown()
        logger.info("DREX shutdown complete")