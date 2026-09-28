"""
tests/test_graph_engine.py

Unit tests for agent/graph_engine.py:
- Case subgraph extraction
- Verified relational edge construction (CONNECTED_TO, OCCURRED_AT, SUPPORTED_BY)
- Strict reliance on stored data without fabrication
"""

import os
import pytest

from agent.graph_engine import RelationshipGraphEngine
from database.connection import init_db
from database.models import Case, Suspect, Evidence
from database.repository import CaseRepository, SuspectRepository, EvidenceRepository, TimelineRepository


@pytest.fixture
def graph_eng(tmp_path):
    db_file = str(tmp_path / "test_graph.db")
    init_db(db_file)
    c_repo = CaseRepository(db_path=db_file)
    s_repo = SuspectRepository(db_path=db_file)
    e_repo = EvidenceRepository(db_path=db_file)
    t_repo = TimelineRepository(db_path=db_file)

    # 1. Create Case
    test_case = Case(
        case_id="CASE-GRAPH-01",
        title="Dockside Smuggling Network",
        location="Seaport Terminal 3",
        assigned_investigator="Lead Det. Briggs",
    )
    c_repo.create_case(test_case)

    # 2. Create Suspect linked to Case
    test_suspect = Suspect(
        suspect_id="SUSP-G-01",
        name="Viktor Vane",
        alias="The Captain",
        case_connections=["CASE-GRAPH-01"],
        known_associations="Black Pearl Cargo Syndicate",
    )
    s_repo.create_suspect(test_suspect)

    # 3. Create Evidence linked to Case
    test_ev = Evidence(
        evidence_id="EV-G-01",
        case_id="CASE-GRAPH-01",
        file_type="PDF",
        description="Cargo manifest with altered vessel registration",
        sha256_hash="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
    )
    e_repo.create_evidence(test_ev)

    return RelationshipGraphEngine(case_repo=c_repo, suspect_repo=s_repo, evidence_repo=e_repo, timeline_repo=t_repo)


def test_build_case_subgraph(graph_eng):
    graph = graph_eng.build_case_subgraph("CASE-GRAPH-01")
    nodes = graph["nodes"]
    edges = graph["edges"]

    # Verify nodes present
    node_types = {n["type"] for n in nodes}
    assert "Case" in node_types
    assert "Location" in node_types
    assert "Person" in node_types
    assert "Evidence" in node_types
    assert "Organization" in node_types

    # Verify edge relations
    relations = {e["relation"] for e in edges}
    assert "OCCURRED_AT" in relations
    assert "CONNECTED_TO" in relations
    assert "SUPPORTED_BY" in relations
    assert "ASSOCIATED_WITH" in relations


def test_build_global_network(graph_eng):
    network = graph_eng.build_global_network()
    assert network["node_count"] >= 5
    assert network["edge_count"] >= 4
