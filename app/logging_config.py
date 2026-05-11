"""
Logging configuration for the Auto Trade System.
Standardizes logging across all modules using Python's built-in logging module.
"""
import logging
import sys
from app.config import settings


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with standardized formatting.

    Args:
        name: The name of the logger (usually __name__).

    Returns:
        A configured Logger instance.
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(console_handler)
        
        # Prevent log messages from being propagated to the root logger
        logger.propagate = False
        
    return logger
