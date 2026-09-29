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



# Devanagari script transliteration mappings for Latin-1/Helvetica compatibility
_DEVA_VOWELS = {
    0x0904: "e", 0x0905: "a", 0x0906: "aa", 0x0907: "i", 0x0908: "ee", 0x0909: "u", 0x090A: "oo",
    0x090B: "ri", 0x090C: "li", 0x090D: "e", 0x090E: "e", 0x090F: "e", 0x0910: "ai",
    0x0911: "o", 0x0912: "o", 0x0913: "o", 0x0914: "au",
}
_DEVA_MATRAS = {
    0x093E: "aa", 0x093F: "i", 0x0940: "ee", 0x0941: "u", 0x0942: "oo", 0x0943: "ri",
    0x0944: "ree", 0x0945: "e", 0x0946: "e", 0x0947: "e", 0x0948: "ai", 0x0949: "o",
    0x094A: "o", 0x094B: "o", 0x094C: "au", 0x094D: "",  # Virama (halant)
}
_DEVA_CONSONANTS = {
    0x0915: "k", 0x0916: "kh", 0x0917: "g", 0x0918: "gh", 0x0919: "ng",
    0x091A: "ch", 0x091B: "chh", 0x091C: "j", 0x091D: "jh", 0x091E: "ny",
    0x091F: "t", 0x0920: "th", 0x0921: "d", 0x0922: "dh", 0x0923: "n",
    0x0924: "t", 0x0925: "th", 0x0926: "d", 0x0927: "dh", 0x0928: "n",
    0x0929: "nn", 0x092A: "p", 0x092B: "ph", 0x092C: "b", 0x092D: "bh", 0x092E: "m",
    0x092F: "y", 0x0930: "r", 0x0931: "rr", 0x0932: "l", 0x0933: "l", 0x0934: "ll",
    0x0935: "v", 0x0936: "sh", 0x0937: "sh", 0x0938: "s", 0x0939: "h",
    0x0958: "q", 0x0959: "kh", 0x095A: "g", 0x095B: "z", 0x095C: "r", 0x095D: "rh", 0x095E: "f", 0x095F: "y",
}
_DEVA_OTHERS = {
    0x0901: "n", 0x0902: "n", 0x0903: "h", 0x0964: ".", 0x0965: ".",
    0x0966: "0", 0x0967: "1", 0x0968: "2", 0x0969: "3", 0x096A: "4",
    0x096B: "5", 0x096C: "6", 0x096D: "7", 0x096E: "8", 0x096F: "9",
    0x0970: ".", 0x0971: ".",
}


def transliterate_devanagari(text: str) -> str:
    """Transliterate Devanagari script (Hindi/Sanskrit) phonetically to Roman characters."""
    if not text:
        return ""
    if not any(0x0900 <= ord(c) <= 0x097F for c in text):
        return text
    res = []
    i = 0
    n = len(text)
    while i < n:
        cp = ord(text[i])
        if cp in _DEVA_VOWELS:
            res.append(_DEVA_VOWELS[cp])
        elif cp in _DEVA_CONSONANTS:
            base = _DEVA_CONSONANTS[cp]
            if i + 1 < n and ord(text[i + 1]) == 0x094D:
                res.append(base)
                i += 1
            elif i + 1 < n and ord(text[i + 1]) in _DEVA_MATRAS:
                matra = _DEVA_MATRAS[ord(text[i + 1])]
                res.append(base + matra)
                i += 1
            else:
                res.append(base + "a")
        elif cp in _DEVA_OTHERS:
            res.append(_DEVA_OTHERS[cp])
        else:
            res.append(text[i])
        i += 1
    out = "".join(res)
    # Schwa deletion heuristic for word endings
    out = re.sub(r"([bcdfghjklmnpqrstvwxyz])a(?=[ ,;!?.:\-\n\r\t/()\[\]]|$)", r"\1", out)
    return out


def wrap_unbroken_tokens(text: str, max_token_len: int = 35) -> str:
    """
    Wrap words that exceed max_token_len without spaces (e.g., long hashes, URLs)
    to permanently prevent FPDF from throwing 'Not enough horizontal space' errors.
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
    2. Transliterate Devanagari (Hindi) if present.
    3. Strip Markdown markers.
    4. Replace known Unicode characters with ASCII equivalents.
    5. Wrap ultra-long uninterrupted tokens.
    6. Encode to Latin-1 with replacement ('?') to guarantee no unhandled exceptions.
    """
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default

    # 1. Transliterate Devanagari
    text = transliterate_devanagari(text)

    # 2. Strip markdown
    text = strip_markdown(text)

    # 3. Map Unicode replacements
    for uni, ascii_eq in UNICODE_TO_ASCII_MAP.items():
        if uni in text:
            text = text.replace(uni, ascii_eq)

    # 4. Wrap long tokens
    text = wrap_unbroken_tokens(text, max_token_len=35)

    # 5. Fallback replacement for any remaining non-latin1 characters
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


def extract_behavioral_patterns(text: str) -> list:
    """
    Extract structured behavioral patterns from user-provided investigative text.
    Strictly grounds every extracted pattern in verbatim user-provided text clauses.
    Never invents facts or infers criminal intent.
    """
    if not text or not str(text).strip():
        return []
    clean_text = str(text).strip()
    raw_clauses = re.split(r"[\n\r.;,]+", clean_text)
    clauses = [c.strip() for c in raw_clauses if len(c.strip()) > 3]

    rules = [
        ("Communication patterns", [r"phone", r"burner", r"sim", r"call", r"note", r"letter", r"message", r"communicat", r"contact", r"whatsapp", r"telegram", r"confession"]),
        ("Surveillance-related behaviour", [r"cctv", r"camera", r"surveillance", r"monitoring", r"casing", r"watch", r"reconnaissance", r"scout", r"stakeout"]),
        ("Time-of-day pattern", [r"night", r"midnight", r"nocturnal", r"after-hours", r"late", r"hours", r"dawn", r"dark", r"evening", r"morning", r"shift"]),
        ("Location changes & Movement pattern", [r"location", r"transit", r"railway", r"delhi", r"ghaziabad", r"station", r"bus", r"interstate", r"travel", r"movement", r"move", r"lodge", r"hotel", r"route"]),
        ("Target presence & approach pattern", [r"befriend", r"lure", r"vulnerable", r"migrant", r"jewelry", r"shop", r"warehouse", r"target", r"victim", r"premises", r"locked", r"pavement", r"door"]),
        ("Forensic counter-measures & concealment", [r"disabl", r"wire", r"alarm", r"plastic", r"sack", r"dump", r"conceal", r"cut", r"destroy", r"hide", r"mask", r"glove"]),
        ("Operational instrument / substance usage", [r"poison", r"cyanide", r"acid", r"rod", r"serpent", r"snake", r"strangl", r"decapitat", r"dismember", r"lock-pick", r"chemical", r"weapon", r"substance"]),
    ]

    extracted = []
    used_clauses = set()

    for pattern_name, regex_list in rules:
        for clause in clauses:
            if clause.lower() in used_clauses:
                continue
            if any(re.search(rx, clause, re.IGNORECASE) for rx in regex_list):
                extracted.append({
                    "pattern": pattern_name,
                    "evidence": clause,
                    "confidence": "Based on available textual evidence",
                })
                used_clauses.add(clause.lower())
                break

    for clause in clauses:
        if clause.lower() not in used_clauses and len(extracted) < 6:
            extracted.append({
                "pattern": "Other explicitly mentioned behaviour",
                "evidence": clause,
                "confidence": "Based on available textual evidence",
            })
            used_clauses.add(clause.lower())

    return extracted

