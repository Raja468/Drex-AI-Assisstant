"""
core/permission.py — Security & Approval Layer for DREX Automation

WHAT IT DOES:
  - Classifies automation actions by risk level (SAFE / DANGEROUS / CRITICAL)
  - Requires explicit user confirmation before executing risky operations
  - Provides callback hooks for GUI to display approval dialogs
  - Prevents unauthorized command execution, file deletion, system changes

USAGE:
    from core.permission import PermissionManager, ActionRisk
    
    perm = PermissionManager()
    risk = perm.classify_action("shutdown")
    if risk == ActionRisk.SAFE:
        execute()
    else:
        perm.request_approval("shutdown", callback=on_approve_or_deny)

INTEGRATION:
  - TaskHandler calls PermissionManager before executing risky automation
  - GUI registers a confirmation dialog callback for visual prompts
  - All actions are logged for audit trail
  - Thread-safe for concurrent voice+GUI access
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional
from loguru import logger


class ActionRisk(Enum):
    """Risk classification for automation actions."""
    SAFE = "safe"            # No confirmation needed (e.g., volume up, open YouTube)
    DANGEROUS = "dangerous"  # User should be warned (e.g., delete file, close app)
    CRITICAL = "critical"    # Explicit approval required (e.g., shutdown, restart, file deletion)


@dataclass
class ApprovalRequest:
    """
    Represents a pending user approval request.
    
    Attributes:
        action: The action name (e.g., "shutdown", "delete_file")
        target: What the action would affect (e.g., "C:\\file.txt")
        risk: Risk level of the action
        timestamp: When the request was created
        approved: Whether the user approved (None = pending)
        callback: Function to call when approved/denied
    """
    action: str
    target: str
    risk: ActionRisk
    timestamp: float = field(default_factory=time.time)
    approved: Optional[bool] = None
    callback: Optional[Callable[[bool], None]] = None


class PermissionManager:
    """
    Security layer that controls which automation actions can execute.
    
    Features:
      - Risk classification for all automation actions
      - User approval workflow with callback hooks
      - Configurable auto-approve for safe actions
      - Audit logging of all decisions
      - Thread-safe approval state management
    """

    # Actions that are always safe and need no confirmation
    SAFE_ACTIONS = {
        "volume_up", "volume_down", "mute", "volume_mute", "volume_set",
        "brightness_up", "brightness_down", "brightness_set",
        "system_info", "clipboard_read",
        "open", "search", "open_url", "open_site", "new_tab",
        "youtube", "weather", "get_weather", "get_news",
        "current_time", "current_date", "set_timer",
        "find_file", "list_directory", "get_file_info",
        "greeting", "farewell", "thanks", "how_are_you",
        "identity", "capabilities",
        "play", "pause", "next_track", "prev_track",
    }

    # Actions that need explicit user confirmation
    DANGEROUS_ACTIONS = {
        "shutdown", "restart", "sleep", "lock",
        "delete_file", "empty_trash", "create_file", "create_folder",
        "close", "close_app", "kill",
        "screenshot",  # Screenshots capture potentially sensitive data
    }

    # Actions that require strict approval
    CRITICAL_ACTIONS = {
        "shutdown", "restart",
        "delete_file", "empty_trash",
    }

    def __init__(self, auto_approve_safe: bool = True):
        self._auto_approve_safe = auto_approve_safe
        self._pending_approval: Optional[ApprovalRequest] = None
        self._lock = threading.Lock()
        
        # Optional callback for GUI to display confirmation dialog
        # Callback receives: (action_name, risk_level, target, approve_fn, deny_fn)
        self.on_approval_required: Optional[Callable[[str, str, str, Callable, Callable], None]] = None
        
        logger.info("✅ PermissionManager initialized (auto-approve safe: {})", auto_approve_safe)

    def classify_action(self, action: str) -> ActionRisk:
        """
        Determine the risk level of an automation action.
        
        Args:
            action: The action name from the Intent parser
            
        Returns:
            ActionRisk level (SAFE, DANGEROUS, or CRITICAL)
        """
        action_lower = action.lower().strip()
        
        if action_lower in self.CRITICAL_ACTIONS:
            return ActionRisk.CRITICAL
        elif action_lower in self.DANGEROUS_ACTIONS:
            return ActionRisk.DANGEROUS
        else:
            return ActionRisk.SAFE

    def requires_approval(self, action: str, target: str = "") -> bool:
        """
        Check if an action requires user approval before execution.
        
        Args:
            action: The action to check
            target: What the action targets (for context)
            
        Returns:
            True if the action needs approval, False if it can execute freely
        """
        risk = self.classify_action(action)
        
        if self._auto_approve_safe and risk == ActionRisk.SAFE:
            return False
        
        return risk in (ActionRisk.DANGEROUS, ActionRisk.CRITICAL)

    def request_approval(
        self,
        action: str,
        target: str = "",
        callback: Optional[Callable[[bool], None]] = None,
    ) -> bool:
        """
        Request user approval for a risky action.
        
        If no approval callback is registered, automatically denies the action
        to prevent unauthorized execution.
        
        Args:
            action: The action needing approval
            target: What the action targets
            callback: Function to call with the approval result (True=approved, False=denied)
            
        Returns:
            True if auto-approved (safe action), False if pending/denied
        """
        risk = self.classify_action(action)
        
        # Safe actions execute immediately
        if self._auto_approve_safe and risk == ActionRisk.SAFE:
            return True
        
        # Log the decision
        logger.warning("⚠️  Approval required: {} '{}' [risk={}]", action, target, risk.value)
        
        # If no GUI callback registered, DENY by default (fail-safe)
        if self.on_approval_required is None:
            logger.warning(
                "⛔ No approval handler registered. Action DENIED: {} '{}'",
                action, target
            )
            return False
        
        # Create approval request
        with self._lock:
            self._pending_approval = ApprovalRequest(
                action=action,
                target=target,
                risk=risk,
                callback=callback,
            )
        
        # Notify GUI to show confirmation dialog
        request = self._pending_approval
        
        def approve():
            """User approved the action."""
            with self._lock:
                if self._pending_approval:
                    self._pending_approval.approved = True
                    cb = self._pending_approval.callback
                    self._pending_approval = None
                    if cb:
                        cb(True)
            logger.info("✅ Action APPROVED: {} '{}'", action, target)
        
        def deny():
            """User denied the action."""
            with self._lock:
                if self._pending_approval:
                    self._pending_approval.approved = False
                    cb = self._pending_approval.callback
                    self._pending_approval = None
                    if cb:
                        cb(False)
            logger.info("⛔ Action DENIED: {} '{}'", action, target)
        
        # Fire the approval callback (GUI shows dialog here)
        try:
            self.on_approval_required(
                action=action,
                risk=risk.value,
                target=target,
                approve_fn=approve,
                deny_fn=deny,
            )
        except Exception as e:
            logger.error("Approval handler error: {}", e)
            deny()
        
        # Return False — actual result comes via callback
        return False

    def register_approval_handler(
        self,
        handler: Callable[[str, str, str, Callable, Callable], None],
    ):
        """
        Register a callback for displaying approval dialogs.
        
        The handler receives:
            action: str        — The action name
            risk: str          — "safe", "dangerous", or "critical"
            target: str        — What the action targets
            approve_fn: Callable — Call to approve
            deny_fn: Callable    — Call to deny
        
        Args:
            handler: The callback function
        """
        self.on_approval_required = handler
        logger.debug("Approval handler registered")

    def is_pending_approval(self) -> bool:
        """Check if there's a pending approval request."""
        with self._lock:
            return self._pending_approval is not None

    def cancel_pending(self):
        """Cancel a pending approval request (deny by default)."""
        with self._lock:
            if self._pending_approval:
                self._pending_approval.approved = False
                if self._pending_approval.callback:
                    self._pending_approval.callback(False)
                self._pending_approval = None
                logger.info("Pending approval cancelled (denied by default)")

    def get_approval_summary(self) -> dict:
        """Get summary of approval stats for debugging."""
        return {
            "safe_actions": sorted(self.SAFE_ACTIONS),
            "dangerous_actions": sorted(self.DANGEROUS_ACTIONS),
            "critical_actions": sorted(self.CRITICAL_ACTIONS),
            "pending": self.is_pending_approval(),
            "auto_approve_safe": self._auto_approve_safe,
        }