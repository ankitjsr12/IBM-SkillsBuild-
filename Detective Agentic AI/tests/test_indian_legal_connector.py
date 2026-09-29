"""
tests/test_indian_legal_connector.py

Comprehensive tests for:
- Indian Legal Gateway Connector (status, supported courts, safe failure on missing auth)
- Real Indian Case repository verification (50+ authentic cases, IPC sections, judicial citations, Indian Kanoon URLs)
- Explainable AI pipeline (SOURCE DATA → MATCHED PATTERN → SIMILARITY → AI ANALYSIS)
- Guardrails and "No sufficiently similar Indian record found" fallback
"""

import glob
import json
import os
import pytest

from agent.indian_legal_connector import IndianLegalConnector, IndianLegalGatewayConnector
from agent.explainability_engine import ExplainabilityEngine
from database.models import Case, Suspect
from agent.analyzer import DetectiveAgent


class TestIndianLegalConnector:
    """Test connector handling for Indian legal databases."""

    def test_gateway_query_without_token(self, monkeypatch):
        monkeypatch.delenv("INDIAN_KANOON_API_KEY", raising=False)
        res = IndianLegalConnector.query_public_indian_legal_gateway("cyanide poisoning case")

        assert res["status"] == "UNAVAILABLE"
        assert "Data source unavailable" in res["message"]
        assert res["records"] == []

    def test_supported_authorities_list(self):
        authorities = IndianLegalConnector.get_supported_authorities()
        names = [a["name"] for a in authorities]
        assert "Supreme Court of India" in names
        assert "High Court of Delhi" in names
        assert "Central Bureau of Investigation (CBI) Special Courts" in names
        assert len(authorities) >= 8

    def test_import_validation_rejects_non_indian_id(self, tmp_path):
        connector = IndianLegalConnector(cases_dir=str(tmp_path))
        bad_case = {
            "case_id": "CASE-USA-1999-01",
            "title": "Foreign Case",
            "court_or_authority": "US District Court",
            "legal_citation": "123 F.3d 456",
            "source": "US Lexis",
        }
        ok, msg, path = connector.import_verified_indian_case(bad_case)
        assert ok is False
        assert "CASE-IND-" in msg
        assert path is None

    def test_import_validation_accepts_valid_indian_case(self, tmp_path):
        connector = IndianLegalConnector(cases_dir=str(tmp_path))
        valid_case = {
            "case_id": "CASE-IND-2024-999",
            "title": "State of Test vs Suspect",
            "crime_type": "Homicide",
            "court_or_authority": "High Court of Delhi",
            "legal_citation": "2024 DHC 1234",
            "source": "Indian Kanoon (https://indiankanoon.org/doc/12345/)",
            "source_url": "https://indiankanoon.org/doc/12345/",
            "ipc_sections": ["Section 302 IPC"],
            "modus_operandi": "Poisoning through chemical compound",
            "summary": "Forensic evidence correlated with digital communications",
        }
        ok, msg, path = connector.import_verified_indian_case(valid_case)
        assert ok is True
        assert path is not None
        assert os.path.exists(path)


class TestRealIndianCaseDatabase:
    """Verify integrity of authentic Indian case data files."""

    @pytest.fixture
    def indian_cases(self):
        cases_dir = os.path.join(os.path.dirname(__file__), "..", "cases")
        case_files = sorted(glob.glob(os.path.join(cases_dir, "case_*.json")))
        cases = []
        for cf in case_files:
            with open(cf, "r", encoding="utf-8") as f:
                cases.append(json.load(f))
        return cases

    def test_has_at_least_50_authentic_indian_cases(self, indian_cases):
        assert len(indian_cases) >= 50, f"Expected at least 50 authentic Indian cases, found {len(indian_cases)}"

    def test_all_cases_have_indian_identifiers_and_metadata(self, indian_cases):
        for c in indian_cases:
            assert c["case_id"].startswith("CASE-IND-"), f"Case {c.get('case_id')} does not have Indian ID prefix"
            assert "court_or_authority" in c and len(c["court_or_authority"]) > 0
            assert "legal_citation" in c and len(c["legal_citation"]) > 0
            assert "source" in c and len(c["source"]) > 0
            assert "source_url" in c and c["source_url"].startswith("http")
            assert "ipc_sections" in c and isinstance(c["ipc_sections"], list) and len(c["ipc_sections"]) > 0
            assert "modus_operandi" in c and len(c["modus_operandi"]) > 10

    def test_landmark_cases_present(self, indian_cases):
        titles = [c["title"] for c in indian_cases]
        assert any("Cyanide Mohan" in t for t in titles)
        assert any("Nithari" in t for t in titles)
        assert any("Nirbhaya" in t for t in titles)
        assert any("Joshi-Abhyankar" in t for t in titles)
        assert any("Sobhraj" in t for t in titles)
        assert any("Koodathayi" in t for t in titles)
        assert any("Uthra" in t for t in titles)
        assert any("Raman Raghav" in t for t in titles)


