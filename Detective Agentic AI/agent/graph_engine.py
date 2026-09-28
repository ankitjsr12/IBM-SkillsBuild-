"""
agent/graph_engine.py

Case Connection and Entity Relationship Graph Engine.
Implements Part 14 (Case Connection Graph).

Nodes:
  - Case
  - Person (Suspect, Assigned Investigator)
  - Evidence
  - Location
  - Organization
  - Event

Edges:
  - CONNECTED_TO (Suspect <-> Case)
  - MENTIONED_IN (Person/Org <-> Evidence/Case)
  - ASSOCIATED_WITH (Suspect <-> Known Association)
  - SUPPORTED_BY (Case <-> Evidence)
  - OCCURRED_AT (Case/Event <-> Location)

MANDATORY RULE:
Only create relationships supported by stored information.
Never invent imaginary graph connections.
"""

import collections
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from database.repository import CaseRepository, SuspectRepository, EvidenceRepository, TimelineRepository

logger = logging.getLogger(__name__)


class RelationshipGraphEngine:
    """Extracts entity nodes and relational edges strictly from active database records."""

    def __init__(
        self,
        case_repo: Optional[CaseRepository] = None,
        suspect_repo: Optional[SuspectRepository] = None,
        evidence_repo: Optional[EvidenceRepository] = None,
        timeline_repo: Optional[TimelineRepository] = None,
    ):
        self.case_repo = case_repo or CaseRepository()
        self.suspect_repo = suspect_repo or SuspectRepository()
        self.evidence_repo = evidence_repo or EvidenceRepository()
        self.timeline_repo = timeline_repo or TimelineRepository()

    def build_case_subgraph(self, case_id: str) -> Dict[str, Any]:
        """Build relationship graph centered on a specific case."""
        case = self.case_repo.get_case(case_id.strip())
        if not case:
            return {"nodes": [], "edges": []}

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        # 1. Central Case Node
        c_node_id = f"case:{case.case_id}"
        nodes[c_node_id] = {
            "id": c_node_id,
            "label": f"[{case.case_id}] {case.title}",
            "type": "Case",
            "status": case.status,
            "priority": case.priority,
        }

        # 2. Location Node
        if case.location and case.location.lower() != "not provided":
            loc_id = f"loc:{case.location.strip().lower()}"
            nodes[loc_id] = {"id": loc_id, "label": case.location, "type": "Location"}
            edges.append({
                "source": c_node_id,
                "target": loc_id,
                "relation": "OCCURRED_AT",
                "label": "Occurred at",
            })

        # 3. Investigator Node
        if case.assigned_investigator and case.assigned_investigator.lower() != "unassigned":
            inv_id = f"person:{case.assigned_investigator.strip().lower()}"
            nodes[inv_id] = {"id": inv_id, "label": case.assigned_investigator, "type": "Person", "subtype": "Investigator"}
            edges.append({
                "source": inv_id,
                "target": c_node_id,
                "relation": "CONNECTED_TO",
                "label": "Investigating",
            })

        # 4. Suspect Nodes
        all_suspects = self.suspect_repo.list_suspects()
        for s in all_suspects:
            if case.case_id in s.case_connections:
                s_id = f"suspect:{s.suspect_id}"
                nodes[s_id] = {
                    "id": s_id,
                    "label": f"{s.name} ({s.alias})" if s.alias and s.alias != "Not provided" else s.name,
                    "type": "Person",
                    "subtype": "Suspect",
                }
                edges.append({
                    "source": s_id,
                    "target": c_node_id,
                    "relation": "CONNECTED_TO",
                    "label": "Connected to case",
                })

                # Known associations (Person / Org)
                if s.known_associations and s.known_associations != "Not provided":
                    assoc_id = f"org:{s.known_associations.strip().lower()}"
                    nodes[assoc_id] = {"id": assoc_id, "label": s.known_associations, "type": "Organization"}
                    edges.append({
                        "source": s_id,
                        "target": assoc_id,
                        "relation": "ASSOCIATED_WITH",
                        "label": "Associated with",
                    })

        # 5. Evidence Nodes
        evidence_items = self.evidence_repo.list_evidence(case_id=case.case_id)
        for ev in evidence_items:
            ev_node_id = f"ev:{ev.evidence_id}"
            nodes[ev_node_id] = {
                "id": ev_node_id,
                "label": f"[{ev.evidence_id}] {ev.file_type}",
                "type": "Evidence",
                "hash": ev.sha256_hash[:12] + "...",
            }
            edges.append({
                "source": c_node_id,
                "target": ev_node_id,
                "relation": "SUPPORTED_BY",
                "label": "Supported by evidence",
            })

        # 6. Timeline Event Nodes
        events = self.timeline_repo.list_events_for_case(case.case_id)
        for t_ev in events:
            ev_t_id = f"event:{t_ev.event_id}"
            nodes[ev_t_id] = {
                "id": ev_t_id,
                "label": f"[{t_ev.event_type}] {t_ev.description[:25]}",
                "type": "Event",
                "timestamp": t_ev.timestamp,
            }
            edges.append({
                "source": c_node_id,
                "target": ev_t_id,
                "relation": "MENTIONED_IN",
                "label": "Event logged",
            })

            # Event -> Evidence link if present
            if t_ev.linked_evidence_id:
                ev_target = f"ev:{t_ev.linked_evidence_id}"
                if ev_target in nodes:
                    edges.append({
                        "source": ev_t_id,
                        "target": ev_target,
                        "relation": "SUPPORTED_BY",
                        "label": "References evidence",
                    })

        return {
            "case_id": case.case_id,
            "nodes": list(nodes.values()),
            "edges": edges,
            "summary": f"{len(nodes)} entity nodes and {len(edges)} verified relational edges.",
        }

    def build_global_network(self) -> Dict[str, Any]:
        """Compile a multi-case relationship network across the entire database."""
        all_cases = self.case_repo.list_cases()
        all_nodes: Dict[str, Dict[str, Any]] = {}
        all_edges: List[Dict[str, Any]] = []

        for c in all_cases:
            sub = self.build_case_subgraph(c.case_id)
            for n in sub["nodes"]:
                all_nodes[n["id"]] = n
            all_edges.extend(sub["edges"])

        return {
            "nodes": list(all_nodes.values()),
            "edges": all_edges,
            "node_count": len(all_nodes),
            "edge_count": len(all_edges),
        }
