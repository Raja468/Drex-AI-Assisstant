"""
core/orchestrator.py — Central Controller for DREX

Wires: voice -> intent -> automation/AI -> memory -> response -> voice/GUI

Architecture improvements:
  - Streaming response foundation (callback-based token delivery)
  - Wake word integration (background listening mode)
  - Thread-safe shutdown with proper lifecycle management
  - Resilient voice loop with automatic recovery
  - Performance: lazy-load ScreenCapture/VisionAnalyzer, deferred DB init
"""

import asyncio
import hashlib
import threading
import time
import uuid
from datetime import datetime
from typing import Optional, Callable
from loguru import logger

# ── Shared event loop for async operations ──────────────────
# Created once, reused for all async calls. Prevents the
# "asyncio.run() cannot be called from a running event loop"
# error and avoids creating a new event loop per request.
_SHARED_LOOP: Optional[asyncio.AbstractEventLoop] = None
_LOOP_LOCK = threading.Lock()

def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create the shared event loop (thread-safe, created once)."""
    global _SHARED_LOOP
    if _SHARED_LOOP is None or _SHARED_LOOP.is_closed():
        with _LOOP_LOCK:
            if _SHARED_LOOP is None or _SHARED_LOOP.is_closed():
                _SHARED_LOOP = asyncio.new_event_loop()
                _SHARED_LOOP.set_debug(False)
    return _SHARED_LOOP

def _run_async(coro) -> any:
    """Run a coroutine on the shared event loop from a sync context."""
    loop = _get_event_loop()
    try:
        return loop.run_until_complete(coro)
    except RuntimeError:
        # Fallback: create a temporary loop if the shared one is busy
        temp_loop = asyncio.new_event_loop()
        try:
            return temp_loop.run_until_complete(coro)
        finally:
            temp_loop.close()

from config import get_config
from brain.prompt_builder import PromptBuilder
from brain.ai_router import AIRouter
from brain.base_client import StreamCallback
from core.fast_router import FastRouter
from core.intent_parser import IntentParser, Intent
from core.permission import PermissionManager, ActionRisk

# Screen awareness (optional - requires mss, Pillow) — lazy-imported
_SCREEN_CAPTURE_CLS = None
_VISION_ANALYZER_CLS = None

def _get_screen_capture_cls():
    global _SCREEN_CAPTURE_CLS
    if _SCREEN_CAPTURE_CLS is None:
        try:
            from assistant.screen_capture import ScreenCapture
            _SCREEN_CAPTURE_CLS = ScreenCapture
        except ImportError:
            _SCREEN_CAPTURE_CLS = False  # Sentinel: already tried
    return _SCREEN_CAPTURE_CLS if _SCREEN_CAPTURE_CLS is not False else None

def _get_vision_analyzer_cls():
    global _VISION_ANALYZER_CLS
    if _VISION_ANALYZER_CLS is None:
        try:
            from assistant.vision_analyzer import VisionAnalyzer
            _VISION_ANALYZER_CLS = VisionAnalyzer
        except ImportError:
            _VISION_ANALYZER_CLS = False
    return _VISION_ANALYZER_CLS if _VISION_ANALYZER_CLS is not False else None


# ── Voice state machine ─────────────────────────────────────
class VoiceState:
    """Centralized voice session state with thread-safe mutex.

    Delegates to VoiceEngine's VoiceState enum when a VoiceEngine
    is wired in via set_voice_engine(). Otherwise uses local state
    for backward compatibility.
    """
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"

    def __init__(self):
        self._state = self.IDLE
        self._lock = threading.Lock()
        self._voice_engine_ref = None

    def set_voice_engine(self, voice_engine):
        """Wire a VoiceEngine to use its state as source of truth."""
        self._voice_engine_ref = voice_engine

    @property
    def state(self) -> str:
        # When VoiceEngine is wired, delegate to it
        if self._voice_engine_ref is not None:
            try:
                return self._voice_engine_ref.state.value
            except Exception:
                pass
        with self._lock:
            return self._state

    @state.setter
    def state(self, new_state: str):
        # If VoiceEngine is wired, let it be source of truth
        if self._voice_engine_ref is not None:
            return
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
      
    PERFORMANCE: Heavy modules (ScreenCapture, VisionAnalyzer, DB session)
    are lazy-loaded to reduce startup time.
    """

    # Phase 5C: class-level wiring slots (architecture contract)
    planner = None
    execution_engine = None
    _pending_execution = None
    # Phase 6: Awareness Engine (read-only query)
    awareness_engine = None
    # Multi-step keywords (overridden per-instance, kept here for tests)
    MULTI_STEP_KEYWORDS = [
        "then", "and then", "after that", "followed by",
        "first", "next", "finally", "step by step",
    ]
    _CONFIRM_YES = {"yes", "yeah", "sure", "proceed", "go", "do it", "confirm", "okay"}
    _CONFIRM_NO = {"no", "cancel", "stop", "abort", "nevermind", "don't", "dont"}

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

        # Core modules (fast to init)
        self.db = None  # Lazy-init on first use
        self._db_init_lock = threading.Lock()
        self._db_initialized = False
        
        # prompt_builder is a @property backed by _pb_instance
        # Lazy-init with memory manager on first use
        self._pb_instance = None
        self._pb_lock = threading.Lock()
        self._pb_initialized = False
        
        self.ai_router = AIRouter()
        self.intent_parser = IntentParser()
        self.fast_router = FastRouter()

        # Optional modules (lazy init)
        self._speaker = None
        self._listener = None
        self._automation = None
        self._wake_word = None  # lazy init for wake word detector
        self._conversation_engine = None  # lazy init for duplex conversation engine
        self._post_processor = None  # lazy init for STT text cleaning

        # Conversation mode flag
        self._conversation_mode = False

        # Voice state machine for mutex protection
        self.voice_state = VoiceState()

        # Request dedup state
        self._last_request_id = ""
        self._request_counter = 0

        # State
        self._running = False
        self._voice_mode = self.cfg.app.voice_enabled
        self._user_name = "User"  # Default until DB loads
        self._wake_word_activated = False  # True when wake word was just heard
        self._process_lock = threading.Lock()
        self._processing = False
        self._generation_id = 0
        self._last_voice_at = 0.0
        self._voice_debounce_sec = 1.5

        # ── Phase 4: IntentService, ToolRouter, ResponseService (wired by main.py) ──
        self._intent_service = None
        self._tool_router = None
        self._response_service = None

        # ── Phase 5B: Planner (wired by main.py) ──
        self.planner = None

        # ── Phase 5C: ExecutionEngine (wired by main.py) ──
        self.execution_engine = None
        self._pending_execution = None

        # ── Phase 6: AwarenessEngine (wired by main.py) ──
        self.awareness_engine = None

        # ── Phase 5C: Multi-step planning constants ──
        self.MULTI_STEP_KEYWORDS = [
            "then", "and then", "after that", "followed by",
            "first", "next", "finally", "step by step",
            "do the following", "do this", "in order",
            "sequentially", "one by one", "steps:", "step 1",
        ]
        self._CONFIRM_YES = {"yes", "yeah", "sure", "proceed", "go", "do it", "confirm", "okay"}
        self._CONFIRM_NO = {"no", "cancel", "stop", "abort", "nevermind", "don't", "dont"}

        # Screen awareness (lazy-loaded on first use)
        self.screen_capture = None
        self.vision_analyzer = None

        # Permission manager for automation security
        self.permission = PermissionManager()

        # Deduplication
        self._recent_requests: dict[str, float] = {}
        self._dedup_window = 2.0  # seconds

        # Defer heavy init: DB, prompt builder, personality, screen modules
        # These are initialized on first access.
        self._setup_logging()
        logger.info("DREX Orchestrator created (Session: {} | lazy-heavy-init)", self.session_id)

    # ── Lazy DB accessor ──────────────────────────────────
    @property
    def prompt_builder(self):
        """Lazy-init PromptBuilder on first use. Thread-safe."""
        if not self._pb_initialized:
            with self._pb_lock:
                if not self._pb_initialized:
                    db = self._ensure_db()
                    self._pb_instance = PromptBuilder(memory_manager=db)
                    # Restore saved personality
                    saved = db.get_preference("personality_mode", "jarvis")
                    self._pb_instance.set_personality(saved)
                    self._pb_initialized = True
        return self._pb_instance

    @prompt_builder.setter
    def prompt_builder(self, value):
        """Allow direct assignment for backward compatibility."""
        self._pb_instance = value
        self._pb_initialized = value is not None

    def _ensure_db(self):
        """Initialize DB on first use. Thread-safe."""
        if self._db_initialized and self.db is not None:
            return self.db
        with self._db_init_lock:
            if self._db_initialized and self.db is not None:
                return self.db
            from memory.db_manager import DBManager
            self.db = DBManager()
            self.db.start_session(self.session_id)
            # Now load user preferences
            self._user_name = self.db.get_preference("user_name", "User")
            self._db_initialized = True
            logger.debug("DB initialized on first use")
            return self.db

    def _lazy_init_screen_capture(self):
        """Lazy-init screen capture on first use."""
        if self.screen_capture is None:
            cls = _get_screen_capture_cls()
            if cls:
                try:
                    self.screen_capture = cls()
                    logger.info("ScreenCapture lazy-loaded")
                except Exception as e:
                    logger.warning("ScreenCapture lazy init failed: {}", e)
        return self.screen_capture

    def _lazy_init_vision_analyzer(self):
        """Lazy-init vision analyzer on first use."""
        if self.vision_analyzer is None:
            cls = _get_vision_analyzer_cls()
            if cls:
                try:
                    self.vision_analyzer = cls(ai_router=self.ai_router)
                    logger.info("VisionAnalyzer lazy-loaded")
                except Exception as e:
                    logger.warning("VisionAnalyzer lazy init failed: {}", e)
        return self.vision_analyzer

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

    # ── Runtime voice engine (set by main.py if available) ──
    # If set, all voice properties delegate to the engine.
    _voice_engine = None

    # ── Lazy module loaders ────────────────────────────────

    @property
    def speaker(self):
        # If VoiceEngine is wired, delegate to it
        if self._voice_engine is not None:
            return self._voice_engine.speaker
        # Fallback: existing lazy init
        if self._speaker is None and self._voice_mode:
            try:
                from voice.speaker import Speaker
                self._speaker = Speaker()
            except Exception as e:
                logger.error("Speaker init failed: {}", e)
        return self._speaker

    @property
    def listener(self):
        # If VoiceEngine is wired, delegate to it
        if self._voice_engine is not None:
            return self._voice_engine.listener
        # Fallback: existing lazy init
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
        # If VoiceEngine is wired, delegate to it
        if self._voice_engine is not None:
            return self._voice_engine.wake_word
        # Fallback: existing lazy init
        if self._wake_word is None:
            try:
                from voice.wake_word import WakeWordDetector
                self._wake_word = WakeWordDetector()
            except Exception as e:
                logger.error("Wake word init failed: {}", e)
        return self._wake_word

    @property
    def conversation_engine(self):
        """Lazy-load the duplex conversation engine."""
        if self._conversation_engine is None:
            try:
                from voice.conversation_engine import ConversationEngine
                self._conversation_engine = ConversationEngine()
                if self._speaker:
                    self._conversation_engine.wire_speaker(self._speaker)
            except Exception as e:
                logger.error("ConversationEngine init failed: {}", e)
        return self._conversation_engine

    @property
    def post_processor(self):
        """Lazy-load the STT text post-processor."""
        if self._post_processor is None:
            try:
                from voice.post_processor import PostProcessor
                self._post_processor = PostProcessor()
            except Exception as e:
                logger.error("PostProcessor init failed: {}", e)
        return self._post_processor

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

        # Ensure DB is initialized before first process
        self._ensure_db()

        user_input = user_input.strip()
        use_voice = voice_response if voice_response is not None else self._voice_mode

        # ── Deduplication ───────────────────────────────────────
        if self._is_duplicate(user_input):
            return ""

        # ── Timing Checkpoints ──────────────────────────────────
        t0 = time.perf_counter()

        # ── FastRouter: intercept simple commands before AI ─────
        fast_method, fast_groups = self.fast_router.match(user_input)
        if fast_method:
            t1 = time.perf_counter()
            response = self.fast_router.execute(fast_method, fast_groups)
            ms = (t1 - t0) * 1000
            logger.info(f"FastRouter: '{user_input}' → {ms:.1f}ms")
            # Format through ResponseService if available
            if self._response_service is not None:
                response = self._response_service.format_ai_response(response)
            self._emit_status("Ready")
            if use_voice and self.speaker:
                self.speaker.speak(response)
            if self.on_response:
                self.on_response(response, "fast_router")
            return response

        # ── LAYER 2.5: Confirmation Layer (Phase 5C) ─────────────
        # Check if user is confirming/cancelling a pending execution
        if self._pending_execution is not None:
            decision, _ = self._handle_confirmation(user_input)
            if decision is True:
                # User confirmed — execute
                task = self._pending_execution
                self._pending_execution = None
                result = self.execution_engine.execute(task)
                if self._response_service is not None:
                    response = self._response_service.format_execution_result(result)
                else:
                    response = result.summary()
                db = self._ensure_db()
                db.save_message(self.session_id, "assistant", response, metadata={"provider": "execution_engine"})
                if self.on_response:
                    self.on_response(response, "execution_engine")
                if use_voice and self.speaker:
                    self.speaker.speak(response)
                self._emit_status("Ready")
                return response
            elif decision is False:
                # User rejected — cancel
                self._pending_execution = None
                response = "Okay, I've cancelled that plan."
                self._emit_status("Ready")
                return response
            # Ambiguous — continue to normal processing

        # ── LAYER 3: Planning Layer (Phase 5C) ───────────────────
        if self.execution_engine is not None and self.planner is not None \
                and self._response_service is not None:
            if self._should_plan(user_input):
                plan = self.planner.create_plan(user_input)
                task = self.execution_engine.prepare(plan)
                if task is not None:
                    self._pending_execution = task
                    response = self._response_service.format_plan_summary(plan)
                    db = self._ensure_db()
                    db.save_message(self.session_id, "assistant", response, metadata={"provider": "planner"})
                    if self.on_response:
                        self.on_response(response, "planner")
                    if use_voice and self.speaker:
                        self.speaker.speak(response)
                    self._emit_status("Waiting for confirmation...")
                    return response

        # ── LAYER 4: IntentService + ToolRouter ──
        if self._tool_router is not None and self._intent_service is not None:
            intent_result = self._intent_service.classify(user_input)
            if self._tool_router.can_handle(intent_result):
                tool_result = self._tool_router.route(user_input, intent_result)
                if tool_result and tool_result.success:
                    response = (
                        self._response_service.format_tool_result(tool_result)
                        if self._response_service else tool_result.output or "Done."
                    )
                    if self._response_service is not None:
                        response = self._response_service.format_tool_result(tool_result)
                    else:
                        response = tool_result.output or "Done."
                    db = self._ensure_db()
                    db.save_message(self.session_id, "assistant", response, metadata={"provider": "tool_router"})
                    if self.on_response:
                        self.on_response(response, "tool_router")
                    if use_voice and self.speaker:
                        self.speaker.speak(response)
                    self._emit_status("Ready")
                    return response
                elif tool_result and not tool_result.success:
                    logger.warning("Tool failed, falling back to AI: {}", tool_result.error)

        t1 = time.perf_counter()

        with self._process_lock:
            self._generation_id += 1
            generation_id = self._generation_id
            self._processing = True

        if self.speaker:
            self.speaker.stop()

        logger.info("Processing: '{}'", user_input[:100])
        self._emit_status("Thinking...")

        db = self._ensure_db()
        db.save_message(self.session_id, "user", user_input)

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

            elif intent.type == "screen_query":
                response = self._handle_screen_query(intent, user_input)

            else:
                # AI response — use streaming TTS when voice is active
                if use_voice and self.speaker:
                    try:
                        prompt_data = self.prompt_builder.build(
                            user_input=user_input,
                            session_id=self.session_id,
                        )
                        response = _run_async(
                            self._stream_response_with_tts(
                                user_input=user_input,
                                context=prompt_data.get("messages"),
                            )
                        )
                        provider = "streaming"
                    except Exception as stream_err:
                        logger.error("Streaming TTS failed, falling back: {}", stream_err)
                        response, provider = self._get_ai_response(
                            user_input, generation_id=generation_id
                        )
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

        db = self._ensure_db()
        db.save_message(
            self.session_id, "assistant", response,
            metadata={"provider": provider},
        )
        logger.info(
            "LIFECYCLE | SAVE SESSION | session={} | provider={}",
            self.session_id, provider,
        )

        facts = self.prompt_builder.extract_facts_from_response(
            user_input, response
        )
        for fact in facts:
            db.save_fact(fact["category"], fact["key"], fact["value"])
            if fact["category"] == "identity" and fact["key"] == "name":
                self._user_name = fact["value"]
                db.set_preference("user_name", fact["value"])

        if self.on_response:
            self.on_response(response, provider)

        if use_voice and self.speaker:
            self.speaker.speak(response)

        self._emit_status("Ready")
        return response

    # ── Streaming TTS Pipeline ────────────────────────────

    async def _stream_response_with_tts(self, user_input: str, context: list = None,
                                         provider: str = None) -> str:
        """
        Streams AI response and pipes chunks to speak_stream() simultaneously.
        Returns the full assembled response text for saving to DB.
        Also fires GUI streaming callback for chat bubble updates.
        """
        full_response = []

        async def _chunk_generator():
            async for chunk in self.ai_router.stream_response(user_input, context, provider):
                full_response.append(chunk)
                if self.on_stream_token:
                    self._emit_stream_token(chunk, self._generation_id)
                yield chunk

        # Speak and stream simultaneously — speak_stream accumulates
        # chunks until sentences are complete, then speaks each one
        await self.speaker.speak_stream(_chunk_generator())

        return "".join(full_response)

    # ── Handlers ───────────────────────────────────────────

    def _handle_personality(self, intent: Intent) -> str:
        """Handle personality mode switching."""
        mode = intent.target.lower().strip()
        result = self.prompt_builder.set_personality(mode)
        db = self._ensure_db()
        db.set_preference(
            "personality_mode", self.prompt_builder.get_personality()
        )
        return result

    def _emit_stream_token(self, token: str, generation_id: int):
        if generation_id != self._generation_id:
            return
        if self.on_stream_token:
            self.on_stream_token(token)

    def process_stream(self, user_input: str, voice_response: bool = None) -> None:
        """
        Process user input through FastRouter → AI streaming → streaming TTS.
        
        Unlike process(), this method streams AI tokens to the speaker
        sentence-by-sentence without waiting for the full response.
        
        Args:
            user_input: The text input from the user.
            voice_response: Whether to speak the response (None = use default).
        """
        if not user_input or not user_input.strip():
            return

        # Ensure DB is initialized before first process
        self._ensure_db()

        user_input = user_input.strip()
        use_voice = voice_response if voice_response is not None else self._voice_mode

        t0 = time.perf_counter()

        # Try FastRouter first
        fast_method, fast_groups = self.fast_router.match(user_input)
        if fast_method:
            t1 = time.perf_counter()
            response = self.fast_router.execute(fast_method, fast_groups)
            ms = (t1 - t0) * 1000
            logger.info(f"FastRouter: '{user_input}' → {ms:.1f}ms")
            self._emit_status("Ready")
            if use_voice and self.speaker:
                self.speaker.speak(response)
            if self.on_response:
                self.on_response(response, "fast_router")
            return

        with self._process_lock:
            self._generation_id += 1
            generation_id = self._generation_id
            self._processing = True

        if self.speaker:
            self.speaker.stop()

        logger.info("Processing (streaming): '{}'", user_input[:100])
        self._emit_status("Thinking...")

        db = self._ensure_db()
        db.save_message(self.session_id, "user", user_input)

        t1 = time.perf_counter()
        intent = self.intent_parser.parse(user_input)
        t2 = time.perf_counter()
        logger.debug("Intent: {} / {}", intent.type, intent.action)

        # For AI-requiring intents, use streaming path
        if intent.type in ("personality", "automation", "memory", "small_talk", "time_date", "screen_query"):
            # Non-AI path — use existing synchronous processing
            response = self._handle_non_streaming_intent(intent, user_input)
            if response:
                db = self._ensure_db()
                db.save_message(self.session_id, "assistant", response, metadata={"provider": "system"})
                if self.on_response:
                    self.on_response(response, "system")
                if use_voice and self.speaker:
                    self.speaker.speak(response)
                self._emit_status("Ready")
            return

        # Build prompt for AI
        prompt = self.prompt_builder.build(
            user_input=user_input,
            session_id=self.session_id,
        )
        self._emit_status("Generating response...")

        # Stream AI → TTS pipeline
        if use_voice and self.speaker:
            async def _stream_pipeline():
                full_response = []
                provider_used = "unknown"

                async for chunk in self.ai_router.stream_response(
                    prompt=user_input,
                    context=prompt.get("messages"),
                ):
                    full_response.append(chunk)
                    if self.on_stream_token:
                        self._emit_stream_token(chunk, generation_id)

                # Speak the full assembled response
                response_text = "".join(full_response).strip()
                t3 = time.perf_counter()
                if response_text:
                    self.speaker.speak(response_text)
                    t4 = time.perf_counter()
                    self._log_latency(t0, t1, t2, t3, t4)
                    db = self._ensure_db()
                    db.save_message(self.session_id, "assistant", response_text, metadata={"provider": provider_used})
                    if self.on_response:
                        self.on_response(response_text, provider_used)

                with self._process_lock:
                    if generation_id == self._generation_id:
                        self._processing = False
                self._emit_status("Ready")

            try:
                _run_async(_stream_pipeline())
            except Exception as e:
                logger.error("Stream pipeline error: {}", e)
                self._emit_status("Ready")
        else:
            # Text-only streaming path (no voice)
            response, provider = self._get_ai_response(user_input, generation_id=generation_id)
            if response:
                db = self._ensure_db()
                db.save_message(self.session_id, "assistant", response, metadata={"provider": provider})
                if self.on_response:
                    self.on_response(response, provider)
            self._emit_status("Ready")

    def _handle_non_streaming_intent(self, intent, user_input: str) -> str:
        """Handle non-AI intents synchronously (shared by process and process_stream)."""
        if intent.type == "personality":
            return self._handle_personality(intent)
        if self.intent_parser.is_automation(intent):
            return self._handle_automation(intent)
        if self.intent_parser.is_memory_op(intent):
            return self._handle_memory(intent)
        if intent.type == "small_talk":
            response, _ = self._handle_small_talk(intent)
            return response
        if intent.type == "time_date":
            return self._handle_time_date(intent)
        if intent.type == "screen_query":
            return self._handle_screen_query(intent, user_input)
        return ""

    def _log_latency(self, t0: float, t1: float, t2: float, t3: float, t4: float):
        """Log latency breakdown for performance monitoring."""
        logger.info(
            f"Latency | FastRouter: {(t1-t0)*1000:.0f}ms | "
            f"Intent: {(t2-t1)*1000:.0f}ms | "
            f"AI: {(t3-t2)*1000:.0f}ms | "
            f"TTS: {(t4-t3)*1000:.0f}ms | "
            f"Total: {(t4-t0)*1000:.0f}ms"
        )

    def _get_ai_response(
        self,
        user_input: str,
        context: str = None,
        generation_id: int = None,
    ) -> tuple[str, str]:
        """Get AI response via the router with fallback and optional streaming."""
        gen_id = generation_id if generation_id is not None else self._generation_id

        # Inject awareness context (Phase 6)
        awareness_ctx = ""
        if self.awareness_engine is not None:
            awareness_ctx = self.awareness_engine.get_context_for_prompt()

        extra_ctx = context if context else ""
        if awareness_ctx:
            if extra_ctx:
                extra_ctx = f"{extra_ctx}\n[System Context: {awareness_ctx}]"
            else:
                extra_ctx = awareness_ctx

        prompt = self.prompt_builder.build(
            user_input=user_input,
            session_id=self.session_id,
            extra_context=extra_ctx,
        )
        self._emit_status("Generating response...")
        logger.info("LIFECYCLE | ROUTER START | gen={}", gen_id)

        if self.on_stream_token:
            self._emit_stream_token("__DREX_STREAM_START__", gen_id)

            first_token_seen = False

            def on_token(token: str):
                nonlocal first_token_seen
                if not first_token_seen:
                    first_token_seen = True
                    logger.info("LIFECYCLE | FIRST TOKEN | gen={}", gen_id)
                self._emit_stream_token(token, gen_id)

            response, provider = self.ai_router.generate_stream(
                messages=prompt["messages"],
                system_prompt=prompt["system"],
                user_input=user_input,
                on_token=on_token,
            )

            if gen_id == self._generation_id:
                self._emit_stream_token("__DREX_STREAM_END__", gen_id)
                logger.info(
                    "LIFECYCLE | LAST TOKEN → STREAM COMPLETE | gen={} | provider={} | {} chars",
                    gen_id, provider, len(response or ""),
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
        db = self._ensure_db()
        if intent.action == "remember":
            db.save_fact("user_notes", intent.target[:50], intent.target)
            return f"Got it, I'll remember that: {intent.target}"

        elif intent.action == "recall":
            facts = db.get_facts()
            history = db.search_history(intent.target, limit=3)
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
            db.set_preference("user_name", name)
            db.save_fact("identity", "name", name)
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

    # ── Screen Awareness ──────────────────────────────────

    def _handle_screen_query(self, intent: Intent, user_input: str) -> str:
        """
        Handle screen awareness queries from the user.

        Routes to the appropriate screen analysis method based on intent action.
        ScreenCapture and VisionAnalyzer are lazy-loaded on first call.
        """
        action = intent.action

        if action == "screenshot":
            screen = self._lazy_init_screen_capture()
            if not screen or not screen.available:
                return "Screen capture is not available on this system."
            path = screen.save_screenshot()
            if path:
                return f"I've saved a screenshot to: {path}"
            return "Failed to save screenshot."

        if action == "read_text":
            vision = self._lazy_init_vision_analyzer()
            if not vision or not vision.available:
                return "Vision analysis is not available. I cannot read your screen."
            try:
                self._emit_status("Reading your screen...")
                screen = self._lazy_init_screen_capture()
                if not screen:
                    return "Screen capture is not available."
                image = screen.capture_full()
                text = vision.extract_text_from_image(image)
                self._emit_status("Ready")
                if text:
                    return f"I can see the following text on your screen:\n\n{text}"
                return "I can see your screen, but I don't detect any text on it."
            except Exception as e:
                logger.error("Screen read failed: {}", e)
                return "I encountered an error reading your screen."

        if action == "active_app":
            vision = self._lazy_init_vision_analyzer()
            if not vision or not vision.available:
                return "Vision analysis is not available."
            try:
                self._emit_status("Checking what app is open...")
                result = self.analyze_current_screen()
                self._emit_status("Ready")
                if result.get("active_app"):
                    return f"Based on what I see, you are using: {result['active_app']}"
                if result.get("description"):
                    return f"Looking at your screen: {result['description'][:200]}"
                return "I can see your screen, but I'm not sure what application is active."
            except Exception as e:
                logger.error("Active app detection failed: {}", e)
                return "I encountered an error detecting the active application."

        # Default: describe the screen or answer a question
        # Use AwarenessEngine if available (Phase 6)
        if self.awareness_engine is not None:
            try:
                return self.awareness_engine.describe_screen()
            except Exception as e:
                logger.error("AwarenessEngine screen query failed: {}", e)

        # Fallback: lazy-init screen modules
        vision = self._lazy_init_vision_analyzer()
        if not vision or not vision.available:
            return "I cannot see your screen right now — screen analysis is not available."

        try:
            return self.answer_screen_question(user_input)
        except Exception as e:
            logger.error("Screen query failed: {}", e)
            return "I encountered an error analyzing your screen. Please try again."

    def analyze_current_screen(self) -> dict:
        """
        Captures and analyzes the current screen state.
        Lazy-initializes ScreenCapture and VisionAnalyzer on first call.

        Returns:
            Dict with screen analysis results, or error dict on failure.
        """
        screen = self._lazy_init_screen_capture()
        if not screen or not screen.available:
            return {"error": "Screen capture not available", "description": ""}
        vision = self._lazy_init_vision_analyzer()
        if not vision or not vision.available:
            return {"error": "Vision analysis not available", "description": ""}

        try:
            self._emit_status("Capturing screen...")
            image = screen.capture_full()
            logger.info("Screen captured ({}x{})", image.width, image.height)

            self._emit_status("Analyzing screen...")
            result = vision.analyze_screenshot(image)
            self._emit_status("Ready")
            return result
        except Exception as e:
            logger.error("analyze_current_screen failed: {}", e)
            return {"error": str(e), "description": ""}

    def answer_screen_question(self, question: str) -> str:
        """
        Answers a user question about the current screen.
        Lazy-initializes ScreenCapture and VisionAnalyzer on first call.

        Args:
            question: Natural language question about screen content.

        Returns:
            Natural language answer string.
        """
        screen = self._lazy_init_screen_capture()
        if not screen or not screen.available:
            return "I cannot see your screen right now — screen capture is not available."
        vision = self._lazy_init_vision_analyzer()
        if not vision or not vision.available:
            return "I cannot analyze your screen right now — vision AI is not available."

        try:
            self._emit_status("Looking at your screen...")
            image = screen.capture_full()
            logger.info("Screen captured for question: '{}'", question[:60])

            self._emit_status("Analyzing...")
            answer = vision.answer_screen_question(image, question)
            self._emit_status("Ready")
            return answer
        except Exception as e:
            logger.error("answer_screen_question failed: {}", e)
            return "Sorry, I encountered an error while analyzing your screen."

    # ── Voice loop ─────────────────────────────────────────

    def _voice_process(self, text: str, request_id: str = None):
        """
        Debounced voice input handler with UUID dedup — avoids duplicate triggers.
        
        Uses two-layer dedup:
          1. UUID-based: same request_id cannot be processed twice
          2. Time-based: 1.5s debounce window prevents rapid re-triggers
        
        Self-speech filtering: ignores input while speaker is active or
        during the post-TTS cooldown period to prevent DREX from
        hearing and responding to its own voice.
        
        Includes voice latency logging:
          STT latency = time from voice input to processing start
          
        Args:
            text: Transcribed speech text
            request_id: Unique UUID for this voice input (generated if not provided)
        """
        if not text or not text.strip():
            return

        # ── Self-speech filtering ─────────────────────────────
        # Reject input while DREX is speaking or during post-speech cooldown
        if self.speaker and getattr(self.speaker, "is_speaking", False):
            logger.debug("Voice input rejected — speaker is active")
            return

        now = time.time()
        if now - self._last_voice_at < self._voice_debounce_sec and self._last_voice_at > 0:
            logger.debug("Voice input debounced (cooldown)")
            return
        
        # Generate request_id if not provided (listen_once path)
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        # Layer 1: UUID dedup — reject exact same request
        if request_id == self._last_request_id:
            logger.debug("Duplicate voice request (UUID match) — rejected")
            return
        
        # Layer 2: Time-based debounce — reject rapid re-triggers
        if now - self._last_voice_at < self._voice_debounce_sec:
            logger.debug("Voice input debounced (time window)")
            return
        
        # ── Duplicate text filtering ──────────────────────────
        # Google STT sometimes fires the same transcription twice in quick succession
        clean_text = text.strip()
        if hasattr(self, "_last_voice_text") and self._last_voice_text == clean_text:
            text_age = now - getattr(self, "_last_voice_text_time", 0)
            if text_age < 3.0:
                logger.debug("Voice input rejected — duplicate text in {}s", text_age)
                return
        self._last_voice_text = clean_text
        self._last_voice_text_time = now
        
        # Voice Latency Logging: STT completion → processing start
        stt_latency = (now - self._last_voice_at) * 1000 if self._last_voice_at > 0 else 0
        logger.info(f"Voice Latency | STT: {stt_latency:.0f}ms (from voice input to process)")
        
        # Accept this request
        self._last_request_id = request_id
        self._last_voice_at = now
        self.voice_state.state = VoiceState.PROCESSING
        
        # Notify GUI of voice input (so it can display user message + streaming label)
        if self.on_voice_input:
            self.on_voice_input(clean_text)
        
        t_ai_start = time.perf_counter()
        self.process(clean_text, voice_response=True)
        t_ai_end = time.perf_counter()
        
        # AI routing latency logging
        ai_routing_latency = (t_ai_end - t_ai_start) * 1000
        logger.info(f"Voice Latency | AI Routing: {ai_routing_latency:.0f}ms")
        
        # Return to listening state after processing
        self.voice_state.state = VoiceState.LISTENING

    def start_voice_loop(self):
        """
        Start the voice listening loop.

        If conversation mode is enabled, use the duplex ConversationEngine
        (automatic turn detection, no button presses needed).
        If wake word is enabled, starts the wake word detector.
        Otherwise, falls back to standard continuous listening mode.
        """
        if self._running:
            logger.debug("Voice loop already running")
            return

        if not self.listener or not self.listener.is_available:
            logger.warning(
                "Voice loop unavailable — microphone not accessible"
            )
            return

        # ── Duplex Conversation Mode (Phase 8) ──
        if self._conversation_mode:
            self._start_conversation_mode()
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
            # Run through post-processor for better accuracy
            clean = self._apply_post_processing(text)
            request_id = str(uuid.uuid4())
            self._voice_process(clean, request_id=request_id)

        self.listener.start_continuous(callback=on_speech)
        self._running = True
        logger.info("Voice loop started (continuous mode)")

    def _start_conversation_mode(self):
        """
        Start the duplex conversation engine for ChatGPT-like voice mode.

        The ConversationEngine handles:
          - Continuous audio capture
          - Automatic speech/silence turn detection
          - VAD-based endpointing
          - Interruption (barge-in) detection
          - Automatic listen→speak→listen cycling
        """
        engine = self.conversation_engine
        if engine is None:
            logger.error("ConversationEngine unavailable, falling back to continuous")
            self._start_continuous_mode()
            return

        if self.speaker:
            engine.wire_speaker(self.speaker)

        engine.on_speech_start = lambda: self._emit_status("DREX is listening...")
        engine.on_state_change = lambda old, new: logger.debug("ConvEngine: {} → {}", old, new)

        engine.on_interruption = lambda: self.cancel_pending_generation()

        def on_utterance(text: str):
            clean = self._apply_post_processing(text)
            self._emit_status("Processing...")
            self.cancel_pending_generation()
            engine.pause()
            self._voice_process(clean)
            engine.resume()

        engine.on_utterance = on_utterance
        engine.start(on_utterance=on_utterance)
        self._running = True
        self._emit_status("Conversation mode active — talk naturally")
        logger.info("Voice loop started (duplex conversation mode)")

    def _apply_post_processing(self, text: str) -> str:
        """Apply STT post-processing (Tier 1) for cleaner text."""
        if self._post_processor:
            return self._post_processor.clean_for_ai(text)
        return text

    def set_conversation_mode(self, enabled: bool):
        """
        Toggle ChatGPT-like continuous conversation mode.

        When enabled, the ConversationEngine handles turn detection
        automatically — no need to press a button after every sentence.
        """
        self._conversation_mode = enabled
        if self._running:
            self.stop_voice_loop()
            if enabled:
                self.start_voice_loop()
        logger.info("Conversation mode: {}", "ON" if enabled else "OFF")

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
                text = self._apply_post_processing(text)
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
        # Stop conversation engine
        if self._conversation_engine:
            try:
                self._conversation_engine.stop()
            except Exception as e:
                logger.debug("Error stopping conversation engine: {}", e)

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

    # ── Deduplication ────────────────────────────────────

    def _is_duplicate(self, text: str) -> bool:
        """
        Returns True if identical request was processed
        within the last 2 seconds.

        Prevents double-processing from voice recognition glitches
        or rapid button clicks. Covers ALL input (text + voice),
        unlike the UUID-based dedup in _voice_process() which is
        voice-only.
        """
        key = hashlib.md5(text.strip().lower().encode()).hexdigest()
        now = time.time()
        if key in self._recent_requests:
            if now - self._recent_requests[key] < self._dedup_window:
                logger.warning("Duplicate request blocked: {!r}", text)
                return True
        self._recent_requests[key] = now
        # Clean up old entries
        self._recent_requests = {
            k: v for k, v in self._recent_requests.items()
            if now - v < self._dedup_window
        }
        return False

    # ── Phase 5C: Planning / Confirmation / Execution ──────

    # Phrases that are always info-seeking or conversational — never plans
    _INFO_SEEKING_PHRASES: list[str] = [
        "compare", "explain", "tell me about", "tell me how",
        "what is", "what are", "what does", "what do",
        "how to", "how do", "how does", "how are", "how is",
        "how much", "how many", "how long", "how far",
        "why is", "why are", "why do", "why does",
        "when is", "when was", "when will",
        "where is", "where can", "where do",
        "who is", "who was",
        "which is", "which are",
        "difference between", "vs ", " versus ",
        "give me", "show me", "list", "summarize",
        "translate",
        "what do you", "how can i",
        "do you know", "do you have",
    ]

    # Action verbs that indicate the user is asking DREX to DO something
    _TASK_ACTION_VERBS: set[str] = {
        "create", "build", "make", "write", "develop", "implement",
        "generate", "install", "setup", "set up", "configure", "deploy",
        "launch", "open", "close", "save", "delete", "remove", "add", "update",
        "fix", "debug", "refactor", "test", "scan", "analyze",
        "download", "upload", "copy", "move", "rename", "search",
        "book", "schedule", "send", "share", "publish", "commit",
        "push", "pull", "merge", "organize", "sort", "filter",
        "extract", "compile", "convert", "transform", "translate",
        "start", "stop", "restart", "run", "execute",
    }

    def _should_plan(self, user_input: str) -> bool:
        """
        Determine if user input needs multi-step planning.

        Think like ChatGPT: Answer first, plan only when execution is required.

        Returns True ONLY when the user is explicitly asking DREX to DO something
        that requires multiple steps, AND either:
          1. Multi-step keywords are detected ("then", "step by step", etc.)
          2. A specific domain template matches (website, react, python, etc.)

        NEVER triggers on:
          - Questions (even with multi-step keywords)
          - Comparisons ("compare X vs Y")
          - Explanations ("how does X work", "what is Y")
          - Small talk ("how are you")
          - Info-seeking ("tell me about", "give me a list of")
          - "Show me how to X" (this is explanation, not execution)
        """
        if self.planner is None:
            return False

        input_lower = user_input.lower().strip()
        if not input_lower:
            return False

        # ── Explicit rejection: info-seeking / conversational ──
        if self._is_info_seeking(input_lower):
            return False

        # ── Questions are never plans ──
        if input_lower.endswith("?"):
            return False

        # ── Must contain an action verb asking DREX to DO something ──
        if not self._has_task_action(input_lower):
            return False

        # ── Multi-step keywords: explicit planning intent ──
        for kw in self.MULTI_STEP_KEYWORDS:
            if kw in input_lower:
                return True

        # ── Domain template match via GoalDecomposer ──
        # decompose_or_none returns None unless a SPECIFIC domain matches
        steps = self.planner._decomposer.decompose_or_none(user_input)
        if steps is not None and len(steps) > 1:
            return True

        return False

    def _is_info_seeking(self, input_lower: str) -> bool:
        """Check if input is asking for information, not execution."""
        for phrase in self._INFO_SEEKING_PHRASES:
            if phrase in input_lower:
                return True
        return False

    def _has_task_action(self, input_lower: str) -> bool:
        """Check if input contains an action verb that implies the user wants DREX to DO something."""
        words = input_lower.split()
        if not words:
            return False

        if words[0] in self._TASK_ACTION_VERBS:
            return True

        if "please" in words[:2]:
            remaining = [w for w in words if w != "please"]
            if remaining and remaining[0] in self._TASK_ACTION_VERBS:
                return True

        for verb in ("would you", "could you", "can you", "will you"):
            if input_lower.startswith(verb):
                rest = input_lower[len(verb):].strip()
                first_word = rest.split()[0] if rest.split() else ""
                if first_word in self._TASK_ACTION_VERBS:
                    return True

        return False

    def _handle_confirmation(self, text: str):
        """
        Handle user confirmation response for pending execution.

        Args:
            text: The user's confirmation input

        Returns:
            Tuple of (decision: bool|None, response: str)
            True = proceed, False = cancel, None = ambiguous
        """
        text_lower = text.lower().strip().rstrip(".!?")
        if text_lower in self._CONFIRM_YES:
            return (True, "")
        if text_lower in self._CONFIRM_NO:
            return (False, "")
        return (None, "")

    # ── Utilities ──────────────────────────────────────────

    def _emit_status(self, msg: str):
        if self.on_status:
            self.on_status(msg)

    def get_ai_status(self) -> dict:
        return self.ai_router.get_status()

    def get_session_info(self) -> dict:
        db = self._ensure_db()
        return {
            "session_id": self.session_id,
            "user_name": self._user_name,
            "voice_mode": self._voice_mode,
            "personality": self.prompt_builder.get_personality(),
            "started": datetime.now().isoformat(),
            "total_sessions": db.get_session_count(),
        }

    def set_voice_mode(self, enabled: bool):
        self._voice_mode = enabled
        if not enabled:
            self.stop_voice_loop()

    def switch_ai_provider(self, provider: str):
        self.cfg.ai.default_provider = provider
        self.ai_router.reset_status()
        logger.info("AI provider switched to: {}", provider)

    def new_session(self) -> str:
        """End current session and create a new one. Returns new session_id."""
        db = self._ensure_db()
        if self.session_id:
            db.end_session(self.session_id)
        self.session_id = str(uuid.uuid4())[:8]
        db.start_session(self.session_id)
        logger.info("New session: {}", self.session_id)
        return self.session_id

    def switch_session(self, session_id: str):
        """Switch to an existing session (loads context for AI memory)."""
        self.session_id = session_id
        db = self._ensure_db()
        db.start_session(session_id)

    def shutdown(self):
        """Clean shutdown of all modules. Idempotent and thread-safe."""
        logger.info("DREX shutting down...")

        # Stop voice loops first
        self.stop_voice_loop()

        # Shutdown conversation engine
        if self._conversation_engine:
            try:
                self._conversation_engine.shutdown()
            except Exception as e:
                logger.debug("ConversationEngine shutdown error: {}", e)

        # End database session
        if self.db is not None:
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