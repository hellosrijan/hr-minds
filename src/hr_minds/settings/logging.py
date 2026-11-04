"""
Dual Logging Configuration for HR Minds API:
- Simple string-based logging for the Terminal (CLI).
- JSON-based logging for file output (logs/app.log) - active only when DEBUG is False.
"""

import logging
import os
import sys
from pythonjsonlogger import jsonlogger
from hr_minds.settings.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for file logs."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname.upper()
        log_record["logger"] = record.name
        if "time" not in log_record:
            log_record["timestamp"] = record.created


def setup_logging() -> None:
    """Configure root logger with CLI handler and conditional JSON file handler."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates
    if root_logger.handlers:
        root_logger.handlers.clear()

    # --- 1. Terminal (CLI) Handler: Simple String-based (Always active) ---
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    text_formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stdout_handler.setFormatter(text_formatter)
    root_logger.addHandler(stdout_handler)

    # --- 2. File Handler: JSON-based (Active only when DEBUG is False) ---
    if not settings.DEBUG:
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
        file_handler.setLevel(log_level)

        json_formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)

    # Adjust external libraries noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )
