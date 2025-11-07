"""Logging configuration."""
import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", format_string: Optional[str] = None) -> None:
    """
    Configure application logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format_string: Custom format string
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)

