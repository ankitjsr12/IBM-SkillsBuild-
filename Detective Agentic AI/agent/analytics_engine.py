"""
agent/analytics_engine.py

Analytics & Aggregation Engine.
Aggregates live database statistics across authentic Indian cases, evidence custody,
suspects, timeline events, and verified judicial sources without mock data.
"""

import logging
from typing import Any, Dict, List, Optional
from database.connection import DEFAULT_DB_PATH
from database.repository import CaseRepository, SuspectRepository, EvidenceRepository, TimelineRepository

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Aggregates investigative statistics from relational storage."""

    def __init__(
        self,
        case_repo: Optional[CaseRepository] = None,
        suspect_repo: Optional[SuspectRepository] = None,
        evidence_repo: Optional[EvidenceRepository] = None,
        timeline_repo: Optional[TimelineRepository] = None,
        db_path: Optional[str] = None,
    ):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.case_repo = case_repo or CaseRepository(self.db_path)
        self.suspect_repo = suspect_repo or SuspectRepository(self.db_path)
        self.evidence_repo = evidence_repo or EvidenceRepository(self.db_path)
        self.timeline_repo = timeline_repo or TimelineRepository(self.db_path)

    def get_kpi_summary(self) -> Dict[str, Any]:
        """Return headline KPI metrics across all operational entities."""
        case_stats = self.case_repo.count_cases()
        total_cases = case_stats.get("total", 0)
        open_cases = case_stats.get("open", 0)
        review_cases = case_stats.get("under_review", 0)
        closed_cases = case_stats.get("closed", 0) + case_stats.get("archived", 0)

        total_suspects = self.suspect_repo.count_suspects()
        ev_counts = self.evidence_repo.count_evidence()
        total_evidence = ev_counts.get("total", 0) if isinstance(ev_counts, dict) else ev_counts
        total_events = self.timeline_repo.count_events()

        evidence_items = self.evidence_repo.list_evidence() or []
        total_storage_bytes = sum(
            (e.file_size_bytes or 0) for e in evidence_items
        )
        storage_mb = round(total_storage_bytes / (1024 * 1024), 2)

        # Count total AI evaluations recorded
        suspects = self.suspect_repo.list_suspects(limit=500)
        total_ai_evals = sum(len(s.assessment_history) for s in suspects)

        return {
            "total_cases": total_cases,
            "open_cases": open_cases,
            "under_review_cases": review_cases,
            "closed_cases": closed_cases,
            "total_suspects": total_suspects,
            "total_evidence_items": total_evidence,
            "total_timeline_events": total_events,
            "total_storage_bytes": total_storage_bytes,
            "storage_mb": storage_mb,
            "total_ai_evals": total_ai_evals,
        }

    def get_cases_by_status(self) -> Dict[str, int]:
        """Aggregate case count by status."""
        stats = self.case_repo.count_cases()
        return stats.get("by_status", {})

    def get_cases_by_priority(self) -> Dict[str, int]:
        """Aggregate case count by priority level."""
        stats = self.case_repo.count_cases()
        return stats.get("by_priority", {})

    def get_cases_by_type(self) -> Dict[str, int]:
        """Aggregate case count by crime/case classification type."""
        cases = self.case_repo.list_cases(limit=1000)
        breakdown: Dict[str, int] = {}
        for c in cases:
            ctype = c.case_type or "General Investigation"
            breakdown[ctype] = breakdown.get(ctype, 0) + 1
        return breakdown

    def get_evidence_by_type(self) -> Dict[str, int]:
        """Aggregate evidence count by file/media format."""
        evidence = self.evidence_repo.list_evidence()
        breakdown: Dict[str, int] = {}
        for e in evidence:
            ftype = (e.file_type or "OTHER").upper()
            breakdown[ftype] = breakdown.get(ftype, 0) + 1
        return breakdown

    def get_indian_courts_distribution(self) -> Dict[str, int]:
        """Aggregate cases by judicial court / authority."""
        cases = self.case_repo.list_cases(limit=1000)
        breakdown: Dict[str, int] = {}
        for c in cases:
            meta = c.extra_metadata if isinstance(c.extra_metadata, dict) else {}
            court = meta.get("court_or_authority") or "Sessions / High Court"
            court_short = court.split("/")[0].strip()
            breakdown[court_short] = breakdown.get(court_short, 0) + 1
        return breakdown

    def get_verified_sources_summary(self) -> List[Dict[str, Any]]:
        """List distinct verified Indian legal sources in the repository."""
        cases = self.case_repo.list_cases(limit=1000)
        sources_map: Dict[str, Dict[str, Any]] = {}
        for c in cases:
            meta = c.extra_metadata if isinstance(c.extra_metadata, dict) else {}
            source_name = meta.get("source") or "Indian Legal Records"
            if source_name not in sources_map:
                sources_map[source_name] = {
                    "source": source_name,
                    "court": meta.get("court_or_authority", "Indian Judicial Courts"),
                    "source_url": meta.get("source_url", ""),
                    "cases_count": 0,
                }
            sources_map[source_name]["cases_count"] += 1
        return list(sources_map.values())

    def get_recent_case_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recently updated cases with summary fields."""
        cases = self.case_repo.list_cases(limit=limit)
        return [
            {
                "case_id": c.case_id,
                "title": c.title,
                "case_type": c.case_type,
                "status": c.status,
                "priority": c.priority,
                "assigned_investigator": c.assigned_investigator,
                "updated_at": c.updated_at,
            }
            for c in cases
        ]
