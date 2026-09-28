"""
agent/anomaly_engine.py

Investigative Anomaly Detection Engine.
Implements Part 13 (Anomaly Detection).

Detects:
  - Unusual timestamps & impossible temporal orders
  - Repeated events & duplicate timeline descriptions
  - Duplicate evidence & hash collisions
  - Unexpected event frequency / burst patterns
  - Data inconsistencies (e.g., activity logged after case closure)
  - Unusual operational sequences

MANDATORY RULE:
Do NOT claim that an anomaly proves wrongdoing.
Every flag must be presented as: "Potential anomaly detected".
"""

import collections
import datetime
import logging
from typing import Any, Dict, List, Optional

from database.repository import CaseRepository, EvidenceRepository, TimelineRepository

logger = logging.getLogger(__name__)


class AnomalyEngine:
    """Detects temporal, frequency, evidentiary, and sequence anomalies across stored records."""

    def __init__(
        self,
        case_repo: Optional[CaseRepository] = None,
        evidence_repo: Optional[EvidenceRepository] = None,
        timeline_repo: Optional[TimelineRepository] = None,
    ):
        self.case_repo = case_repo or CaseRepository()
        self.evidence_repo = evidence_repo or EvidenceRepository()
        self.timeline_repo = timeline_repo or TimelineRepository()

    def scan_case_anomalies(self, case_id: str) -> List[Dict[str, Any]]:
        """
        Analyze a specific case for anomalies across timeline events,
        evidence items, and case status attributes.
        """
        anomalies: List[Dict[str, Any]] = []
        case = self.case_repo.get_case(case_id.strip())
        if not case:
            return anomalies

        timeline_events = self.timeline_repo.list_events_for_case(case_id.strip())
        evidence_items = self.evidence_repo.list_evidence(case_id=case_id.strip())

        # ---------------------------------------------------------------------
        # 1. Unusual Timestamps & Sequence Order
        # ---------------------------------------------------------------------
        # Check if events precede case date_opened
        case_opened_str = case.date_opened
        for ev in timeline_events:
            if ev.timestamp < case_opened_str and ev.event_type != "INCIDENT":
                anomalies.append({
                    "anomaly": f"Potential anomaly detected: Event precedes Case Open Date",
                    "target": f"Event [{ev.event_id}] ({ev.event_type})",
                    "reason": f"Event timestamp '{ev.timestamp}' is recorded prior to case opened date '{case_opened_str}'.",
                    "severity": "MEDIUM",
                })

        # Check sequence: Investigator review before Incident
        incident_seen = False
        for ev in timeline_events:
            if ev.event_type == "INCIDENT":
                incident_seen = True
            elif ev.event_type == "INVESTIGATOR_REVIEW" and not incident_seen:
                anomalies.append({
                    "anomaly": "Potential anomaly detected: Premature Investigator Review",
                    "target": f"Event [{ev.event_id}]",
                    "reason": "Investigator review logged before initial incident notification event.",
                    "severity": "LOW",
                })

        # ---------------------------------------------------------------------
        # 2. Repeated Events & Duplicate Descriptions
        # ---------------------------------------------------------------------
        seen_event_descs: Dict[str, str] = {}
        for ev in timeline_events:
            clean_d = ev.description.lower().strip()
            if len(clean_d) > 10:
                if clean_d in seen_event_descs:
                    anomalies.append({
                        "anomaly": "Potential anomaly detected: Repeated Timeline Event",
                        "target": f"Event [{ev.event_id}] & [{seen_event_descs[clean_d]}]",
                        "reason": f"Identical event description logged more than once in the case timeline.",
                        "severity": "LOW",
                    })
                else:
                    seen_event_descs[clean_d] = ev.event_id

        # ---------------------------------------------------------------------
        # 3. Duplicate Evidence / Repeated Filenames
        # ---------------------------------------------------------------------
        seen_hashes: Dict[str, str] = {}
        seen_names: Dict[str, str] = {}
        for ev_item in evidence_items:
            h = ev_item.sha256_hash
            if h in seen_hashes:
                anomalies.append({
                    "anomaly": "Potential anomaly detected: Exact Cryptographic Evidence Collision",
                    "target": f"Evidence [{ev_item.evidence_id}] & [{seen_hashes[h]}]",
                    "reason": f"Two evidence entries share the identical SHA-256 hash ({h[:16]}...). Possible duplicate seizure.",
                    "severity": "HIGH",
                })
            else:
                seen_hashes[h] = ev_item.evidence_id

            fname = ev_item.metadata.get("original_filename", "").lower()
            if fname and fname in seen_names:
                anomalies.append({
                    "anomaly": "Potential anomaly detected: Duplicate Evidence Filename",
                    "target": f"Evidence [{ev_item.evidence_id}]",
                    "reason": f"Filename '{fname}' is attached multiple times under this case.",
                    "severity": "LOW",
                })
            elif fname:
                seen_names[fname] = ev_item.evidence_id

        # ---------------------------------------------------------------------
        # 4. Unexpected Frequency / Event Bursts
        # ---------------------------------------------------------------------
        parsed_times = []
        for ev in timeline_events:
            try:
                # Try parsing ISO or space separated format
                fmt = "%Y-%m-%d %H:%M:%S" if " " in ev.timestamp else "%Y-%m-%d"
                dt = datetime.datetime.strptime(ev.timestamp[:19], fmt)
                parsed_times.append((dt, ev.event_id))
            except Exception:
                pass

        if len(parsed_times) >= 4:
            for i in range(len(parsed_times) - 3):
                delta = (parsed_times[i + 3][0] - parsed_times[i][0]).total_seconds()
                if delta <= 120 and delta >= 0:
                    anomalies.append({
                        "anomaly": "Potential anomaly detected: Unusually High Event Frequency",
                        "target": f"Events [{parsed_times[i][1]}] to [{parsed_times[i + 3][1]}]",
                        "reason": f"4 timeline events recorded within {int(delta)} seconds. Rapid clustering detected.",
                        "severity": "MEDIUM",
                    })
                    break

        # ---------------------------------------------------------------------
        # 5. Data Inconsistencies: Closed/Archived status with post-closure activity
        # ---------------------------------------------------------------------
        if case.status in ("CLOSED", "ARCHIVED"):
            for ev in timeline_events:
                if ev.created_at > case.updated_at:
                    anomalies.append({
                        "anomaly": f"Potential anomaly detected: Activity Logged Post-Closure",
                        "target": f"Case [{case.case_id}] - Event [{ev.event_id}]",
                        "reason": f"Event logged while case status is '{case.status}'.",
                        "severity": "HIGH",
                    })
                    break

        return anomalies

    def scan_global_anomalies(self) -> List[Dict[str, Any]]:
        """Scan across all cases in the repository for system-wide anomalies."""
        all_cases = self.case_repo.list_cases()
        all_anomalies = []
        for c in all_cases:
            case_anoms = self.scan_case_anomalies(c.case_id)
            for a in case_anoms:
                a["case_id"] = c.case_id
                a["case_title"] = c.title
                all_anomalies.append(a)
        return all_anomalies
