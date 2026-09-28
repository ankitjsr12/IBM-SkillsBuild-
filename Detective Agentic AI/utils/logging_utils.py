"""
utils/logging_utils.py

Standardized logging infrastructure for Detective Agentic AI.
Ensures sensitive tokens, passwords, and PII are redacted from log streams.
"""

import logging
import re
import sys
from typing import Optional

# Sensitive patterns to scrub from logs
_SCRUB_PATTERNS = [
    (re.compile(r"(password['\":\s=]+)(['\"][^'\"]+['\"]|\S+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(pin['\":\s=]+)(['\"][^'\"]+['\"]|\S+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(secret['\":\s=]+)(['\"][^'\"]+['\"]|\S+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(app_password['\":\s=]+)(['\"][^'\"]+['\"]|\S+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE), r"\1[REDACTED]"),
]


class RedactingFormatter(logging.Formatter):
    """Custom logging formatter that scrubs sensitive credentials from output."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for pattern, replacement in _SCRUB_PATTERNS:
            formatted = pattern.sub(replacement, formatted)
        return formatted


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger instance with redacting formatter."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = RedactingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger
