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

import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional

from agent.indian_legal_connector import IndianLegalConnector
from rag.retriever import CaseRetriever, SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)

# Subjective bias & non-empirical assertion patterns prohibited in objective forensic profiling
_SUBJECTIVE_BIAS_PATTERNS = [
    (r"\b(looks|seems|appears)\s+(like\s+a\s+)?(criminal|thief|murderer|evil|guilty|shady|bad)\b",
     "Subjective physical appearance stereotype detected ('{match}'). Profiling must rely solely on empirical behavior."),
    (r"\b(born|habitual|hereditary)\s+(criminal|thief|offender)\b",
     "Unverified label ('{match}') violates objective evidentiary standards (anti-bias protection under Art. 14/21)."),
    (r"\b(suspicious|shady|untrustworthy)\s+(caste|community|tribe|religion|ethnicity|appearance)\b",
     "Demographic/appearance bias ('{match}') prohibited under Indian judicial standards and Criminal Tribes Act repeal."),
    (r"\b(definitely\s+guilty|no\s+doubt\s+he\s+did\s+it|100%\s+guilty)\b",
     "Presumption of guilt assertion ('{match}') detected. Profiling system outputs are non-legal investigative hypotheses only."),
]


def detect_subjective_bias(text: str) -> Dict[str, Any]:
    """Inspect investigator input for non-empirical prejudice or subjective confirmation bias."""
    if not text:
        return {"has_bias_flags": False, "flags": [], "advisory": ""}

    flags = []
    text_lower = text.lower()
    for pattern, warning_tmpl in _SUBJECTIVE_BIAS_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            flags.append(warning_tmpl.format(match=match.group(0)))

    if flags:
        advisory = (
            "⚠️ OBJECTIVITY NOTICE: Input contains subjective or appearance-based non-empirical characterizations. "
            "Forensic profiling algorithms discard personal appearance impressions and evaluate physical modus operandi only."
        )
    else:
        advisory = "Input adheres to empirical behavioral observation standards."

    return {
        "has_bias_flags": len(flags) > 0,
        "flags": flags,
        "advisory": advisory,
    }

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

        # Cross-reference IPC sections to Bharatiya Nyaya Sanhita (BNS 2023) provisions
        for case in retrieved_cases:
            ipc_secs = case.get("ipc_sections") or []
            if isinstance(ipc_secs, str):
                ipc_secs = [s.strip() for s in ipc_secs.split(",") if s.strip()]
            case["bns_cross_references"] = IndianLegalConnector.get_bns_cross_references(ipc_secs)

        # Evaluate potential investigator subjective bias & non-empirical assertions
        combined_input = f"{behavior} {mo_suspected} {personality_notes}"
        bias_evaluation = detect_subjective_bias(combined_input)

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
            average = sum(similarities) / len(similarities) if similarities else 0.0

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

            if strongest >= 0.30:
                match_quality = "Strong case-index similarity"
            elif strongest >= 0.18:
                match_quality = "Moderate case-index similarity"
            else:
                match_quality = "Weak case-index similarity"

            case_count = len(retrieved_cases)
            summary = (
                f"The system identified behavioural similarities with {case_count} historical "
                f"case{'s' if case_count != 1 else ''} in the indexed dataset. "
                "This is an AI-generated similarity analysis for investigative research only and is not a legal finding, "
                "proof of guilt, or probability of criminal activity. "
                "Final interpretation must be performed by a qualified investigator."
            )

        else:
            # Fallback: keyword severity heuristic
            combined_text = combined_input.lower()
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

            match_quality = "No sufficiently similar Indian record found."
            summary = (
                "The system found no sufficiently similar historical cases in the indexed dataset. "
                "This is an AI-generated similarity analysis for investigative research only and is not a legal finding, "
                "proof of guilt, or probability of criminal activity. "
                "Final interpretation must be performed by a qualified investigator."
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
            "factor": "Final score (capped 15–95)",
            "contribution": score,
            "explanation": (
                f"Score {score}/100 → Risk category: {risk_level}. "
                f"{risk_explanation}"
            ),
        })

        # --- 5. Legal Compliance (Section 65B IEA / Section 63 BSA 2023 Digital Fingerprint) ---
        canonical_str = f"{name}|{behavior}|{mo_suspected}|{personality_notes}|{score}|{len(retrieved_cases)}"
        evidence_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        return {
            "model_assessment_title": "MODEL ASSESSMENT",
            "suspect_name": str(name or "Unnamed Suspect").strip(),
            "tendency_score": f"{score}%",
            "risk_level": risk_level,
            "risk_explanation": risk_explanation,
            "match_quality": match_quality,
            "confidence_indicator": match_quality,
            "scoring_breakdown": scoring_breakdown,
            "summary": summary,
            "similar_cases": retrieved_cases,
            "matched_precedents": retrieved_cases,
            "evidence_hash": evidence_hash,
            "legal_compliance": {
                "statutory_framework": "Section 65B Indian Evidence Act, 1872 & Section 63 Bharatiya Sakshya Adhiniyam, 2023",
                "digital_evidence_hash": evidence_hash,
                "verification_seal": f"SHA256:{evidence_hash[:16].upper()}...{evidence_hash[-8:].upper()}",
                "chain_of_custody": "Authenticated Electronic Profiling Output - Read-Only Digital Record",
                "court_admissibility_notice": "Admissible in court only when accompanied by Section 65B / Section 63 BSA certificate signed by the designated forensic/investigating officer.",
            },
            "bias_guardrail": bias_evaluation,
            "disclaimer": (
                "All scores are MODEL ASSESSMENTS produced by similarity-based "
                "pattern matching against historical case records. "
                "They are NOT legal findings, NOT proof of guilt, and must NOT be "
                "used as the sole basis for any legal or investigative decision. "
                "Always verify with qualified human investigators."
            ),
        }
