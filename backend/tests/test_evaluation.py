import json
from types import SimpleNamespace

import run_evaluation
from app.engine import GeminiUnavailableError


def test_evaluation_records_unavailable_generation_as_blocked(monkeypatch, tmp_path):
    cases = [
        {
            "test_number": 1,
            "test_id": "greeting",
            "input": "Hello",
            "test_type": "Normal",
            "collection": "official",
            "expected": {
                "response_type": "general_conversation",
                "status": "supported",
                "minimum_citations": 0,
            },
        },
        {
            "test_number": 2,
            "test_id": "general-question",
            "input": "What is Python?",
            "test_type": "Normal",
            "collection": "official",
            "expected": {
                "response_type": "general_knowledge",
                "status": "supported",
                "minimum_citations": 0,
            },
        },
    ]
    cases_path = tmp_path / "test-cases.json"
    cases_path.write_text(json.dumps(cases), encoding="utf-8")
    results_path = tmp_path / "results.json"
    csv_path = tmp_path / "results.csv"
    comparison_path = tmp_path / "comparison.json"
    public_results_path = tmp_path / "public" / "results.json"
    public_results_path.parent.mkdir()
    monkeypatch.setattr(run_evaluation, "CASES_PATH", cases_path)
    monkeypatch.setattr(run_evaluation, "RESULTS_PATH", results_path)
    monkeypatch.setattr(run_evaluation, "CSV_PATH", csv_path)
    monkeypatch.setattr(run_evaluation, "COMPARISON_PATH", comparison_path)
    monkeypatch.setattr(run_evaluation, "PUBLIC_RESULTS_PATH", public_results_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def fake_answer(question, version, collection, history):
        if question == "What is Python?":
            raise GeminiUnavailableError("Gemini is not configured.")
        return SimpleNamespace(model_dump=lambda mode: {
            "category": "out_of_scope",
            "answer": "Hello! I can help with questions.",
            "response_type": "general_conversation",
            "status": "supported",
            "citations": [],
            "mode": "predefined",
        })

    monkeypatch.setattr(run_evaluation, "answer_question", fake_answer)
    run_evaluation.main()

    result = json.loads(results_path.read_text(encoding="utf-8"))
    assert result["total"] == 6
    assert result["passed"] == 3
    assert result["failed"] == 0
    assert result["blocked"] == 3
    assert result["pass_percentage"] == 100.0
    assert result["prompt_comparable_case_count"] == 0
    assert all(row["outcome"] == "blocked" for row in result["results"] if row["test_id"] == "general-question")
    assert csv_path.is_file()
    assert comparison_path.is_file()
    assert public_results_path.is_file()
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert len(comparison["case_comparisons"]) == 2
    assert all(case["same_input_for_all_versions"] for case in comparison["case_comparisons"])
    assert not comparison["case_comparisons"][1]["live_gemini_comparable"]
