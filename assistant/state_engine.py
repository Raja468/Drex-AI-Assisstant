# ============================================================
#  DREX - AI Assistant Runtime
#  assistant/state_engine.py  —  Assistant State Machine
#
#  Central state machine for the assistant runtime.
#  Manages state transitions, mode switching, and notifications.
#
#  States:
#  - IDLE: Waiting for input
#  - LISTENING: Microphone active, waiting for speech
#  - THINKING: Processing user input, generating response
#  - SPEAKING: TTS playback in progress
#  - EXECUTING: Running automation task
#  - MUTED: Microphone disabled
#  - ERROR: Recovery mode
#  - MINIMIZED: Tray mode, still listening
#
#  Modes:
#  - AGENT: Voice-first, floating UI, realtime
#  - CHAT: Text-first, chat bubbles, long-form
# ============================================================

from enum import Enum, auto
from typing import Callable, Optional
import threading
from loguru import logger


class AssistantState(Enum):
    """Assistant operational states."""
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()
    EXECUTING = auto()
    MUTED = auto()
    ERROR = auto()
    MINIMIZED = auto()


class AssistantMode(Enum):
    """Assistant interaction modes."""
    AGENT = auto()  # Voice-first, floating UI
    CHAT = auto()   # Text-first, chat window


# State transition rules
VALID_TRANSITIONS = {
    AssistantState.IDLE: [
        AssistantState.LISTENING,
        AssistantState.THINKING,
        AssistantState.MUTED,
        AssistantState.MINIMIZED,
        AssistantState.ERROR,
    ],
    AssistantState.LISTENING: [
        AssistantState.IDLE,
        AssistantState.THINKING,
        AssistantState.MUTED,
        AssistantState.ERROR,
    ],
    AssistantState.THINKING: [
        AssistantState.IDLE,
        AssistantState.SPEAKING,
        AssistantState.EXECUTING,
        AssistantState.LISTENING,  # Interruption
        AssistantState.ERROR,
    ],
    AssistantState.SPEAKING: [
        AssistantState.IDLE,
        AssistantState.LISTENING,  # Interruption
        AssistantState.EXECUTING,
        AssistantState.ERROR,
    ],
    AssistantState.EXECUTING: [
        AssistantState.IDLE,
        AssistantState.SPEAKING,
        AssistantState.ERROR,
    ],
    AssistantState.MUTED: [
        AssistantState.IDLE,
        AssistantState.LISTENING,
        AssistantState.ERROR,
    ],
    AssistantState.ERROR: [
        AssistantState.IDLE,
    ],
    AssistantState.MINIMIZED: [
        AssistantState.IDLE,
        AssistantState.LISTENING,
        AssistantState.ERROR,
    ],
}


