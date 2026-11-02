# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/mode_manager.py  —  Agent/Chat Mode Manager
#
#  Manages switching between Agent Mode and Chat Mode.
#  
#  Agent Mode (Primary):
#  - Voice-first interaction
#  - Floating UI / compact panel
#  - Continuous listening
#  - Realtime responses
#  - Interruption support
#
#  Chat Mode (Secondary):
#  - Text-first interaction
#  - Full chat window
#  - Markdown support
#  - Long-form reasoning
#  - Document analysis
# ============================================================

from typing import Callable, Optional
import threading
from loguru import logger

from assistant.state_engine import StateEngine, AssistantMode, AssistantState


class ModeManager:
    """
    Manages Agent/Chat mode switching and mode-specific behavior.
    
    Coordinates between:
    - StateEngine (for state tracking)
    - GUI (for UI switching)
    - Voice pipeline (for mode-specific behavior)
    
    Usage:
        manager = ModeManager(state_engine)
        manager.switch_to_agent()
        manager.switch_to_chat()
    """
    
    def __init__(self, state_engine: StateEngine):
        self.state_engine = state_engine
        self._lock = threading.RLock()
        
        # Mode-specific callbacks
        self._on_agent_activate: Optional[Callable] = None
        self._on_chat_activate: Optional[Callable] = None
        self._on_mode_change: Optional[Callable[[AssistantMode], None]] = None
        
        # Mode preferences
        self._agent_auto_listen = True  # Auto-start listening in Agent mode
        self._chat_preserve_history = True  # Keep history when switching
        
        logger.debug("ModeManager initialized | mode={}", 
                     self.state_engine.mode.name)
    
    # ── Mode Switching ────────────────────────────────────────
    
    def switch_to_agent(self) -> bool:
        """
        Switch to Agent Mode.
        
        Agent Mode characteristics:
        - Voice-first interaction
        - Floating UI
        - Continuous listening
        - Realtime responses
        
        Returns True if mode was changed.
        """
        with self._lock:
            if self.state_engine.mode == AssistantMode.AGENT:
                logger.debug("Already in Agent mode")
                return False
            
            logger.info("Switching to Agent mode...")
            
            # Switch mode in state engine
            changed = self.state_engine.switch_mode(AssistantMode.AGENT)
            
            if changed:
                # Activate Agent-specific behavior
                self._activate_agent_mode()
                
                # Notify callback
                if self._on_mode_change:
                    try:
                        self._on_mode_change(AssistantMode.AGENT)
                    except Exception as e:
                        logger.error("Mode change callback error: {}", e)
            
            return changed
    
    def switch_to_chat(self) -> bool:
        """
        Switch to Chat Mode.
        
        Chat Mode characteristics:
        - Text-first interaction
        - Full chat window
        - Markdown support
        - Long-form reasoning
        
        Returns True if mode was changed.
        """
        with self._lock:
            if self.state_engine.mode == AssistantMode.CHAT:
                logger.debug("Already in Chat mode")
                return False
            
            logger.info("Switching to Chat mode...")
            
            # Switch mode in state engine
            changed = self.state_engine.switch_mode(AssistantMode.CHAT)
            
            if changed:
                # Activate Chat-specific behavior
                self._activate_chat_mode()
                
                # Notify callback
                if self._on_mode_change:
                    try:
                        self._on_mode_change(AssistantMode.CHAT)
                    except Exception as e:
                        logger.error("Mode change callback error: {}", e)
            
            return changed
    
    def toggle_mode(self) -> AssistantMode:
        """
        Toggle between Agent and Chat modes.
        
        Returns the new mode.
        """
        if self.state_engine.mode == AssistantMode.AGENT:
            self.switch_to_chat()
            return AssistantMode.CHAT
        else:
            self.switch_to_agent()
            return AssistantMode.AGENT
    
    # ── Mode Activation ───────────────────────────────────────
    
    def _activate_agent_mode(self):
        """Activate Agent mode specific behavior."""
        logger.debug("Activating Agent mode...")
        
        # Call Agent activation callback
        if self._on_agent_activate:
            try:
                self._on_agent_activate()
            except Exception as e:
                logger.error("Agent activation callback error: {}", e)
        
        # In Agent mode, we might want to auto-start listening
        if self._agent_auto_listen and self.state_engine.can_listen():
            logger.debug("Agent mode: auto-listen enabled")
            # The actual listening start is handled by the orchestrator
    
    def _activate_chat_mode(self):
        """Activate Chat mode specific behavior."""
        logger.debug("Activating Chat mode...")
        
        # Call Chat activation callback
        if self._on_chat_activate:
            try:
                self._on_chat_activate()
            except Exception as e:
                logger.error("Chat activation callback error: {}", e)
        
        # In Chat mode, we might want to stop continuous listening
        # (but keep single-utterance listening available)
    
    # ── Callbacks ─────────────────────────────────────────────
    
    def set_agent_callback(self, callback: Callable):
        """
        Set callback for Agent mode activation.
        
        Callback is called when switching TO Agent mode.
        Use this to show floating UI, start listening, etc.
        """
        with self._lock:
            self._on_agent_activate = callback
    
    def set_chat_callback(self, callback: Callable):
        """
        Set callback for Chat mode activation.
        
        Callback is called when switching TO Chat mode.
        Use this to show chat window, stop continuous listening, etc.
        """
        with self._lock:
            self._on_chat_activate = callback
    
    def set_mode_change_callback(self, callback: Callable[[AssistantMode], None]):
        """
        Set callback for any mode change.
        
        Callback signature: callback(new_mode)
        """
        with self._lock:
            self._on_mode_change = callback
    
    # ── Mode Queries ──────────────────────────────────────────
    
    def is_agent_mode(self) -> bool:
        """Check if currently in Agent mode."""
        return self.state_engine.mode == AssistantMode.AGENT
    
    def is_chat_mode(self) -> bool:
        """Check if currently in Chat mode."""
        return self.state_engine.mode == AssistantMode.CHAT
    
    def get_mode(self) -> AssistantMode:
        """Get current mode."""
        return self.state_engine.mode
    
    def get_mode_name(self) -> str:
        """Get current mode name as string."""
        return self.state_engine.mode.name
    
    # ── Mode Preferences ──────────────────────────────────────
    
    def set_auto_listen(self, enabled: bool):
        """
        Enable/disable auto-listening in Agent mode.
        
        When enabled, Agent mode automatically starts listening
        when activated.
        """
        self._agent_auto_listen = enabled
        logger.debug("Agent auto-listen: {}", enabled)
    
    def set_preserve_history(self, enabled: bool):
        """
        Enable/disable history preservation when switching modes.
        
        When enabled, conversation history is kept when switching
        between Agent and Chat modes.
        """
        self._chat_preserve_history = enabled
        logger.debug("Chat preserve history: {}", enabled)
    
    # ── Mode-Specific Behavior ────────────────────────────────
    
    def should_use_voice(self) -> bool:
        """
        Should we use voice for responses?
        
        Agent mode: Yes (voice-first)
        Chat mode: Optional (user preference)
        """
        return self.is_agent_mode()
    
    def should_show_floating(self) -> bool:
        """
        Should we show floating UI?
        
        Agent mode: Yes
        Chat mode: No (full window)
        """
        return self.is_agent_mode()
    
    def should_stream_tokens(self) -> bool:
        """
        Should we stream tokens to UI?
        
        Both modes support streaming, but Agent mode
        prioritizes low latency.
        """
        return True  # Both modes stream
    
    def get_response_style(self) -> str:
        """
        Get preferred response style for current mode.
        
        Agent mode: Concise, conversational
        Chat mode: Detailed, formatted
        """
        if self.is_agent_mode():
            return "concise"
        else:
            return "detailed"
    
    # ── Utilities ─────────────────────────────────────────────
    
    def get_mode_info(self) -> dict:
        """Get comprehensive mode information."""
        return {
            "mode": self.get_mode_name(),
            "is_agent": self.is_agent_mode(),
            "is_chat": self.is_chat_mode(),
            "auto_listen": self._agent_auto_listen,
            "preserve_history": self._chat_preserve_history,
            "use_voice": self.should_use_voice(),
            "show_floating": self.should_show_floating(),
            "response_style": self.get_response_style(),
        }
    
    def __repr__(self) -> str:
        return f"ModeManager(mode={self.get_mode_name()})"