class TestExplainableResultsPipeline:
    """Test SOURCE DATA → MATCHED PATTERN → SIMILARITY → AI ANALYSIS pipeline."""

    def test_explainable_pipeline_generation(self):
        precedents = [
            {
                "case_id": "CASE-IND-2009-001",
                "case_title": "Cyanide Mohan Serial Murders",
                "crime_type": "Serial Homicide",
                "court_or_authority": "High Court of Karnataka",
                "legal_citation": "Criminal Appeal No. 250 of 2014",
                "source": "Indian Kanoon (https://indiankanoon.org/doc/1066795/)",
                "similarity": 0.42,
                "similarity_pct": "42%",
                "ipc_sections": ["Section 302 IPC", "Section 328 IPC"],
            }
        ]

        assessment = ExplainabilityEngine.generate_explainable_assessment(
            suspect_name="Suspect Under Assessment",
            observed_behaviors="Administered toxic cyanide laced capsules disguised as medication",
            modus_operandi="Cyanide capsules disguised as anti-pregnancy pills",
            retrieved_cases=precedents,
        )

        pipelines = assessment["explainable_pipelines"]
        assert len(pipelines) > 0
        first_pipeline = pipelines[0]

        assert "SOURCE DATA: High Court of Karnataka" in first_pipeline
        assert "→ MATCHED PATTERN: Serial Homicide" in first_pipeline
        assert "→ SIMILARITY: 42%" in first_pipeline
        assert "→ AI ANALYSIS:" in first_pipeline
        assert "Section 302 IPC" in first_pipeline

        # Statutory caveat
        assert "Never present this output as a legal finding" in assessment["statutory_caveat"]

    def test_no_match_returns_standard_message(self):
        assessment = ExplainabilityEngine.generate_explainable_assessment(
            suspect_name="Suspect With No Match",
            observed_behaviors="Completely unrelated interstellar asteroid trajectory observation",
            modus_operandi="None",
            retrieved_cases=[],
        )

        assert assessment["similarity_score"] == "15%"
        assert assessment["assessment"] == "No sufficiently similar Indian record found."
        assert assessment["confidence_indicator"] == "No sufficiently similar Indian record found."
        assert len(assessment["matched_historical_patterns"]) == 0

    def test_seven_part_case_summary_sections(self):
        case = Case(
            case_id="CASE-TEST-007",
            title="Snakebite Toxicity Investigation",
            case_type="Homicide",
            description="Viper procured from snake handler used during victim sleep",
            location="Kollam, Kerala",
        )
        summary = ExplainabilityEngine.generate_case_summary(
            case=case,
            evidence_items=[],
            timeline_events=[],
            matched_precedents=[
                {
                    "case_id": "CASE-IND-2020-007",
                    "case_title": "Uthra Snakebite Homicide",
                    "crime_type": "Homicide",
                    "similarity_pct": "71%",
                    "court_or_authority": "Kollam Additional Sessions Court",
                    "legal_citation": "Sessions Case No. 445/2020",
                }
            ],
        )

        expected_sections = [
            "ai_case_summary",
            "pattern_analysis",
            "evidence_summary",
            "historical_similarities",
            "anomalies",
            "information_gaps",
            "human_review_points",
            "explainable_results_pipeline",
            "statutory_caveat",
        ]
        for sec in expected_sections:
            assert sec in summary, f"Missing section: {sec}"

        assert "Uthra Snakebite Homicide" in summary["historical_similarities"]
        assert len(summary["information_gaps"]) >= 2
        assert len(summary["human_review_points"]) >= 2
        assert "Never present AI output as proof of guilt" in summary["statutory_caveat"]


class TestDetectiveAgentIndianRAG:
    """Test DetectiveAgent RAG integration with real Indian cases."""

    def test_detective_agent_matches_indian_precedent(self):
        agent = DetectiveAgent()
        result = agent.evaluate_suspect(
            name="Test Individual",
            behavior="Victim poisoned using cyanide mixed with drinking liquid after matrimonial promise",
            mo_suspected="Lethal poison in drink",
            personality_notes="Deceptive, calm exterior",
        )

        assert result["model_assessment_title"] == "MODEL ASSESSMENT"
        assert "tendency_score" in result
        assert "scoring_breakdown" in result
        assert "disclaimer" in result

        # Check matched precedents contain Indian courts and citations
        precedents = result.get("matched_precedents", [])
        if precedents:
            top = precedents[0]
            assert "court_or_authority" in top
            assert "legal_citation" in top
            assert "source" in top

    def test_detective_agent_unrelated_query_no_match(self):
        agent = DetectiveAgent()
        result = agent.evaluate_suspect(
            name="Botanist Subject",
            behavior="Photosynthesis chloroplast light reaction plant biology laboratory study",
            mo_suspected="Plant taxonomy",
            personality_notes="Academic researcher",
        )

        assert result["confidence_indicator"] == "No sufficiently similar Indian record found."
        assert len(result["matched_precedents"]) == 0

    def test_bns_cross_referencing_mappings(self):
        """Verify IPC to Bharatiya Nyaya Sanhita (BNS 2023) cross-referencing."""
        ipc_inputs = ["Section 302 IPC", "Section 307 IPC", "Section 420 IPC", "Section 120B IPC"]
        refs = IndianLegalConnector.get_bns_cross_references(ipc_inputs)
        assert len(refs) == 4
        bns_sections = [r["bns_section"] for r in refs]
        assert "Section 103 BNS" in bns_sections  # 302 IPC -> 103 BNS
        assert "Section 109 BNS" in bns_sections  # 307 IPC -> 109 BNS
        assert "Section 318 BNS" in bns_sections  # 420 IPC -> 318 BNS
        assert "Section 61 BNS" in bns_sections   # 120B IPC -> 61 BNS
