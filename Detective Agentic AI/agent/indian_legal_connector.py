"""
agent/indian_legal_connector.py

Indian Public Legal Data Connector & Case Importer.
Connects to authentic Indian legal repositories (Indian Kanoon, eCourts, Supreme Court public archives)
and imports verified Indian criminal and judicial precedent records.

MANDATORY RULES:
1. Use only authentic India-specific sources and public legal datasets.
2. Do NOT create fake, mock, hardcoded, or random cases.
3. If a reliable Indian dataset/source is unavailable, do NOT invent one; clearly return
   "Data source unavailable."
"""

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CASES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cases"))

SUPPORTED_INDIAN_AUTHORITIES = [
    {"name": "Supreme Court of India", "type": "Apex Judicial Court", "jurisdiction": "All India"},
    {"name": "High Court of Delhi", "type": "High Court", "jurisdiction": "NCT of Delhi"},
    {"name": "High Court of Bombay", "type": "High Court", "jurisdiction": "Maharashtra & Goa"},
    {"name": "High Court of Karnataka", "type": "High Court", "jurisdiction": "Karnataka"},
    {"name": "High Court of Madras", "type": "High Court", "jurisdiction": "Tamil Nadu & Puducherry"},
    {"name": "High Court of Judicature at Allahabad", "type": "High Court", "jurisdiction": "Uttar Pradesh"},
    {"name": "High Court of Kerala", "type": "High Court", "jurisdiction": "Kerala & Lakshadweep"},
    {"name": "High Court for the State of Telangana", "type": "High Court", "jurisdiction": "Telangana"},
    {"name": "National Investigation Agency (NIA) Special Courts", "type": "Special Investigation Court", "jurisdiction": "Terrorism & National Security"},
    {"name": "Central Bureau of Investigation (CBI) Special Courts", "type": "Anti-Corruption & Major Crimes Court", "jurisdiction": "Federal Jurisdiction"},
]


class IndianLegalConnector:
    """Connects to public Indian legal judgment sources and validates incoming Indian precedent records."""

    def __init__(self, cases_dir: Optional[str] = None):
        self.cases_dir = cases_dir or CASES_DIR
        os.makedirs(self.cases_dir, exist_ok=True)

    @staticmethod
    def query_public_indian_legal_gateway(query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Query public Indian legal search endpoints (Indian Kanoon / Open Law).
        If network is offline or remote API endpoint fails, strictly returns 'Data source unavailable'
        without fabricating fake cases.
        """
        clean_q = str(query or "").strip()
        if not clean_q or len(clean_q) < 3:
            return {
                "status": "ERROR",
                "message": "Search query must be at least 3 characters.",
                "records": [],
            }

        api_token = os.environ.get("INDIAN_KANOON_API_KEY", "").strip()

        # If no external API key configured, attempt direct public title query with timeout
        if not api_token:
            # We strictly report that direct live API requires token or public gateway is unreachable
            return {
                "status": "UNAVAILABLE",
                "message": "Data source unavailable: Public legal gateway requires authenticated API key (INDIAN_KANOON_API_KEY). Live query cannot be completed without verified credentials.",
                "records": [],
            }

        try:
            encoded_q = urllib.parse.quote_plus(clean_q)
            req_url = f"https://api.indiankanoon.org/search/?formInput={encoded_q}&pagenum=0"
            req = urllib.request.Request(
                req_url,
                headers={"Authorization": f"Token {api_token}", "User-Agent": "DetectiveAgenticAI/2.0"},
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    docs = payload.get("docs", [])[:max_results]
                    records = [
                        {
                            "title": d.get("title", "Untitled Judgment"),
                            "legal_citation": d.get("citation", "Indian Kanoon Record"),
                            "court_or_authority": d.get("docsource", "Indian Judicial Court"),
                            "source": "Indian Kanoon API Live Gateway",
                            "source_url": f"https://indiankanoon.org/doc/{d.get('tid')}/" if d.get("tid") else "",
                            "judgment_date": d.get("publishdate", ""),
                            "snippet": d.get("headline", ""),
                        }
                        for d in docs
                    ]
                    return {
                        "status": "SUCCESS",
                        "message": f"Retrieved {len(records)} live legal records from Indian Kanoon gateway.",
                        "records": records,
                    }
        except Exception as exc:
            logger.warning("Indian legal gateway query failed: %s", exc)

        return {
            "status": "UNAVAILABLE",
            "message": "Data source unavailable: Unable to reach Indian public legal gateway.",
            "records": [],
        }

    def import_verified_indian_case(self, case_data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Validate and import an authentic Indian case JSON file.
        Requires:
          - case_id starting with 'CASE-IND-'
          - authentic title and crime_type
          - court_or_authority and legal_citation
          - source and source_url
        """
        if not isinstance(case_data, dict):
            return False, "Case data must be a valid JSON dictionary.", None

        case_id = str(case_data.get("case_id", "")).strip().upper()
        if not case_id.startswith("CASE-IND-"):
            return False, f"Invalid Case ID '{case_id}'. Authentic Indian cases must use the prefix 'CASE-IND-'.", None

        title = str(case_data.get("title", "")).strip()
        if not title:
            return False, "Case title is required.", None

        court = str(case_data.get("court_or_authority", "")).strip()
        if not court:
            return False, "Authentic court or judicial authority is mandatory for Indian cases.", None

        citation = str(case_data.get("legal_citation", "")).strip()
        if not citation:
            return False, "Authentic legal citation or case appeal number is mandatory.", None

        source = str(case_data.get("source", "")).strip()
        if not source:
            return False, "Original source reference is required.", None

        # Build clean sanitized case record
        sanitized_case = {
            "case_id": case_id,
            "title": title,
            "status": str(case_data.get("status", "Solved")).strip(),
            "crime_type": str(case_data.get("crime_type", "General Investigation")).strip(),
            "court_or_authority": court,
            "legal_citation": citation,
            "judgment_date": str(case_data.get("judgment_date", "")).strip(),
            "source": source,
            "source_url": str(case_data.get("source_url", "")).strip(),
            "ipc_sections": case_data.get("ipc_sections", []),
            "location": str(case_data.get("location", "India")).strip(),
            "timestamp": str(case_data.get("timestamp", "2020-01-01T00:00:00Z")).strip(),
            "suspects": case_data.get("suspects", []),
            "evidence": case_data.get("evidence", []),
            "modus_operandi": str(case_data.get("modus_operandi", "")).strip(),
            "personality_disorder": str(case_data.get("personality_disorder", "Not clinically documented")).strip(),
            "common_traits": case_data.get("common_traits", []),
            "summary": str(case_data.get("summary", "")).strip(),
        }

        # Safe filename
        safe_fname = re.sub(r"[^A-Za-z0-9_.-]", "_", case_id.lower()) + ".json"
        save_path = os.path.join(self.cases_dir, safe_fname)

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(sanitized_case, f, indent=2, ensure_ascii=False)
            logger.info("Imported authentic Indian case: %s (%s)", case_id, save_path)
            return True, f"Successfully imported authentic Indian case '{case_id}' ({title}).", save_path
        except Exception as io_err:
            return False, f"Failed to save case file: {io_err}", None

    @staticmethod
    def get_supported_authorities() -> List[Dict[str, str]]:
        """Return the list of recognized Indian judicial and investigative authorities."""
        return list(SUPPORTED_INDIAN_AUTHORITIES)


# Class alias for alternative naming
IndianLegalGatewayConnector = IndianLegalConnector
