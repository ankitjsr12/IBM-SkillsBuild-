"""
tests/test_document_engine.py

Unit tests for agent/document_engine.py:
- Text extraction from Plain Text, CSV, JSON
- Entity extraction (emails, phones, IPs, amounts, dates)
- Image metadata extraction
"""

import io
import pytest
from PIL import Image
from agent.document_engine import DocumentEngine


def test_plain_text_and_entity_extraction():
    sample_text = """
    Incident Report:
    On 2026-05-14, suspect contacted informant via test.witness@agency.org.
    Phone number dialed: +1-555-234-5678.
    IP address traced to 192.168.1.105.
    Ransom demand requested: Rs. 500,000 in cash.
    """
    res = DocumentEngine.extract_text_from_bytes(sample_text.encode("utf-8"), "incident_log.txt")

    assert res["format"] == "TXT"
    assert "Incident Report" in res["text"]

    entities = res["entities"]
    assert "test.witness@agency.org" in entities["emails"]
    assert any("555" in p for p in entities["phones"])
    assert "192.168.1.105" in entities["ips"]
    assert any("500,000" in a for a in entities["amounts"])
    assert "2026-05-14" in entities["dates"]


def test_csv_extraction():
    csv_data = "TransactionID,Amount,Target\nTX101,Rs. 50000,AccountB\nTX102,Rs. 75000,AccountC\n"
    res = DocumentEngine.extract_text_from_bytes(csv_data.encode("utf-8"), "ledger.csv")

    assert res["format"] == "CSV"
    assert "TX101" in res["text"]
    assert "AccountC" in res["text"]


def test_json_extraction():
    json_bytes = b'{"case_id": "CASE-99", "suspect": "John Smith", "risk": "HIGH"}'
    res = DocumentEngine.extract_text_from_bytes(json_bytes, "metadata.json")

    assert res["format"] == "JSON"
    assert "CASE-99" in res["text"]
    assert "John Smith" in res["text"]


def test_image_metadata_extraction():
    # Create an in-memory PNG
    img = Image.new("RGB", (120, 80), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    res = DocumentEngine.extract_text_from_bytes(png_bytes, "cctv_frame.png")
    assert res["format"] == "PNG"
    assert "IMAGE EVIDENCE" in res["text"]
    assert res["metadata"]["dimensions"] == "120x80"
