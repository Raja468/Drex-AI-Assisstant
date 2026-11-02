"""
DREX - Core Module
core/permission_guard.py — Automation Permission Layer

Provides a PermissionGuard that enforces user confirmation for
HIGH risk actions before they are executed. Risk levels:

    LOW:     Auto-approved (e.g., opening apps/websites, reading clipboard)
    MEDIUM:  Logged only (e.g., writing files, accessing browser)
    HIGH:    Requires Tkinter confirmation dialog (e.g., file deletion,
             system shutdown, executing shell commands)
"""

from typing import Optional
from enum import Enum
from loguru import logger


class RiskLevel(Enum):
    """Risk level for automated actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PermissionGuard:
    """
    Guard that validates and logs actions before they can be executed.

    Usage:
        guard = PermissionGuard()
        if guard.request_approval("delete_file", "Delete /tmp/test.txt", RiskLevel.HIGH):
            # execute the action
            pass
    """

    # Actions that are always auto-approved (LOW risk)
    LOW_RISK_ACTIONS = {
        "open_website",
        "open_app",
        "read_clipboard",
        "get_screen_size",
        "check_weather",
        "search_web",
        "get_time",
    }

    # Actions that are logged only (MEDIUM risk)
    MEDIUM_RISK_ACTIONS = {
        "write_file",
        "create_directory",
        "browser_navigate",
        "type_text",
        "press_key",
    }

    # Actions that require user confirmation (HIGH risk)
    HIGH_RISK_ACTIONS = {
        "delete_file",
        "delete_directory",
        "shutdown_system",
        "restart_system",
        "execute_command",
        "install_software",
        "modify_registry",
        "format_disk",
        "send_email",
        "make_http_request",
    }

    def __init__(self, auto_approve_low: bool = True):
        """
        Initialize the PermissionGuard.

        Args:
            auto_approve_low: If True, LOW risk actions are auto-approved.
        """
        self._auto_approve_low = auto_approve_low
        self._tk = None
        self._tk_initialized = False
        logger.debug("PermissionGuard initialized | auto_approve_low={}", auto_approve_low)

    def _resolve_risk_level(self, action: str) -> RiskLevel:
        """
        Determine the risk level for a given action.

        Args:
            action: The action name (e.g., 'delete_file', 'open_website').

        Returns:
            The RiskLevel for this action.
        """
        if action in self.HIGH_RISK_ACTIONS:
            return RiskLevel.HIGH
        if action in self.MEDIUM_RISK_ACTIONS:
            return RiskLevel.MEDIUM
        if action in self.LOW_RISK_ACTIONS:
            return RiskLevel.LOW
        # Unknown actions default to MEDIUM
        return RiskLevel.MEDIUM

    def request_approval(
        self,
        action: str,
        description: str,
        risk_level: Optional[RiskLevel] = None,
    ) -> bool:
        """
        Request approval for an action based on its risk level.

        Args:
            action: Action identifier (e.g., 'delete_file').
            description: Human-readable description of what will happen.
            risk_level: Override the risk level. If None, auto-detected
                        from the action name.

        Returns:
            True if the action is approved, False otherwise.
        """
        if risk_level is None:
            risk_level = self._resolve_risk_level(action)

        # Log the action regardless of risk level
        logger.info(
            "Action: {} | Risk: {} | Description: {}",
            action, risk_level.value, description,
        )

        if risk_level == RiskLevel.LOW and self._auto_approve_low:
            logger.debug("Auto-approved LOW risk action: {}", action)
            return True

        if risk_level == RiskLevel.MEDIUM:
            # MEDIUM: Log only, always approve
            logger.debug("Approved MEDIUM risk action: {}", action)
            return True

        if risk_level == RiskLevel.HIGH:
            # HIGH: Require user confirmation via dialog
            return self._show_confirmation_dialog(action, description)

        return True

    def _show_confirmation_dialog(self, action: str, description: str) -> bool:
        """
        Show a Tkinter confirmation dialog for HIGH risk actions.

        Args:
            action: Action identifier.
            description: Human-readable description.

        Returns:
            True if user confirmed, False if cancelled.
        """
        try:
            import tkinter as tk
            from tkinter import messagebox

            # Create a transient root window
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.attributes("-topmost", True)  # Bring to front

            result = messagebox.askyesno(
                title="⚠ DREX - Confirm Action",
                message=(
                    f"DREX wants to perform a HIGH risk action:\n\n"
                    f"Action: {action}\n"
                    f"Description: {description}\n\n"
                    f"Do you want to allow this?"
                ),
                icon="warning",
                parent=root,
            )

            root.destroy()

            if result:
                logger.info("User APPROVED high risk action: {}", action)
                return True
            else:
                logger.warning("User DENIED high risk action: {}", action)
                return False

        except Exception as e:
            logger.error(
                "PermissionGuard: Confirmation dialog failed: {}. "
                "Defaulting to DENY for safety.", e,
            )
            return False

    def add_custom_risk_action(self, action: str, risk_level: RiskLevel):
        """
        Register a custom action with a specific risk level.

        Args:
            action: Action identifier.
            risk_level: The risk level for this action.
        """
        if risk_level == RiskLevel.LOW:
            self.LOW_RISK_ACTIONS.add(action)
        elif risk_level == RiskLevel.MEDIUM:
            self.MEDIUM_RISK_ACTIONS.add(action)
        elif risk_level == RiskLevel.HIGH:
            self.HIGH_RISK_ACTIONS.add(action)
        logger.debug(
            "Registered custom action '{}' as {}",
            action, risk_level.value,
        )


# Singleton instance
_guard: Optional[PermissionGuard] = None


def get_permission_guard() -> PermissionGuard:
    """Get the singleton PermissionGuard instance."""
    global _guard
    if _guard is None:
        _guard = PermissionGuard()
    return _guard


def request_approval(
    action: str,
    description: str,
    risk_level: Optional[RiskLevel] = None,
) -> bool:
    """Convenience function to request approval via the singleton guard."""
    return get_permission_guard().request_approval(action, description, risk_level)