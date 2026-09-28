"""
utils/text_utils.py

Text processing, sanitization, and Unicode transliteration utilities.
Provides fail-safe encoding for PDF generators and terminal outputs.
"""

import re
from typing import Any, Optional


# Mapping of common Unicode characters and symbols to Latin-1/ASCII equivalents
UNICODE_TO_ASCII_MAP = {
    "\u20b9": "Rs.",     # Indian Rupee symbol ₹
    "\u2018": "'",       # Left single quotation mark
    "\u2019": "'",       # Right single quotation mark
    "\u201c": '"',       # Left double quotation mark
    "\u201d": '"',       # Right double quotation mark
    "\u2013": "-",       # En dash
    "\u2014": "--",      # Em dash
    "\u2022": "*",       # Bullet point
    "\u2026": "...",     # Ellipsis
    "\u2192": "->",      # Rightwards arrow
    "\u2190": "<-",      # Leftwards arrow
    "\u2194": "<->",     # Left right arrow
    "\u2713": "[OK]",    # Checkmark
    "\u2714": "[OK]",    # Heavy checkmark
    "\u2717": "[X]",     # Cross mark
    "\u2718": "[X]",     # Heavy cross mark
    "\u26a0": "[!]",     # Warning sign
    "\u26a1": "[*]",     # High voltage
    "\u00a9": "(c)",     # Copyright
    "\u00ae": "(R)",     # Registered
    "\u2122": "(TM)",    # Trade mark
    "\u00b0": "deg",     # Degree symbol
    "\u00b1": "+/-",     # Plus-minus sign
    "\u00d7": "x",       # Multiplication sign
    "\u00f7": "/",       # Division sign
    "\ufe0f": "",        # Variation selector
}

# Regex to detect Markdown formatting markers
_MD_BOLD_ITALIC = re.compile(r"(\*\*\*|___)(.*?)\1")
_MD_BOLD = re.compile(r"(\*\*|__)(.*?)\1")
_MD_ITALIC = re.compile(r"(\*|_)(.*?)\1")
_MD_CODE = re.compile(r"`([^`]+)`")
_MD_LINKS = re.compile(r"\[([^\]]+)\]\([^\)]+\)")


def safe_str(val: Any, default: str = "Not provided") -> str:
    """Coerce value to a non-empty string or return the default."""
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def strip_markdown(text: str) -> str:
    """Strip markdown syntax (bold, italic, code blocks, links) leaving plain text."""
    if not text:
        return ""
    t = _MD_BOLD_ITALIC.sub(r"\2", text)
    t = _MD_BOLD.sub(r"\2", t)
    t = _MD_ITALIC.sub(r"\2", t)
    t = _MD_CODE.sub(r"\1", t)
    t = _MD_LINKS.sub(r"\1", t)
    return t


def wrap_unbroken_tokens(text: str, max_token_len: int = 70) -> str:
    """
    Wrap words that exceed max_token_len without spaces (e.g., long hashes, URLs)
    to prevent FPDF from throwing 'Not enough horizontal space' errors.
    """
    if not text:
        return ""
    words = text.split(" ")
    wrapped_words = []
    for word in words:
        if len(word) > max_token_len:
            chunks = [word[i:i + max_token_len] for i in range(0, len(word), max_token_len)]
            wrapped_words.append(" ".join(chunks))
        else:
            wrapped_words.append(word)
    return " ".join(wrapped_words)


def sanitize_for_pdf(value: Any, default: str = "Not provided") -> str:
    """
    Sanitize text for standard fpdf2 Latin-1 core fonts (Helvetica, Times, Courier).
    
    Processing steps:
    1. Coerce to string and apply safe default if empty.
    2. Strip Markdown markers.
    3. Replace known Unicode characters with ASCII equivalents.
    4. Wrap ultra-long uninterrupted tokens.
    5. Encode to Latin-1 with replacement ('?') to guarantee no unhandled exceptions.
    """
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default

    # 1. Strip markdown
    text = strip_markdown(text)

    # 2. Map Unicode replacements
    for uni, ascii_eq in UNICODE_TO_ASCII_MAP.items():
        if uni in text:
            text = text.replace(uni, ascii_eq)

    # 3. Wrap long tokens
    text = wrap_unbroken_tokens(text, max_token_len=75)

    # 4. Fallback replacement for any remaining non-latin1 characters
    try:
        encoded = text.encode("latin-1", errors="replace")
        return encoded.decode("latin-1")
    except Exception:
        # Ultimate fallback: keep printable ASCII characters only
        return "".join(c if 32 <= ord(c) < 127 or c in "\n\r\t" else "?" for c in text)


def truncate_text(text: str, max_chars: int = 250, suffix: str = "...") -> str:
    """Safely truncate text at character limit without breaking words where possible."""
    if not text or len(text) <= max_chars:
        return text or ""
    truncated = text[:max_chars - len(suffix)]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated + suffix
