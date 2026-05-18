"""utils/logger.py — logging setup for DREX"""
import os
import sys
from loguru import logger


def setup_logger():
    log_level = os.getenv("DREX_LOG_LEVEL", "INFO")
    log_file = os.getenv("DREX_LOG_FILE", "logs/drex.log")
    debug = os.getenv("DREX_DEBUG", "false").lower() == "true"

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger.remove()

    console_fmt = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level:<8}</level> | "
        "{message}"
    ) if not debug else (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level:<8}</level> | "
        "<cyan>{name}:{line}</cyan> | "
        "{message}"
    )

    logger.add(sys.stdout, level=log_level, format=console_fmt, colorize=True)

    logger.add(
        log_file,
        level="DEBUG" if debug else log_level,
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} | {message}",
        encoding="utf-8",
    )

    logger.info("Logger initialized | Level: {} | Debug: {}", log_level, debug)
    logger.info("   Log file: {}", log_file)
    return logger


__all__ = ["logger", "setup_logger"]