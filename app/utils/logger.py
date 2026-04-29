"""
Logging utility.
Configures a structured logger for the entire application.
"""
import logging
import sys


def setup_logger(level: str = "INFO") -> logging.Logger:
    """
    Configure and return the application logger.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Configured root logger instance.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger("swing_bot")
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = "swing_bot") -> logging.Logger:
    """Get a child logger with the given name."""
    return logging.getLogger(f"swing_bot.{name}")
