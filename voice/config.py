"""
voice/config.py — Voice Configuration (DEPRECATED)

This file is kept for backward compatibility only.
All configuration is now centralized in config.py (get_config()).

Import get_config() from config instead of using this file directly:
    from config import get_config
    cfg = get_config()
    voice_cfg = cfg.voice
"""
import warnings
from config import get_config

# Backward compatibility: re-export
def get_voice_config():
    """DEPRECATED: Use config.get_config().voice instead."""
    warnings.warn(
        "get_voice_config() is deprecated. Use config.get_config().voice instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_config().voice