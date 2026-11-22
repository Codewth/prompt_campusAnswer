import json

import pytest

from app import engine
from app.models import PolicySection
from app.official_index import INDEX_PATH, build_official_index, search_official


def test_official_index_preserves_source_metadata_and_retrieves_relevant_chunk(tmp_path):
    chunks_path = tmp_path / "chunks.jsonl"
    index_path = tmp_path / "official.sqlite3"
    chunk = {
        "id": "exam-manual-p39-c1",
        "document_id": "exam-manual",
        "document_title": "Examination Manual 2024-25",
        "category": "examinations",
        "academic_year": "2024-25",
        "page": 39,
        "source_url": "https://example.edu/examination-manual.pdf",
        "source_page": "39",
        "extraction_method": "ocr",
        "text": "The makeup examination application must be approved no later than 5 days after the last examination date.",
    }
    chunks_path.write_text(json.dumps(chunk) + "\n", encoding="utf-8")

    assert build_official_index(chunks_path, index_path) == 1
    results = search_official("makeup exam application 5 days", "exams", index_path=index_path)

    assert len(results) == 1
    source = results[0]
    assert source.document == chunk["document_title"]
    assert source.academic_year == chunk["academic_year"]
    assert source.source_url == chunk["source_url"]
    assert source.page == chunk["page"]
    assert source.extraction_method == chunk["extraction_method"]
    assert source.text == chunk["text"]


def test_conflicting_official_attendance_claims_are_both_cited(monkeypatch):
    sources = [
        PolicySection(
            document="SCSET Academic Rules",
            section="Page 19",
            title="Page 19",
            text="A student must have a minimum attendance of 70% in a course during a semester.",
            fictional=False,
            collection="official",
            source_type="official",
            document_id="scset",
            academic_year="not specified",
            source_url="https://example.edu/scset.pdf",
            page=19,
        ),
        PolicySection(
            document="Examination Manual 2024-25",
            section="Page 16",
            title="Page 16",
            text="A student must have a minimum attendance of 75% in a course during a semester.",
            fictional=False,
            collection="official",
            source_type="official",
            document_id="exam-manual",
            academic_year="2024-25",
            source_url="https://example.edu/exam-manual.pdf",
            page=16,
        ),
    ]
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(engine, "search_official", lambda question, category, **kwargs: sources)

    response = engine.answer_question(
        "What minimum attendance percentage is required in a course?",
        collection="official",
    )

    assert response.status == "conflict"
    assert response.confidence == "Low"
    assert response.contact == "Academic Affairs Office"
    assert {citation.source_document for citation in response.citations} == {
        "SCSET Academic Rules",
        "Examination Manual 2024-25",
    }
    quoted_percentages = {
        percentage
        for citation in response.citations
        for percentage in ("70%", "75%")
        if percentage in citation.source_quote
    }
    assert quoted_percentages == {"70%", "75%"}


def test_hostel_curfew_is_not_inferred_from_unrelated_schedule_times(monkeypatch):
    section = PolicySection(
        document="Standing Orders for Hostel document dated 2016",
        section="Page 3",
        title="Page 3",
        text="Students must be back inside the campus by 07:00 PM on all days.",
        fictional=False,
        collection="official",
        source_type="official",
        document_id="hostel-orders",
        academic_year="document dated 2016",
        source_url="https://example.edu/hostel-orders.pdf",
        page=3,
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(engine, "search_official", lambda question, category, **kwargs: [section])

    response = engine.answer_question("What is the exact hostel curfew time?", collection="official")

    assert response.status == "unsupported"
    assert not response.citations
    assert response.contact == "Residence Life Office"


def test_ingested_bennett_sources_cover_conflict_supported_and_unknown_answers(monkeypatch):
    if not INDEX_PATH.is_file():
        pytest.skip("Run official-source ingestion and indexing before this integration test.")

    def fake_generation(question, category, evidence, version, collection, history):
        source = evidence[0]
        return engine._verify_and_normalize(
            {
                "answer": source.text,
                "status": "supported",
                "confidence": "High",
                "citations": [{
                    "source_document": source.document,
                    "source_section": source.section,
                    "source_quote": source.text,
                }],
            },
            evidence,
            category,
            version,
            collection,
        )

    monkeypatch.setattr(engine, "_gemini_answer", fake_generation)

    attendance = engine.answer_question(
        "What minimum attendance percentage is required in a course?",
        collection="official",
    )
    makeup = engine.answer_question(
        "How long after the last examination date can a request citing ignorance or any other reason be accepted?",
        collection="official",
    )
    refund = engine.answer_question(
        "How long does the fee refund take to process for AY 2026-27?",
        collection="official",
    )
    curfew = engine.answer_question("What is the exact hostel curfew time?", collection="official")

    assert attendance.status == "conflict"
    assert {citation.academic_year for citation in attendance.citations} == {"2024-25", "not specified"}
    assert any("70%" in citation.source_quote for citation in attendance.citations)
    assert any("75%" in citation.source_quote for citation in attendance.citations)
    assert makeup.status == "supported"
    assert makeup.citations[0].source_document == "Examination Manual 2024-25"
    assert makeup.citations[0].academic_year == "2024-25"
    assert "5 days" in makeup.citations[0].source_quote
    assert refund.status == "supported"
    assert refund.citations[0].source_document == "Fee Refund Policy AY 2026-27"
    assert "15 working days" in refund.citations[0].source_quote
    assert curfew.status == "unsupported"
    assert not curfew.citations
