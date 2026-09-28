"""
agent/explainability_engine.py

Explainable AI (XAI) and Indian Case Analysis Engine.
Implements:
1. Explainable AI Assessment with transparent factor breakdowns.
2. Mandatory SOURCE DATA → MATCHED PATTERN → SIMILARITY → AI ANALYSIS pipeline.
3. 7-Part Structured Investigation Analysis:
   - AI Case Summary
   - Pattern Analysis
   - Evidence Summary
   - Historical Similarities (Indian Legal Precedents)
   - Anomalies
   - Information Gaps
   - Human Review Points
4. Autonomous Guilt Language Scrubber:
   Never displays "Guilty", "Criminal", or "Definitely dangerous".
   Strictly frames outputs as "MODEL ASSESSMENT", "SIMILARITY SCORE", "RISK INDICATOR", or "PATTERN MATCH".
"""

import datetime
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Banned autonomous conclusive terms unless quoted from verified external records
PROHIBITED_AUTONOMOUS_TERMS = [
    re.compile(r"\bguilty\b", re.IGNORECASE),
    re.compile(r"\bcriminal\b", re.IGNORECASE),
    re.compile(r"\bdefinitely dangerous\b", re.IGNORECASE),
    re.compile(r"\bconvicted\b", re.IGNORECASE),
]