class StateEngine:
    """
    Central state machine for the assistant runtime.
    
    Thread-safe state management with callback notifications.
    
    Usage:
        engine = StateEngine()
        engine.register_callback(my_callback)
        engine.state = AssistantState.LISTENING
    """
    
    def __init__(self):
        self._state = AssistantState.IDLE
        self._mode = AssistantMode.AGENT
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        self._state_callbacks: list[Callable] = []
        self._mode_callbacks: list[Callable] = []
        self._history: list[tuple[AssistantState, AssistantState]] = []
        self._max_history = 100
        
        logger.debug("StateEngine initialized | state={} mode={}", 
                     self._state.name, self._mode.name)
    
    # ── State Property ────────────────────────────────────────
    
    @property
    def state(self) -> AssistantState:
        """Get current assistant state."""
        with self._lock:
            return self._state
    
    @state.setter
    def state(self, new_state: AssistantState):
        """
        Set assistant state with validation.
        
        Invalid transitions are logged but not blocked to allow
        recovery from unexpected conditions.
        """
        with self._lock:
            old_state = self._state
            
            if old_state == new_state:
                return  # No change
            
            # Validate transition
            valid_targets = VALID_TRANSITIONS.get(old_state, [])
            if new_state not in valid_targets:
                logger.warning(
                    "Unusual state transition: {} → {} (expected: {})",
                    old_state.name, new_state.name,
                    [s.name for s in valid_targets]
                )
            
            # Record history
            self._history.append((old_state, new_state))
            if len(self._history) > self._max_history:
                self._history.pop(0)
            
            # Update state
            self._state = new_state
            logger.debug("State: {} → {}", old_state.name, new_state.name)
            
            # Notify callbacks
            self._notify_state_change(old_state, new_state)
    
    # ── Mode Property ─────────────────────────────────────────
    
    @property
    def mode(self) -> AssistantMode:
        """Get current assistant mode."""
        with self._lock:
            return self._mode
    
    def switch_mode(self, new_mode: AssistantMode) -> bool:
        """
        Switch between Agent and Chat modes.
        
        Returns True if mode was changed, False if already in that mode.
        """
        with self._lock:
            old_mode = self._mode
            
            if old_mode == new_mode:
                return False
            
            self._mode = new_mode
            logger.info("Mode: {} → {}", old_mode.name, new_mode.name)
            
            # Notify callbacks
            self._notify_mode_change(old_mode, new_mode)
            return True
    
    # ── State Queries ─────────────────────────────────────────
    
    def can_listen(self) -> bool:
        """Can we start listening? Only if idle or minimized."""
        with self._lock:
            return self._state in (
                AssistantState.IDLE,
                AssistantState.MINIMIZED,
            )
    
    def can_speak(self) -> bool:
        """Can we start speaking? Not if listening or muted."""
        with self._lock:
            return self._state not in (
                AssistantState.LISTENING,
                AssistantState.MUTED,
            )
    
    def can_interrupt(self) -> bool:
        """Can the user interrupt? Yes if speaking or thinking."""
        with self._lock:
            return self._state in (
                AssistantState.SPEAKING,
                AssistantState.THINKING,
            )
    
    def can_process(self) -> bool:
        """Can we process new input? Yes if idle or listening."""
        with self._lock:
            return self._state in (
                AssistantState.IDLE,
                AssistantState.LISTENING,
                AssistantState.MINIMIZED,
            )
    
    def is_active(self) -> bool:
        """Is the assistant actively processing or responding?"""
        with self._lock:
            return self._state in (
                AssistantState.THINKING,
                AssistantState.SPEAKING,
                AssistantState.EXECUTING,
            )
    
    def is_listening(self) -> bool:
        """Is the assistant currently listening for speech?"""
        with self._lock:
            return self._state == AssistantState.LISTENING
    
    def is_speaking(self) -> bool:
        """Is the assistant currently speaking?"""
        with self._lock:
            return self._state == AssistantState.SPEAKING
    
    def is_muted(self) -> bool:
        """Is the microphone muted?"""
        with self._lock:
            return self._state == AssistantState.MUTED
    
    # ── Callbacks ─────────────────────────────────────────────
    
    def register_state_callback(self, callback: Callable[[AssistantState, AssistantState], None]):
        """
        Register a callback for state changes.
        
        Callback signature: callback(old_state, new_state)
        """
        with self._lock:
            self._state_callbacks.append(callback)
    
    def register_mode_callback(self, callback: Callable[[AssistantMode, AssistantMode], None]):
        """
        Register a callback for mode changes.
        
        Callback signature: callback(old_mode, new_mode)
        """
        with self._lock:
            self._mode_callbacks.append(callback)
    
    def unregister_state_callback(self, callback: Callable):
        """Remove a state change callback."""
        with self._lock:
            if callback in self._state_callbacks:
                self._state_callbacks.remove(callback)
    
    def unregister_mode_callback(self, callback: Callable):
        """Remove a mode change callback."""
        with self._lock:
            if callback in self._mode_callbacks:
                self._mode_callbacks.remove(callback)
    
    def _notify_state_change(self, old: AssistantState, new: AssistantState):
        """Notify all registered state callbacks."""
        for callback in self._state_callbacks:
            try:
                callback(old, new)
            except Exception as e:
                logger.error("State callback error: {}", e)
    
    def _notify_mode_change(self, old: AssistantMode, new: AssistantMode):
        """Notify all registered mode callbacks."""
        for callback in self._mode_callbacks:
            try:
                callback(old, new)
            except Exception as e:
                logger.error("Mode callback error: {}", e)
    
    # ── History ───────────────────────────────────────────────
    
    def get_history(self, limit: int = 10) -> list[tuple[str, str]]:
        """
        Get recent state transition history.
        
        Returns list of (old_state, new_state) tuples as strings.
        """
        with self._lock:
            recent = self._history[-limit:]
            return [(old.name, new.name) for old, new in recent]
    
    def clear_history(self):
        """Clear state transition history."""
        with self._lock:
            self._history.clear()
    
    # ── Utilities ─────────────────────────────────────────────
    
    def get_state_info(self) -> dict:
        """Get comprehensive state information."""
        with self._lock:
            return {
                "state": self._state.name,
                "mode": self._mode.name,
                "can_listen": self.can_listen(),
                "can_speak": self.can_speak(),
                "can_interrupt": self.can_interrupt(),
                "can_process": self.can_process(),
                "is_active": self.is_active(),
                "history_count": len(self._history),
            }
    
    def reset(self):
        """Reset to initial state (IDLE, AGENT mode)."""
        with self._lock:
            self._state = AssistantState.IDLE
            self._mode = AssistantMode.AGENT
            self._history.clear()
            logger.info("StateEngine reset to initial state")
    
    def __repr__(self) -> str:
        return f"StateEngine(state={self._state.name}, mode={self._mode.name})"