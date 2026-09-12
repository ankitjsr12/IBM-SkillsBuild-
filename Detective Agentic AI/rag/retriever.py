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
# 0.20 means at least 20% token-overlap weighted similarity.
# Raising this reduces false positives at the cost of fewer matches.
SIMILARITY_THRESHOLD: float = 0.20

# The label attached to results so the UI can distinguish them.
RESULT_SOURCE_LABEL: str = "RETRIEVED EVIDENCE (similarity match)"

NO_MATCH_SENTINEL: str = "NO_MATCH"


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
            if not file.lower().endswith(".json"):
                continue

            file_path = os.path.join(self.cases_dir, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if not content:
                    continue

                case = json.loads(content)
                if not isinstance(case, dict):
                    logger.warning("Skipping non-dict case file: %s", file)
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

                self._docs.append({
                    "case_id": case_id,
                    "text": doc_text,
                    "tf": _tf(tokens),
                    "summary": summary,
                    "metadata": {
                        "case_id": case_id,
                        "title": title,
                        "case_title": title,
                        "location": location,
                        "crime_type": crime_type,
                        "summary": summary,
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

        # Normalize query text
        query_tokens = _tokenize(query_clean)
        if not query_tokens:
            return []

        query_tf = _tf(query_tokens)
        scored = []

        for doc in self._docs:
            similarity = _cosine(query_tf, doc["tf"])
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
                # Provide summary (factual) and snippet (extracted) separately
                "summary": doc.get("summary", ""),
                "snippet": doc["text"][:300],
                "distance": round(distance, 4),
                "similarity": round(similarity, 4),
                # Label so the UI can clearly mark this as retrieved evidence
                "result_type": RESULT_SOURCE_LABEL,
            })

        return results
 