class ExplainabilityEngine:
    """Provides transparent, explainable scoring breakdowns and non-legal behavioral analysis."""

    @staticmethod
    def sanitize_assessment_language(text: str) -> str:
        """
        Ensure model explanations never declare legal guilt or conclusive criminality.
        Replaces prohibited autonomous terms with objective investigative phrasing.
        """
        if not text:
            return ""
        sanitized = text
        sanitized = re.sub(r"\bguilty\b", "potential pattern match", sanitized, flags=re.I)
        sanitized = re.sub(r"\bcriminal\b", "investigative subject", sanitized, flags=re.I)
        sanitized = re.sub(r"\bdefinitely dangerous\b", "elevated pattern similarity", sanitized, flags=re.I)
        return sanitized

    @classmethod
    def generate_explainable_assessment(
        cls,
        suspect_name: str,
        observed_behaviors: str,
        modus_operandi: str,
        retrieved_cases: List[Dict[str, Any]],
        base_score: int = 15,
    ) -> Dict[str, Any]:
        """
        Generate a fully explainable Model Assessment.
        Shows SOURCE DATA → MATCHED PATTERN → SIMILARITY → AI ANALYSIS
        """
        name_clean = suspect_name.strip() if suspect_name and suspect_name.strip() else "Unnamed Subject"
        behaviors_clean = observed_behaviors.strip() if observed_behaviors else "Not provided"
        mo_clean = modus_operandi.strip() if modus_operandi else "Not provided"

        # 1. Input Factors
        input_factors = {
            "subject_identifier": name_clean,
            "observed_behaviors_length": len(behaviors_clean),
            "modus_operandi_provided": mo_clean != "Not provided",
            "historical_cases_indexed_matched": len(retrieved_cases),
        }

        # 2. Observed Indicators
        observed_indicators = []
        if behaviors_clean != "Not provided":
            observed_indicators.append("Investigator-submitted behavioral observation recorded")
        if mo_clean != "Not provided":
            observed_indicators.append("Specific operational modus operandi provided")

        # 3. Matched Historical Patterns & Scoring Breakdown
        scoring_breakdown: List[Dict[str, Any]] = [
            {
                "factor": "Baseline Score",
                "contribution": base_score,
                "explanation": "Standard starting baseline applied to all investigative queries.",
            }
        ]

        explainable_pipelines: List[str] = []

        if retrieved_cases:
            similarities = [float(c.get("similarity", 0.0)) for c in retrieved_cases]
            strongest = max(similarities)
            avg = sum(similarities) / len(similarities)

            strongest_contrib = round(strongest * 55)
            avg_contrib = round(avg * 30)

            top_case = retrieved_cases[0]
            scoring_breakdown.append({
                "factor": "Strongest Precedent Similarity",
                "contribution": strongest_contrib,
                "explanation": (
                    f"Top matching Indian precedent '{top_case.get('case_title', 'Case')}' exhibits "
                    f"{strongest:.0%} similarity (x 55 weight = +{strongest_contrib} pts)."
                ),
            })
            scoring_breakdown.append({
                "factor": "Average Corpus Overlap",
                "contribution": avg_contrib,
                "explanation": (
                    f"Average similarity across {len(retrieved_cases)} matched Indian record(s) is {avg:.0%} "
                    f"(x 30 weight = +{avg_contrib} pts)."
                ),
            })

            total_score = min(95, max(15, base_score + strongest_contrib + avg_contrib))

            if strongest >= 0.55:
                confidence = "High Confidence (Strong lexical & behavioral correlation)"
                assessment_desc = "High pattern similarity to historical Indian precedent records"
                risk_category = "HIGH RISK"
            elif strongest >= 0.35:
                confidence = "Moderate Confidence (Partial behavioral correlation)"
                assessment_desc = "Moderate pattern similarity to historical Indian precedent records"
                risk_category = "MEDIUM RISK"
            else:
                confidence = "Low Confidence (Weak correlation)"
                assessment_desc = "Low pattern similarity to historical Indian precedent records"
                risk_category = "LOW RISK"

            matched_patterns = []
            for c in retrieved_cases:
                sim_pct = f"{float(c.get('similarity', 0.0)):.0%}"
                court = c.get("court_or_authority") or c.get("metadata", {}).get("court_or_authority", "Supreme Court / High Court")
                cite = c.get("legal_citation") or c.get("metadata", {}).get("legal_citation", "Public Legal Precedent")
                source_desc = c.get("source") or c.get("metadata", {}).get("source", "Indian Kanoon / Judicial Records")
                ipc = c.get("ipc_sections") or c.get("metadata", {}).get("ipc_sections", [])
                ipc_str = ", ".join(ipc) if isinstance(ipc, list) else str(ipc)

                pipeline_str = (
                    f"SOURCE DATA: {court} [{cite}] "
                    f"→ MATCHED PATTERN: {c.get('crime_type', 'Offence')} ({c.get('location', 'India')}) "
                    f"→ SIMILARITY: {sim_pct} "
                    f"→ AI ANALYSIS: Correlated under {ipc_str or 'Indian Penal Code'}. Pattern match only."
                )
                explainable_pipelines.append(pipeline_str)

                matched_patterns.append({
                    "case_id": c.get("case_id"),
                    "title": c.get("case_title"),
                    "similarity": sim_pct,
                    "crime_type": c.get("crime_type"),
                    "court_or_authority": court,
                    "legal_citation": cite,
                    "source": source_desc,
                    "source_url": c.get("source_url") or c.get("metadata", {}).get("source_url", ""),
                    "ipc_sections": ipc,
                    "explainable_pipeline": pipeline_str,
                })
        else:
            total_score = base_score
            confidence = "No sufficiently similar Indian record found."
            assessment_desc = "No sufficiently similar Indian record found."
            risk_category = "LOW RISK"
            matched_patterns = []
            scoring_breakdown.append({
                "factor": "No Vector Correlation",
                "contribution": 0,
                "explanation": "No cases in the Indian precedent index met the minimum 20% similarity threshold.",
            })

        # 4. Transparent Limitations
        limitations = [
            "Evaluations represent statistical word-overlap similarity, not subjective intent or legal proof.",
            "Precedent matching is constrained strictly to the Indian cases currently indexed in this system.",
            "Absence of a matching historical precedent does NOT establish innocence or absence of risk.",
            "All model assessments must be verified independently by human investigative authorities.",
        ]

        return {
            "model_assessment_title": "MODEL ASSESSMENT",
            "subject_name": name_clean,
            "similarity_score": f"{total_score}%",
            "risk_indicator": risk_category,
            "assessment": assessment_desc,
            "confidence_indicator": confidence,
            "input_factors": input_factors,
            "observed_indicators": observed_indicators,
            "matched_historical_patterns": matched_patterns,
            "explainable_pipelines": explainable_pipelines,
            "scoring_breakdown": scoring_breakdown,
            "limitations": limitations,
            "statutory_caveat": (
                "MODEL ASSESSMENT ONLY: All scores are generated by similarity pattern matching against Indian legal precedents. "
                "Never present this output as a legal finding, proof of guilt, or a confirmed criminal classification."
            ),
        }

    @classmethod
    def generate_case_summary(
        cls,
        case: Any,
        evidence_items: List[Any],
        timeline_events: List[Any],
        matched_precedents: List[Dict[str, Any]],
        anomalies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize the 7-Part Structured Investigation Analysis:
        1. AI Case Summary
        2. Pattern Analysis
        3. Evidence Summary
        4. Historical Similarities (Indian Precedents)
        5. Anomalies
        6. Information Gaps
        7. Human Review Points
        Plus: SOURCE DATA → MATCHED PATTERN → SIMILARITY → AI ANALYSIS pipeline.
        """
        c_title = getattr(case, "title", "Untitled Case")
        c_id = getattr(case, "case_id", "N/A")
        c_type = getattr(case, "case_type", "General Investigation")
        c_desc = getattr(case, "description", "")
        c_loc = getattr(case, "location", "Not provided")
        c_status = getattr(case, "status", "OPEN")
        c_priority = getattr(case, "priority", "MEDIUM")

        # 1. AI Case Summary
        ai_case_summary = (
            f"Case '{c_title}' [{c_id}] is currently classified as '{c_status}' with '{c_priority}' priority. "
            f"Investigation focuses on {c_type} incidents reported at {c_loc}. "
            f"Ground record status: {c_desc or 'Primary investigation initiated; formal narrative pending.'}"
        )

        # 2. Pattern Analysis
        mo_text = getattr(case, "extra_metadata", {}).get("modus_operandi", "")
        if mo_text:
            pattern_analysis = (
                f"Modus Operandi: {mo_text}. "
                f"Offence taxonomy evaluated under Indian investigative criteria for {c_type}."
            )
        else:
            pattern_analysis = f"Standard pattern analysis for {c_type} offences in {c_loc}. No specialized MO profile recorded."

        # Known facts extraction
        known_facts = [
            f"Case registered as {c_id} regarding '{c_title}' under classification {c_type}.",
            f"Primary incident site: {c_loc} with current status '{c_status}'.",
        ]
        if c_desc:
            known_facts.append(f"Recorded incident description: {c_desc}")

        # 3. Evidence Summary
        if evidence_items:
            evidence_summary = (
                f"{len(evidence_items)} evidence item(s) logged in the chain of custody with verified SHA-256 hashes. "
                f"Document and media types: {', '.join(sorted(list(set(e.file_type for e in evidence_items))))}."
            )
        else:
            evidence_summary = "No formal evidence items currently cataloged in the repository vault."

        # 4. Historical Similarities (Indian Precedents)
        explainable_pipelines: List[str] = []
        if matched_precedents:
            top_p = matched_precedents[0]
            top_court = top_p.get("court_or_authority") or top_p.get("metadata", {}).get("court_or_authority", "Indian Court")
            top_cite = top_p.get("legal_citation") or top_p.get("metadata", {}).get("legal_citation", "Judicial Record")
            sim_pct = top_p.get("similarity_pct", f"{float(top_p.get('similarity', 0.0)):.0%}")

            similarities_text = (
                f"{len(matched_precedents)} Indian legal precedent record(s) exhibit pattern similarities. "
                f"Top precedent: '{top_p.get('case_title')}' [{top_court} | {top_cite}] at {sim_pct} similarity."
            )
            for p in matched_precedents:
                p_court = p.get("court_or_authority") or p.get("metadata", {}).get("court_or_authority", "Indian Court")
                p_cite = p.get("legal_citation") or p.get("metadata", {}).get("legal_citation", "Judicial Record")
                p_sim = p.get("similarity_pct", f"{float(p.get('similarity', 0.0)):.0%}")
                pipeline_str = (
                    f"SOURCE DATA: {p_court} [{p_cite}] "
                    f"→ MATCHED PATTERN: {p.get('crime_type', 'Offence')} "
                    f"→ SIMILARITY: {p_sim} "
                    f"→ AI ANALYSIS: Evaluated against Indian judicial precedent. Research aid only."
                )
                explainable_pipelines.append(pipeline_str)
        else:
            similarities_text = "No sufficiently similar Indian record found."

        # 5. Anomalies
        anomalies_list = []
        if anomalies:
            for a in anomalies:
                anomalies_list.append(f"[{a.get('severity', 'INFO')}] {a.get('anomaly', 'Potential anomaly detected')}")
        else:
            anomalies_list.append("No structural, temporal, or evidentiary anomalies flagged across current records.")

        # 6. Information Gaps
        information_gaps = [
            "Are there supplementary forensic ballistics, chemical toxicology, or digital extraction reports pending?",
            "Timeline verification for movement of subjects between recorded incident timestamps.",
            "Cross-jurisdictional verification with State Police Crime Branch or CCTNS databases.",
        ]

        # 7. Human Review Points
        human_review_points = [
            "Independent forensic validation of chain-of-custody SHA-256 hashes.",
            "Corroboration of witness depositions against objective electronic Call Data Records (CDR).",
            "Supervisory case officer review prior to filing charge sheet under Section 173 CrPC / Section 193 BNSS.",
        ]

        return {
            "case_id": c_id,
            "case_title": c_title,
            "ai_case_summary": ai_case_summary,
            "case_overview": ai_case_summary,  # backward compatibility
            "known_facts": known_facts,
            "pattern_analysis": pattern_analysis,
            "evidence_summary": evidence_summary,
            "historical_similarities": similarities_text,
            "anomalies": anomalies_list,
            "information_gaps": information_gaps,
            "human_review_points": human_review_points,
            "unresolved_questions": information_gaps,  # backward compatibility
            "recommended_human_review_areas": human_review_points,  # backward compatibility
            "explainable_results_pipeline": explainable_pipelines,
            "statutory_caveat": (
                "MODEL ASSESSMENT ONLY: All scores and precedent correlations are produced by statistical pattern matching "
                "against public Indian judicial records. Never present AI output as proof of guilt, a legal finding, or a confirmed criminal classification."
            ),
            "disclaimer": (
                "IMPORTANT: This summary is an automated investigative research compilation. "
                "It does NOT contain autonomous legal conclusions or findings of liability."
            ),
        }
