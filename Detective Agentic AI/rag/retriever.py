"""
rag/retriever.py

Pure-Python TF/IDF cosine-similarity retriever — zero external dependencies.

IMPORTANT: This module performs similarity-based retrieval only.
All results are labelled as RETRIEVED EVIDENCE (similarity match against
historical case records). They are NOT legal proof. The calling layer must
present them with appropriate caveats.
"""

import logging
import os
import json
import math
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _tf(tokens: List[str]) -> Dict[str, float]:
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    total = len(tokens) or 1
    return {token: count / total for token, count in counts.items()}


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    mag_a = math.sqrt(sum(value * value for value in a.values()))
    mag_b = math.sqrt(sum(value * value for value in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# Minimum cosine similarity required to include a case in results.
SIMILARITY_THRESHOLD: float = 0.10

# The label attached to results so the UI can distinguish them.
RESULT_SOURCE_LABEL: str = "RETRIEVED EVIDENCE (similarity match)"

NO_MATCH_SENTINEL: str = "NO_MATCH"

# Indian Vernacular (Hinglish/Hindi) & Forensic Synonym Expansion
VERNACULAR_CRIME_MAP: Dict[str, List[str]] = {
    "zehar": ["poison", "cyanide", "toxicity", "chemical", "substance", "328"],
    "zahar": ["poison", "cyanide", "toxicity", "chemical", "328"],
    "dhatura": ["poison", "datura", "stupefying", "sedative", "328"],
    "taala": ["lock", "padlock", "breaker", "trespass", "burglary", "457"],
    "chabi": ["key", "master", "duplicate", "lock-picking"],
    "nakabjani": ["housebreaking", "burglary", "night", "trespass", "457"],
    "chori": ["theft", "stolen", "larceny", "379"],
    "loot": ["robbery", "dacoity", "extortion", "392"],
    "dakaiti": ["dacoity", "armed", "robbery", "gang", "395"],
    "supari": ["contract", "killing", "homicide", "mercenary", "conspiracy", "120b"],
    "shooter": ["firearm", "contract", "weapon", "arms"],
    "khun": ["murder", "homicide", "fatal", "302"],
    "khoon": ["murder", "homicide", "fatal", "302"],
    "qatl": ["murder", "homicide", "fatal", "302"],
    "laash": ["corpse", "deceased", "body", "victim", "post-mortem", "autopsy"],
    "tezaab": ["acid", "corrosive", "chemical", "burn", "326a"],
    "tezab": ["acid", "corrosive", "chemical", "326a"],
    "apaharan": ["kidnapping", "abduction", "hostage", "ransom", "364a"],
    "firauti": ["ransom", "extortion", "blackmail", "demand", "364a"],
    "hafta": ["extortion", "protection", "blackmail", "demand", "384"],
    "farar": ["absconding", "fugitive", "evading", "hideout"],
    "cctv": ["surveillance", "camera", "footage", "digital", "counter-measures"],
}


class CaseRetriever:

    def __init__(self, cases_dir: Optional[str] = None):
        if cases_dir is None:
            self.cases_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "cases")
            )
        elif os.path.isabs(cases_dir):
            self.cases_dir = cases_dir
        else:
            self.cases_dir = os.path.abspath(cases_dir)
        self._docs: List[Dict[str, Any]] = []
        self._index_cases()

    def reload(self) -> int:
        """Rebuild the in-memory index after case files change."""
        self._docs = []
        self._index_cases()
        return len(self._docs)

    @staticmethod
    def _case_text(case: Dict[str, Any]) -> str:
        """Flatten common case fields so uploaded evidence is searchable."""
        def flatten(value: Any) -> str:
            if isinstance(value, list):
                return ", ".join(flatten(item) for item in value)
            if isinstance(value, dict):
                return ", ".join(
                    f"{key}: {flatten(item)}"
                    for key, item in value.items()
                )
            return str(value or "")

        fields = (
            "title", "summary", "crime_type", "location", "status",
            "court_or_authority", "legal_citation", "ipc_sections",
            "modus_operandi", "personality_disorder", "common_traits",
            "evidence", "suspects", "case_notes", "investigation_notes",
        )
        return " ".join(
            f"{field.replace('_', ' ').title()}: {flatten(case.get(field, ''))}."
            for field in fields
            if case.get(field)
        )

    def _index_cases(self) -> None:
        if not os.path.isdir(self.cases_dir):
            logger.warning("Cases directory not found: %s", self.cases_dir)
            return

        indexed = 0
        for file in sorted(os.listdir(self.cases_dir)):
            if not file.lower().endswith(".json") or file.lower().startswith(("package", "config", "skills-lock", ".")):
                continue

            file_path = os.path.join(self.cases_dir, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if not content:
                    continue

                case = json.loads(content)
                if not isinstance(case, dict) or not case.get("case_id"):
                    continue

                doc_text = self._case_text(case)
                tokens = _tokenize(doc_text)
                if not tokens:
                    logger.warning("No tokens extracted from case file: %s", file)
                    continue

                case_id = str(case.get("case_id", file))
                title = str(case.get("title", "Unknown"))
                location = str(case.get("location", "Unknown"))
                crime_type = str(case.get("crime_type", "Unknown"))
                summary = str(case.get("summary", ""))

                # Modus operandi & common traits targeted text
                mo_val = case.get("modus_operandi", "")
                traits_val = case.get("common_traits", [])
                traits_str = " ".join(traits_val) if isinstance(traits_val, list) else str(traits_val)
                mo_composite = f"{crime_type} {mo_val} {traits_str}"
                mo_tokens = _tokenize(mo_composite)
                mo_tf = _tf(mo_tokens) if mo_tokens else {}

                # Evidence targeted text
                ev_val = case.get("evidence", [])
                ev_str = " ".join(ev_val) if isinstance(ev_val, list) else str(ev_val)
                ev_tokens = _tokenize(ev_str)
                ev_tf = _tf(ev_tokens) if ev_tokens else {}

                self._docs.append({
                    "case_id": case_id,
                    "text": doc_text,
                    "tf": _tf(tokens),
                    "mo_tf": mo_tf,
                    "ev_tf": ev_tf,
                    "tokens_set": set(tokens),
                    "summary": summary,
                    "metadata": {
                        "case_id": case_id,
                        "title": title,
                        "case_title": title,
                        "location": location,
                        "crime_type": crime_type,
                        "summary": summary,
                        "court_or_authority": str(case.get("court_or_authority", "Supreme Court / High Court")),
                        "legal_citation": str(case.get("legal_citation", "Public Criminal Case Record")),
                        "source": str(case.get("source", "Indian Kanoon / Official Judicial Judgment")),
                        "source_url": str(case.get("source_url", "")),
                        "ipc_sections": case.get("ipc_sections", []),
                        "judgment_date": str(case.get("judgment_date", "")),
                    },
                })
                indexed += 1

            except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
                logger.warning("Failed to index case file %s: %s", file, exc)
                continue

        logger.info("Indexed %d case(s) from %s", indexed, self.cases_dir)

    def search_similar_cases(
        self,
        suspect_query: str,
        top_k: int = 3,
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """Search indexed cases for similarity to the suspect query.

        Returns a list of matching case dicts, each labelled with
        ``result_type = RESULT_SOURCE_LABEL`` so the UI can distinguish
        retrieved evidence from AI inference. Returns an empty list when
        no case meets the threshold — callers should display
        "No sufficiently similar precedent found."
        """
        # Input validation
        query_clean = str(suspect_query or "").strip()
        if not query_clean:
            return []
        if len(query_clean) < 5:
            logger.debug("Query too short for meaningful similarity search.")
            return []
        if not self._docs:
            logger.warning("No cases indexed. Cannot perform similarity search.")
            return []

        try:
            top_k = max(1, int(top_k))
        except (TypeError, ValueError):
            top_k = 3

        try:
            threshold = max(0.0, min(1.0, float(threshold)))
        except (TypeError, ValueError):
            threshold = SIMILARITY_THRESHOLD

        # Normalize query text and apply Vernacular Legal Synonym Expansion
        raw_tokens = _tokenize(query_clean)
        if not raw_tokens:
            return []

        query_tokens = list(raw_tokens)
        for t in raw_tokens:
            if t in VERNACULAR_CRIME_MAP:
                query_tokens.extend(VERNACULAR_CRIME_MAP[t])

        query_tf = _tf(query_tokens)
        unique_q = set(query_tokens)
        scored = []

        for doc in self._docs:
            sim_full = _cosine(query_tf, doc["tf"])
            sim_mo = _cosine(query_tf, doc.get("mo_tf", {}))
            sim_ev = _cosine(query_tf, doc.get("ev_tf", {}))
            max_sec = max(sim_full, sim_mo, sim_ev)

            matched_tokens = unique_q & doc.get("tokens_set", set())
            coverage = len(matched_tokens) / len(unique_q) if unique_q else 0.0

            # Dynamic blend: section similarity + keyword coverage
            if coverage >= 0.20 and max_sec > 0.07:
                similarity = max(sim_full, 0.7 * max_sec + 0.3 * (coverage * max_sec * 1.5))
            else:
                similarity = max(sim_full, max_sec)

            if similarity <= 0:
                continue
            distance = max(0.0, 1.0 - similarity)
            scored.append((similarity, distance, doc))

        # Highest similarity = best match.
        scored.sort(key=lambda item: item[0], reverse=True)

        results: List[Dict[str, Any]] = []
        for similarity, distance, doc in scored[:top_k]:
            # Only include results above the similarity threshold
            if similarity < threshold:
                continue
            metadata = dict(doc["metadata"])
            results.append({
                "case_id": doc["case_id"],
                "metadata": metadata,
                "case_title": metadata.get("case_title", metadata.get("title", "Unknown Case")),
                "location": metadata.get("location", "Unknown"),
                "crime_type": metadata.get("crime_type", "Unknown"),
                "court_or_authority": metadata.get("court_or_authority", "Supreme Court / High Court"),
                "legal_citation": metadata.get("legal_citation", "Public Criminal Case Record"),
                "source": metadata.get("source", "Indian Kanoon / Official Judicial Judgment"),
                "source_url": metadata.get("source_url", ""),
                "ipc_sections": metadata.get("ipc_sections", []),
                "judgment_date": metadata.get("judgment_date", ""),
                # Provide summary (factual) and snippet (extracted) separately
                "summary": doc.get("summary", ""),
                "snippet": doc["text"][:300],
                "distance": round(distance, 4),
                "similarity": round(similarity, 4),
                # Label so the UI can clearly mark this as retrieved evidence
                "result_type": RESULT_SOURCE_LABEL,
            })

        return results
 
