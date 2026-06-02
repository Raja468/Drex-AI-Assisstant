"""
core/orchestrator.py — Central Controller for DREX

Wires: voice -> intent -> automation/AI -> memory -> response -> voice/GUI

Architecture improvements:
  - Streaming response foundation (callback-based token delivery)
  - Wake word integration (background listening mode)
  - Thread-safe shutdown with proper lifecycle management
  - Resilient voice loop with automatic recovery
"""

import threading
import time
import uuid
from datetime import datetime
from typing import Optional, Callable
from loguru import logger

from config import get_config
from memory.db_manager import DBManager
from brain.prompt_builder import PromptBuilder
from brain.ai_router import AIRouter
from brain.base_client import StreamCallback
from core.intent_parser import IntentParser, Intent


# ── Voice state machine ─────────────────────────────────────
class VoiceState:
    """Centralized voice session state with thread-safe mutex."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"

    def __init__(self):
        self._state = self.IDLE
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @state.setter
    def state(self, new_state: str):
        with self._lock:
            old = self._state
            self._state = new_state
            if old != new_state:
                logger.debug("Voice state: {} → {}", old, new_state)

    def can_listen(self) -> bool:
        """Can we start listening? Only if not currently speaking."""
        with self._lock:
            return self._state not in (self.SPEAKING,)

    def can_speak(self) -> bool:
        """Can we start speaking? Only if not currently listening."""
        with self._lock:
            return self._state not in (self.LISTENING,)


class Orchestrator:
    """
    Central controller for DREX.

    Wires: voice -> intent -> automation/AI -> memory -> response -> voice/GUI

    Supports:
      - Synchronous response processing
      - Streaming response callbacks (for realtime token delivery)
      - Wake word detection for always-listening mode
      - Voice mode toggling
      - Multi-provider AI fallback
    """

    def __init__(self, on_response: Callable[[str, str], None] = None,
                 on_status: Callable[[str], None] = None,
                 on_stream_token: Callable[[str], None] = None,
                 on_voice_input: Callable[[str], None] = None):
        self.cfg = get_config()
        self.session_id = str(uuid.uuid4())[:8]
        self.on_response = on_response
        self.on_status = on_status
        self.on_stream_token = on_stream_token  # callback for streaming tokens
        self.on_voice_input = on_voice_input    # callback for voice input text

        # Core modules
        self.db = DBManager()
        self.prompt_builder = PromptBuilder(memory_manager=self.db)
        self.ai_router = AIRouter()
        self.intent_parser = IntentParser()

        # Optional modules (lazy init)
        self._speaker = None
        self._listener = None
        self._automation = None
        self._wake_word = None  # lazy init for wake word detector

        # Voice state machine for mutex protection
        self.voice_state = VoiceState()

        # Request dedup state
        self._last_request_id = ""
        self._request_counter = 0

        # State
        self._running = False
        self._voice_mode = self.cfg.app.voice_enabled
        self._user_name = self.db.get_preference("user_name", "User")
        self._wake_word_activated = False  # True when wake word was just heard
        self._process_lock = threading.Lock()
        self._processing = False
        self._generation_id = 0
        self._last_voice_at = 0.0
        self._voice_debounce_sec = 1.5

        # Restore saved personality
        saved_personality = self.db.get_preference("personality_mode", "jarvis")
        self.prompt_builder.set_personality(saved_personality)

        # Start session
        self.db.start_session(self.session_id)
        self._setup_logging()
        logger.info("DREX Orchestrator started. Session: {}", self.session_id)

    # ── Streaming hooks (Issue 5) ──────────────────────────

    def register_response_callback(self, callback: Callable[[str, str], None]):
        """Register a callback for complete responses (text, provider)."""
        self.on_response = callback
        logger.debug("Response callback registered")

    def register_status_callback(self, callback: Callable[[str], None]):
        """Register a callback for status updates."""
        self.on_status = callback
        logger.debug("Status callback registered")

    def register_stream_callback(self, callback: Callable[[str], None]):
        """
        Register a callback for streaming token delivery.

        Args:
            callback: Called with each partial token as it's generated.
                      Used by the GUI to display realtime streaming text.
        """
        self.on_stream_token = callback
        logger.debug("Stream callback registered")

    def register_voice_input_callback(self, callback: Callable[[str], None]):
        """
        Register a callback for voice input text.

        Called when the user speaks and the text is transcribed.
        The GUI uses this to display the user's spoken message in the chat
        before the AI response is generated.

        Args:
            callback: Called with the transcribed text from voice input.
        """
        self.on_voice_input = callback
        logger.debug("Voice input callback registered")

    # ── Setup ──────────────────────────────────────────────

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

    @property
    def wake_word(self):
        """Lazy-load the wake word detector module."""
        if self._wake_word is None:
            try:
                from voice.wake_word import WakeWordDetector
                self._wake_word = WakeWordDetector()
            except Exception as e:
                logger.error("Wake word init failed: {}", e)
        return self._wake_word

    # ── Main entry point ───────────────────────────────────

    def cancel_pending_generation(self):
        """Invalidate in-flight streaming and stop TTS (new user input)."""
        self._generation_id += 1
        if self._speaker:
            try:
                self._speaker.stop()
            except Exception:
                pass
        logger.debug("Generation cancelled (id={})", self._generation_id)

    def process(self, user_input: str, voice_response: bool = None) -> str:
        """
        Process user input through intent parser -> AI -> response.

        Args:
            user_input: The text input from the user.
            voice_response: Whether to speak the response (None = use default).

        Returns:
            The response text.
        """
        if not user_input or not user_input.strip():
            return ""

        user_input = user_input.strip()
        use_voice = voice_response if voice_response is not None else self._voice_mode

        with self._process_lock:
            self._generation_id += 1
            generation_id = self._generation_id
            self._processing = True

        if self.speaker:
            self.speaker.stop()

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
                    ai_comment, provider = self._get_ai_response(
                        user_input,
                        context=response,
                        generation_id=generation_id,
                    )
                    if ai_comment:
                        response = ai_comment

            elif self.intent_parser.is_memory_op(intent):
                response = self._handle_memory(intent)

            elif intent.type == "small_talk":
                response, provider = self._handle_small_talk(intent)

            elif intent.type == "time_date":
                response = self._handle_time_date(intent)

            else:
                response, provider = self._get_ai_response(
                    user_input, generation_id=generation_id
                )

        except Exception as e:
            logger.error("Processing error: {}", e)
            response = (
                f"I encountered an error: {str(e)[:100]}. Please try again."
            )
        finally:
            with self._process_lock:
                if generation_id == self._generation_id:
                    self._processing = False

        if generation_id != self._generation_id:
            logger.debug("Discarding stale response (generation {})", generation_id)
            return ""

        if not response:
            response = "I'm not sure how to respond to that. Could you rephrase?"

        self.db.save_message(
            self.session_id, "assistant", response,
            metadata={"provider": provider},
        )

        facts = self.prompt_builder.extract_facts_from_response(
            user_input, response
        )
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
        self.db.set_preference(
            "personality_mode", self.prompt_builder.get_personality()
        )
        return result

    def _emit_stream_token(self, token: str, generation_id: int):
        if generation_id != self._generation_id:
            return
        if self.on_stream_token:
            self.on_stream_token(token)

    def _get_ai_response(
        self,
        user_input: str,
        context: str = None,
        generation_id: int = None,
    ) -> tuple[str, str]:
        """Get AI response via the router with fallback and optional streaming."""
        gen_id = generation_id if generation_id is not None else self._generation_id
        prompt = self.prompt_builder.build(
            user_input=user_input,
            session_id=self.session_id,
            extra_context=context if context else "",
        )
        self._emit_status("Generating response...")

        if self.on_stream_token:
            self._emit_stream_token("__DREX_STREAM_START__", gen_id)

            def on_token(token: str):
                self._emit_stream_token(token, gen_id)

            response, provider = self.ai_router.generate_stream(
                messages=prompt["messages"],
                system_prompt=prompt["system"],
                user_input=user_input,
                on_token=on_token,
            )
        else:
            response, provider = self.ai_router.generate(
                messages=prompt["messages"],
                system_prompt=prompt["system"],
                user_input=user_input,
            )

        if gen_id == self._generation_id:
            logger.info("AI response via {}: {}...", provider, response[:80])
        return response, provider

    def _handle_automation(self, intent: Intent) -> str:
        if not self.automation:
            return (
                f"Automation module not available. "
                f"I would have: {intent.action} {intent.target}"
            )
        self._emit_status(f"Running: {intent.action} {intent.target}...")
        try:
            result = self.automation.execute(intent)
            return result
        except Exception as e:
            logger.error("Automation failed: {}", e)
            return (
                f"I tried to {intent.action} {intent.target} "
                f"but encountered an error: {e}"
            )

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
                    parts.append(
                        "Here's what I know: "
                        + ", ".join(
                            f"{f['key']}: {f['value']}" for f in facts[:5]
                        )
                    )
                if history:
                    parts.append(
                        "From our conversation: "
                        + " | ".join(
                            h["content"][:80] for h in history
                        )
                    )
                return " ".join(parts)
            return "I don't have any saved information about that."

        elif intent.action == "set_name":
            name = intent.target.strip().split()[0].capitalize()
            self._user_name = name
            self.db.set_preference("user_name", name)
            self.db.save_fact("identity", "name", name)
            return f"Got it! I'll call you {name} from now on."

        elif intent.action == "forget":
            return (
                "I've noted that. Memory management is being "
                "improved in a future update."
            )

        return "Memory operation processed."

    def _handle_small_talk(self, intent: Intent) -> tuple[str, str]:
        """
        Handle greetings, farewells, and small talk.

        For jarvis/friendly/calm: route through AI for natural conversation.
        For hacker mode: keep hardcoded terminal-style responses.
        Only capabilities/identity stay hardcoded (they're structural).
        """
        personality = self.prompt_builder.get_personality()

        # Structural info — keep hardcoded
        if intent.action in ("identity", "capabilities"):
            responses = {
                "identity": (
                    f"I'm DREX — your AI desktop assistant. "
                    f"Currently in {self.prompt_builder.get_personality_display()}."
                ),
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
            return responses[intent.action], "system"

        # Hacker mode: keep terminal-style hardcoded responses
        if personality == "hacker":
            hacker_responses = {
                "greeting":    f">> HELLO {self._user_name.upper()} | READY",
                "farewell":    ">> SESSION TERMINATED | GOODBYE",
                "thanks":      ">> ACKNOWLEDGED",
                "how_are_you": ">> STATUS: OPTIMAL | AWAITING INPUT",
            }
            return hacker_responses.get(
                intent.action,
                ">> PROCESSING... | STATE: AWAITING",
            ), "system"

        # All other personality modes: route through AI for natural conversation
        response, _ = self._get_ai_response(intent.raw)
        return (response or f"Hey {self._user_name}! What can I help you with?"), _

    def _handle_time_date(self, intent: Intent) -> str:
        now = datetime.now()
        if intent.action == "current_time":
            return f"It's {now.strftime('%I:%M %p')}."
        elif intent.action == "current_date":
            return f"Today is {now.strftime('%A, %B %d, %Y')}."
        return (
            f"It's {now.strftime('%A, %B %d, %Y at %I:%M %p')}."
        )

    # ── Voice loop ─────────────────────────────────────────

    def _voice_process(self, text: str, request_id: str = None):
        """
        Debounced voice input handler with UUID dedup — avoids duplicate triggers.
        
        Uses two-layer dedup:
          1. UUID-based: same request_id cannot be processed twice
          2. Time-based: 1.5s debounce window prevents rapid re-triggers
        
        Args:
            text: Transcribed speech text
            request_id: Unique UUID for this voice input (generated if not provided)
        """
        if not text or not text.strip():
            return
        
        # Generate request_id if not provided (listen_once path)
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        now = time.time()
        
        # Layer 1: UUID dedup — reject exact same request
        if request_id == self._last_request_id:
            logger.debug("Duplicate voice request (UUID match) — rejected")
            return
        
        # Layer 2: Time-based debounce — reject rapid re-triggers
        if now - self._last_voice_at < self._voice_debounce_sec:
            logger.debug("Voice input debounced (time window)")
            return
        
        # Accept this request
        self._last_request_id = request_id
        self._last_voice_at = now
        self.voice_state.state = VoiceState.PROCESSING
        
        # Notify GUI of voice input (so it can display user message + streaming label)
        clean_text = text.strip()
        if self.on_voice_input:
            self.on_voice_input(clean_text)
        
        self.process(clean_text, voice_response=True)
        
        # Return to listening state after processing
        self.voice_state.state = VoiceState.LISTENING

    def start_voice_loop(self):
        """
        Start the resilient voice listening loop.

        If wake word is enabled, starts the wake word detector instead,
        and only starts listening for commands after wake word detection.
        """
        if self._running:
            logger.debug("Voice loop already running")
            return

        if not self.listener or not self.listener.is_available:
            logger.warning(
                "Voice loop unavailable — microphone not accessible"
            )
            return

        # If wake word is enabled, start in wake word mode
        if self.cfg.app.wake_word_enabled and self.wake_word_is_available():
            self._start_wake_word_mode()
            return

        # Standard continuous listening mode
        self._start_continuous_mode()

    def _start_continuous_mode(self):
        """Start standard continuous listening mode."""
        def on_speech(text: str):
            # Generate UUID for continuous voice callback dedup
            request_id = str(uuid.uuid4())
            self._voice_process(text, request_id=request_id)

        self.listener.start_continuous(callback=on_speech)
        self._running = True
        logger.info("Voice loop started (continuous mode)")

    def _start_wake_word_mode(self):
        """
        Start wake word + command mode.

        The wake word detector runs in the background. When the wake word
        is detected, a single command is listened for, processed, and then
        it returns to wake word detection mode.
        """
        if not self.wake_word or not self.wake_word.is_available:
            logger.warning(
                "Wake word not available, falling back to continuous mode"
            )
            self._start_continuous_mode()
            return

        def on_wake_word():
            """Called when wake word is detected."""
            logger.info("🔊 Wake word detected — listening for command...")
            self._emit_status("Wake word detected. Listening...")

            if self.speaker:
                self.speaker.speak("Yes?", priority=True)
                time.sleep(0.3)

            text = self.listener.listen_once(timeout=5, phrase_limit=10)
            if text:
                self._voice_process(text)
            else:
                logger.debug("No command after wake word")

        self.wake_word.start(callback=on_wake_word)
        self._running = True
        logger.info("Voice loop started (wake word mode)")

    def wake_word_is_available(self) -> bool:
        """Check if the wake word detector is initialized and available."""
        return (
            self._wake_word is not None
            and self._wake_word.is_available
        )

    def stop_voice_loop(self):
        """Stop all voice-related threads gracefully."""
        # Stop continuous listening
        if self.listener:
            self.listener.stop_continuous()

        # Stop wake word detection
        if self._wake_word:
            try:
                self._wake_word.stop()
            except Exception as e:
                logger.debug("Error stopping wake word: {}", e)

        self._running = False
        logger.info("Voice loop stopped")

    def start_voice_listening(self):
        """Alias for GUI compatibility."""
        self.start_voice_loop()

    def stop_voice_listening(self):
        """Alias for GUI compatibility."""
        self.stop_voice_loop()

    def listen_once(self) -> Optional[str]:
        """Listen for a single utterance and process it."""
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
        if not enabled:
            self.stop_voice_loop()

    def switch_ai_provider(self, provider: str):
        self.cfg.ai.default_provider = provider
        self.ai_router.reset_status()
        logger.info("AI provider switched to: {}", provider)

    def shutdown(self):
        """Clean shutdown of all modules. Idempotent and thread-safe."""
        logger.info("DREX shutting down...")

        # Stop voice loops first
        self.stop_voice_loop()

        # End database session
        try:
            self.db.end_session(self.session_id, summary="User ended session")
            self.db.close()
        except Exception as e:
            logger.error("DB shutdown error: {}", e)

        # Shutdown speaker
        if self._speaker:
            try:
                self._speaker.shutdown()
            except Exception as e:
                logger.error("Speaker shutdown error: {}", e)

        # Shutdown listener
        if self._listener:
            try:
                self._listener.shutdown()
            except Exception as e:
                logger.error("Listener shutdown error: {}", e)

        # Shutdown wake word
        if self._wake_word:
            try:
                self._wake_word.shutdown()
            except Exception as e:
                logger.debug("Wake word shutdown error: {}", e)

        logger.info("DREX shutdown complete")