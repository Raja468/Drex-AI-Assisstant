# ============================================================
#  DREX - AI Desktop Assistant
#  utils/error_handler.py  —  Global Exception Management
#
#  PURPOSE:
#  Provides a consistent way to handle errors across the app.
#  Instead of crashing silently or showing ugly tracebacks,
#  every error goes through here to be:
#    1. Logged properly
#    2. Shown to the user in a friendly way
#    3. Reported back to the module that caused it
# ============================================================

from utils.logger import logger


# ─────────────────────────────────────────────────────────────
#  CUSTOM EXCEPTION CLASSES
#  These make it easy to tell WHERE an error came from
# ─────────────────────────────────────────────────────────────

class DrexError(Exception):
    """Base exception for all Drex-specific errors."""
    pass

class VoiceError(DrexError):
    """Raised when voice input/output fails."""
    pass

class AIError(DrexError):
    """Raised when an AI API call fails."""
    pass

class AutomationError(DrexError):
    """Raised when a system automation task fails."""
    pass

class MemoryError(DrexError):
    """Raised when database operations fail."""
    pass

class ConfigError(DrexError):
    """Raised when configuration is invalid or missing."""
    pass


# ─────────────────────────────────────────────────────────────
#  SAFE EXECUTOR  — Run risky code without crashing Drex
# ─────────────────────────────────────────────────────────────

def safe_execute(func, *args, fallback=None, context: str = "", **kwargs):
    """
    Runs a function safely, catching all exceptions.
    
    Args:
        func:     The function to call
        *args:    Arguments to pass to the function
        fallback: Value to return if the function fails (default: None)
        context:  Description of what we're trying to do (for logging)
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        The function's return value, or `fallback` if it raised an exception.
    
    Example:
        result = safe_execute(
            risky_function, arg1, arg2,
            fallback="default response",
            context="Opening Chrome browser"
        )
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        if context:
            logger.error(f"❌ Failed [{context}] → {error_msg}")
        else:
            logger.error(f"❌ Error in {func.__name__}() → {error_msg}")
        logger.debug(f"Full traceback:", exc_info=True)
        return fallback


# ─────────────────────────────────────────────────────────────
#  ERROR FORMATTER  — Turn exceptions into user-friendly text
# ─────────────────────────────────────────────────────────────

def format_error_for_user(error: Exception) -> str:
    """
    Converts a technical exception into a friendly message
    that Drex can speak or display to the user.
    
    Example:
        ConnectionError → "I'm having trouble connecting to the internet."
        FileNotFoundError → "I couldn't find that file."
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()
    
    # Network/API errors
    if any(word in error_msg for word in ["connection", "network", "timeout", "unreachable"]):
        return "I'm having trouble connecting to the internet. Please check your connection."
    
    if any(word in error_msg for word in ["api key", "unauthorized", "401", "403"]):
        return "There's an issue with my API key. Please check your settings."
    
    if any(word in error_msg for word in ["rate limit", "429", "quota"]):
        return "I've hit the API rate limit. Please wait a moment and try again."
    
    # File errors
    if error_type == "FileNotFoundError":
        return "I couldn't find that file or application."
    
    if error_type == "PermissionError":
        return "I don't have permission to do that. Try running as administrator."
    
    # Voice errors
    if isinstance(error, VoiceError):
        return "I had trouble with the microphone. Please try again."
    
    # AI errors
    if isinstance(error, AIError):
        return "My AI system is temporarily unavailable. I'll try a backup."
    
    # Automation errors
    if isinstance(error, AutomationError):
        return f"I couldn't complete that task. {str(error)}"
    
    # Generic fallback
    return "Something went wrong. Please try again."


# ─────────────────────────────────────────────────────────────
#  GLOBAL EXCEPTION HOOK  — Catch completely unhandled errors
# ─────────────────────────────────────────────────────────────

def install_global_handler():
    """
    Installs a global handler for any uncaught exception.
    Call this once in main.py.
    
    This is your last safety net — if ANY exception escapes
    all the other try/except blocks, this catches it and logs
    it cleanly instead of showing an ugly crash window.
    """
    import sys
    
    def handle_uncaught(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't log Ctrl+C as an error — it's intentional
            logger.info("👋 Drex closed by user (Ctrl+C)")
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger.critical(
            "💥 UNCAUGHT EXCEPTION — Drex crashed!",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    sys.excepthook = handle_uncaught
    logger.info("✅ Global exception handler installed")