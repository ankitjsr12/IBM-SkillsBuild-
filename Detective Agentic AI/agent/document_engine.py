"""
agent/document_engine.py

Document Intelligence & Text Extraction Engine.
Extracts searchable text, structural metadata, and key investigative entities
(emails, phones, IPs, amounts, dates) from uploaded evidence documents:
- PDF (pure-Python stream extractor with pypdf fallback)
- Plain text / Logs / Markdown (.txt, .log, .md)
- Structured data (.csv, .json)
- Images (PIL metadata extraction + optional OCR)
"""

import csv
import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Entity extraction patterns
PATTERNS = {
    "emails": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phones": re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
    "ips": re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
    "amounts": re.compile(r"(?:Rs\.?|INR|₹|\$|USD|EUR)\s*[\d,]+(?:\.\d+)?", re.IGNORECASE),
    "dates": re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})\b"),
}


class DocumentEngine:
    """Extracts text, metadata, and entities from investigative evidence files."""

    @classmethod
    def extract_text_from_bytes(
        cls,
        file_bytes: bytes,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract text and metadata from raw document bytes.
        Returns:
          - text: str
          - char_count: int
          - format: str
          - entities: Dict[str, List[str]]
          - metadata: Dict[str, Any]
        """
        ext = os.path.splitext(filename)[1].lower() if filename else ""
        text = ""
        meta: Dict[str, Any] = {"filename": filename, "size_bytes": len(file_bytes)}

        if ext in (".txt", ".log", ".md"):
            text = cls._extract_plain_text(file_bytes)
        elif ext == ".csv":
            text = cls._extract_csv(file_bytes)
        elif ext == ".json":
            text = cls._extract_json(file_bytes)
        elif ext == ".pdf":
            text, pdf_meta = cls._extract_pdf(file_bytes)
            meta.update(pdf_meta)
        elif ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"):
            text, img_meta = cls._extract_image(file_bytes)
            meta.update(img_meta)
        else:
            # Fallback attempt plain text
            try:
                text = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                text = f"[Binary data: {len(file_bytes)} bytes]"

        entities = cls.extract_entities(text)

        return {
            "text": text.strip(),
            "char_count": len(text.strip()),
            "format": ext.replace(".", "").upper() or "BINARY",
            "entities": entities,
            "metadata": meta,
        }

    @staticmethod
    def _extract_plain_text(data: bytes) -> str:
        for enc in ("utf-8", "latin-1", "ascii"):
            try:
                return data.decode(enc)
            except Exception:
                continue
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _extract_csv(data: bytes) -> str:
        try:
            content = data.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(content))
            lines = []
            for row in reader:
                if row:
                    lines.append(" | ".join(row))
            return "\n".join(lines)
        except Exception as e:
            return f"CSV Parse Error: {e}"

    @staticmethod
    def _extract_json(data: bytes) -> str:
        try:
            parsed = json.loads(data.decode("utf-8", errors="replace"))
            return json.dumps(parsed, indent=2)
        except Exception as e:
            return f"JSON Parse Error: {e}"

    @staticmethod
    def _extract_pdf(data: bytes) -> Tuple[str, Dict[str, Any]]:
        # Try third-party if available
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages_text), {"pages": len(reader.pages)}
        except ImportError:
            pass

        # Pure-python basic PDF stream text extractor fallback
        text_parts = []
        try:
            content = data.decode("latin-1", errors="ignore")
            # Look for text between parentheses in BT ... ET blocks
            bt_blocks = re.findall(r"BT(.*?)ET", content, re.DOTALL)
            for block in bt_blocks:
                strings = re.findall(r"\((.*?)\)\s*T[jJ]", block)
                for s in strings:
                    # Clean escaped octal and slashes
                    s = re.sub(r"\\[0-7]{3}", " ", s)
                    s = s.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
                    text_parts.append(s)
            extracted = " ".join(text_parts).strip()
            if not extracted:
                extracted = "[PDF Document: Digital PDF content archived. Text layer not encoded as plain ascii streams.]"
            return extracted, {"pages": content.count("/Type /Page")}
        except Exception as e:
            return f"[PDF parsing fallback error: {e}]", {}

    @staticmethod
    def _extract_image(data: bytes) -> Tuple[str, Dict[str, Any]]:
        meta: Dict[str, Any] = {}
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            meta["dimensions"] = f"{img.width}x{img.height}"
            meta["format"] = img.format
            meta["mode"] = img.mode

            # Try pytesseract if installed
            try:
                import pytesseract
                ocr_text = pytesseract.image_to_string(img)
                if ocr_text.strip():
                    return ocr_text.strip(), meta
            except Exception:
                pass

            label = (
                f"[IMAGE EVIDENCE: {img.format} image, {img.width}x{img.height} pixels, "
                f"mode {img.mode}. Visual verification required.]"
            )
            return label, meta
        except Exception as e:
            return f"[Image parse error: {e}]", meta

    @staticmethod
    def extract_entities(text: str) -> Dict[str, List[str]]:
        """Extract structured investigative entities using regular expressions."""
        if not text:
            return {k: [] for k in PATTERNS}

        results: Dict[str, List[str]] = {}
        for key, pattern in PATTERNS.items():
            matches = list(set(pattern.findall(text)))
            results[key] = sorted(matches)[:20]  # Cap at 20 per entity type
        return results
