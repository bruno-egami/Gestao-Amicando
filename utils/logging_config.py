"""
Centralized Logging Configuration for CeramicAdmin OS
Provides consistent logging across all modules with file and console output.
"""
import logging
import os
from datetime import datetime

# --- Configuration ---
LOG_FOLDER = "logs"
LOG_FILE = os.path.join(LOG_FOLDER, "amicando.log")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_LOG_SIZE_MB = 5
BACKUP_COUNT = 3

# Ensure log folder exists
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger for the given module name.
    
    Usage:
        from utils.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
        logger.error("An error occurred", exc_info=True)
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # File Handler (with rotation)
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(file_handler)
    except Exception as e:
        # If file handler fails, continue with console only
        print(f"Warning: Could not create log file handler: {e}")
    
    # Console Handler (only warnings and above to avoid clutter)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(console_handler)
    
    return logger


def log_exception(logger: logging.Logger, context: str, exception: Exception):
    """
    Helper to log exceptions with context.
    
    Usage:
        try:
            do_something()
        except Exception as e:
            log_exception(logger, "Failed to do something", e)
    """
    logger.error(f"{context}: {type(exception).__name__} - {exception}", exc_info=True)


def log_database_operation(logger: logging.Logger, operation: str, table: str, record_id=None, success: bool = True):
    """
    Helper to log database operations consistently.
    
    Usage:
        log_database_operation(logger, "INSERT", "products", new_id)
        log_database_operation(logger, "DELETE", "sales", sale_id, success=False)
    """
    status = "SUCCESS" if success else "FAILED"
    id_info = f" (id={record_id})" if record_id else ""
    logger.info(f"DB {operation} on {table}{id_info} [{status}]")


# Initialize root logger for uncaught exceptions
_root_logger = get_logger("amicando")
_root_logger.info(f"Logging system initialized. Log file: {LOG_FILE}")
