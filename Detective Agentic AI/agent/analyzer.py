"""
agent/analyzer.py

Suspect profiling engine.

IMPORTANT — LIMITATIONS AND DISCLAIMERS:
  All scores produced by this module are MODEL ASSESSMENTS based on
  pattern similarity against historical case records. They are NOT
  legal findings, NOT proof of guilt, and NOT predictions of future
  behaviour. Results must be reviewed by a qualified investigator.
  Never present these scores as facts in legal proceedings.
"""

import logging
from typing import Any, Dict, List

from rag.retriever import CaseRetriever, SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)

# Severe behavioural keywords used when no vector match is found.
_SEVERE_KEYWORDS: List[str] = [
    "murder", "kill", "weapon", "assault", "robbery",
    "theft", "break-in", "crime", "stolen", "force",
    "threat", "arson", "fraud", "extortion", "trafficking",
]


class DetectiveAgent:

    def __init__(self):
        # Create the RAG retriever when the agent is initialised.
        self.retriever = CaseRetriever()
        logger.info(
            "DetectiveAgent initialised. Cases indexed: %d",
            len(self.retriever._docs),
        )

    def reload_cases(self) -> int:
        """Refresh indexed cases after a new JSON file is uploaded."""
        count = self.retriever.reload()
        logger.info("Case index reloaded. Cases indexed: %d", count)
        return count

    def evaluate_suspect(
        self,
        name: str,
        behavior: str,
        mo_suspected: str,
        personality_notes: str,
    ) -> Dict[str, Any]:
        """Evaluate a suspect against the historical case vector index.

        Returns a structured result dict that includes:
          - tendency_score       : int 0-100 (model assessment, NOT a legal finding)
          - risk_level           : "LOW RISK" / "MEDIUM RISK" / "HIGH RISK"
          - match_quality        : human-readable description of match strength
          - scoring_breakdown    : list of dicts explaining each score component
          - similar_cases        : retrieved historical cases above the threshold
          - summary              : brief plain-text summary
          - disclaimer           : mandatory disclaimer text for display
        """
        # --- 1. Build query ---
        query_parts: List[str] = []
        for value in (behavior, mo_suspected, personality_notes):
            value_text = str(value or "").strip()
            if value_text and value_text not in query_parts:
                query_parts.append(value_text)
        query_str = "; ".join(query_parts)

        # --- 2. RAG Retrieval ---
        try:
            retrieved_cases = self.retriever.search_similar_cases(
                query_str,
                top_k=3,
                threshold=SIMILARITY_THRESHOLD,
            )
        except Exception as exc:
            logger.error("RAG retrieval failed: %s", exc)
            retrieved_cases = []

        # --- 3. Scoring with per-factor breakdown ---
        scoring_breakdown: List[Dict[str, Any]] = []
        base_score = 15
        scoring_breakdown.append({
            "factor": "Base score",
            "contribution": base_score,
            "explanation": "Minimum baseline assigned to every evaluation.",
        })

        if retrieved_cases:
            similarities = [float(c.get("similarity", 0.0)) for c in retrieved_cases]
            strongest = max(similarities)
            average = sum(similarities) / len(similarities)

            strongest_contrib = round(strongest * 60)
            average_contrib = round(average * 25)

            scoring_breakdown.append({
                "factor": "Strongest case similarity",
                "contribution": strongest_contrib,
                "explanation": (
                    f"Best matching historical case has {strongest:.0%} similarity "
                    f"(× 60 weight = {strongest_contrib} points). "
                    "SOURCE: similarity-based retrieval."
                ),
            })
            scoring_breakdown.append({
                "factor": "Average case similarity",
                "contribution": average_contrib,
                "explanation": (
                    f"Average similarity across {len(similarities)} matched case(s) "
                    f"is {average:.0%} (× 25 weight = {average_contrib} points). "
                    "SOURCE: similarity-based retrieval."
                ),
            })

            raw_score = base_score + strongest_contrib + average_contrib
            score = round(min(95, max(15, raw_score)))

            if strongest >= 0.55:
                match_quality = "Strong case-index similarity"
            elif strongest >= 0.35:
                match_quality = "Moderate case-index similarity"
            else:
                match_quality = "Weak case-index similarity"

            summary = (
                f"Model assessment: behaviour pattern aligns with "
                f"{len(retrieved_cases)} historical case(s) in the index. "
                "This is a similarity-based result, not a legal finding."
            )

        else:
            # Fallback: keyword severity heuristic
            combined_text = f"{behavior} {mo_suspected} {personality_notes}".lower()
            matched_keywords = [kw for kw in _SEVERE_KEYWORDS if kw in combined_text]
            kw_count = len(matched_keywords)

            if kw_count > 0:
                kw_contrib = min(80, kw_count * 15)
                scoring_breakdown.append({
                    "factor": "Keyword severity heuristic",
                    "contribution": kw_contrib,
                    "explanation": (
                        f"No vector match found. {kw_count} severity keyword(s) detected "
                        f"({', '.join(matched_keywords)}) × 15 points each = {kw_contrib} pts. "
                        "SOURCE: keyword heuristic (low confidence)."
                    ),
                })
                score = round(min(95, max(25, base_score + kw_contrib)))
            else:
                scoring_breakdown.append({
                    "factor": "No indicators detected",
                    "contribution": 0,
                    "explanation": (
                        "No vector case match and no severity keywords detected. "
                        "Score remains at baseline."
                    ),
                })
                score = 15

            match_quality = "No reliable case-index match"
            summary = (
                "No direct vector match found. Risk evaluated from behavioural "
                "keyword indicators only. Confidence is low — manual review recommended."
            )

        # --- 4. Risk category ---
        if score >= 70:
            risk_level = "HIGH RISK"
            risk_explanation = (
                "Model assessment indicates high similarity to high-severity historical patterns. "
                "This is a risk indicator only."
            )
        elif score >= 40:
            risk_level = "MEDIUM RISK"
            risk_explanation = (
                "Model assessment indicates moderate similarity to historical patterns. "
                "This is a risk indicator only."
            )
        else:
            risk_level = "LOW RISK"
            risk_explanation = (
                "Model assessment indicates low similarity to historical high-severity patterns. "
                "Absence of a match does NOT confirm innocence."
            )

        scoring_breakdown.append({
            "factor": "Final score",
            "contribution": score,
            "explanation": (
                f"Score {score}/100 → Risk category: {risk_level}. "
                f"{risk_explanation}"
            ),
        })

        return {
            "suspect_name": str(name or "Unnamed Suspect").strip(),
            "tendency_score": f"{score}%",
            "risk_level": risk_level,
            "risk_explanation": risk_explanation,
            "match_quality": match_quality,
            "scoring_breakdown": scoring_breakdown,
            "summary": summary,
            "similar_cases": retrieved_cases,
            "disclaimer": (
                "All scores are MODEL ASSESSMENTS produced by similarity-based "
                "pattern matching against historical case records. "
                "They are NOT legal findings, NOT proof of guilt, and must NOT be "
                "used as the sole basis for any legal or investigative decision. "
                "Always verify with qualified human investigators."
            ),
        }
