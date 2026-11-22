import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.engine import GeminiUnavailableError, answer_question
from app.models import ConversationMessage


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "test-data" / "test-cases.json"
RESULTS_PATH = ROOT / "test-data" / "demo-evaluation-results.json"
CSV_PATH = ROOT / "test-data" / "evaluation-results.csv"
COMPARISON_PATH = ROOT / "test-data" / "prompt-comparison-log.json"
PUBLIC_RESULTS_PATH = ROOT / "frontend" / "public" / RESULTS_PATH.name
PROMPT_VERSIONS = ("v1", "v2", "v3")


def _history_for_case(case: dict, actual_by_case: dict[int, dict], cases_by_number: dict[int, dict]) -> list[ConversationMessage]:
    previous_number = case.get("history_from")
    if previous_number is None:
        return []
    previous_case = cases_by_number[previous_number]
    previous_output = actual_by_case.get(previous_number)
    history = [ConversationMessage(role="user", content=previous_case["input"])]
    if previous_output and previous_output.get("answer"):
        history.append(
            ConversationMessage(
                role="assistant",
                content=previous_output["answer"],
                response_type=previous_output["response_type"],
                category=previous_output["category"],
            )
        )
    return history


def _matches_expected(actual: dict, expected: dict) -> bool:
    return (
        actual.get("response_type") == expected["response_type"]
        and actual.get("status") == expected["status"]
        and len(actual.get("citations", [])) >= expected.get("minimum_citations", 0)
    )


def _pass_percentage(passed: int, failed: int) -> float | None:
    evaluable = passed + failed
    return round(100 * passed / evaluable, 1) if evaluable else None


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases_by_number = {case["test_number"]: case for case in cases}
    results = []

    for version in PROMPT_VERSIONS:
        actual_by_case: dict[int, dict] = {}
        for case in cases:
            history = _history_for_case(case, actual_by_case, cases_by_number)
            try:
                actual = answer_question(
                    case["input"],
                    version,
                    case.get("collection", "official"),
                    history,
                ).model_dump(mode="json")
                actual_by_case[case["test_number"]] = actual
                passed = _matches_expected(actual, case["expected"])
                outcome = "pass" if passed else "fail"
                evaluation_mode = actual["mode"]
            except GeminiUnavailableError as error:
                actual = {
                    "response_type": "not_returned",
                    "status": "service_unavailable",
                    "error": str(error),
                    "citations": [],
                }
                actual_by_case[case["test_number"]] = actual
                passed = None
                outcome = "blocked"
                evaluation_mode = "service_unavailable"

            results.append({
                "test_number": case["test_number"],
                "test_id": case["test_id"],
                "input": case["input"],
                "test_type": case["test_type"],
                "collection": case.get("collection", "official"),
                "expected_output": case["expected"],
                "actual_output": actual,
                "outcome": outcome,
                "pass": passed,
                "prompt_version": version,
                "evaluation_mode": evaluation_mode,
            })

    per_version = {}
    for version in PROMPT_VERSIONS:
        version_results = [row for row in results if row["prompt_version"] == version]
        passed = sum(row["outcome"] == "pass" for row in version_results)
        failed = sum(row["outcome"] == "fail" for row in version_results)
        blocked = sum(row["outcome"] == "blocked" for row in version_results)
        per_version[version] = {
            "total": len(version_results),
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "evaluable": passed + failed,
            "live_gemini_runs": sum(row["evaluation_mode"] == "gemini" for row in version_results),
            "pass_percentage": _pass_percentage(passed, failed),
        }

    modes = {row["evaluation_mode"] for row in results}
    if "gemini" in modes:
        evaluation_mode = "live_gemini"
    elif "service_unavailable" in modes:
        evaluation_mode = "gemini_unavailable"
    else:
        evaluation_mode = "local_checks"
    live_cases_by_version = {
        version: {
            row["test_number"]
            for row in results
            if row["prompt_version"] == version and row["evaluation_mode"] == "gemini"
        }
        for version in PROMPT_VERSIONS
    }
    prompt_comparable_cases = sorted(set.intersection(*(live_cases_by_version[version] for version in PROMPT_VERSIONS)))
    comparison_note = (
        f"{len(prompt_comparable_cases)} inputs completed with Gemini for all three prompt versions using the same configured model. Results are descriptive for this run, not proof of statistical significance."
        if prompt_comparable_cases
        else "No inputs completed with Gemini for all three prompt versions. Local deterministic checks validate routing and evidence behavior only; blocked generation cases are excluded from pass percentages."
    )
    passed = sum(row["outcome"] == "pass" for row in results)
    failed = sum(row["outcome"] == "fail" for row in results)
    blocked = sum(row["outcome"] == "blocked" for row in results)
    summary = {
        "evaluation_mode": evaluation_mode,
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_case_count": len(cases),
        "prompt_versions": list(PROMPT_VERSIONS),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "evaluable": passed + failed,
        "pass_percentage": _pass_percentage(passed, failed),
        "version_summaries": per_version,
        "prompt_comparable_case_count": len(prompt_comparable_cases),
        "prompt_comparison_note": comparison_note,
        "results": results,
    }

    RESULTS_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    PUBLIC_RESULTS_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "test_number", "test_id", "input", "test_type", "collection",
            "expected_output", "actual_output", "outcome", "prompt_version", "evaluation_mode",
        ])
        writer.writeheader()
        for row in results:
            writer.writerow({
                "test_number": row["test_number"],
                "test_id": row["test_id"],
                "input": row["input"],
                "test_type": row["test_type"],
                "collection": row["collection"],
                "expected_output": json.dumps(row["expected_output"], ensure_ascii=False),
                "actual_output": json.dumps(row["actual_output"], ensure_ascii=False),
                "outcome": row["outcome"],
                "prompt_version": row["prompt_version"],
                "evaluation_mode": row["evaluation_mode"],
            })

    case_comparisons = []
    for case in cases:
        version_outputs = {
            version: next(
                row for row in results
                if row["test_number"] == case["test_number"] and row["prompt_version"] == version
            )
            for version in PROMPT_VERSIONS
        }
        case_comparisons.append({
            "test_number": case["test_number"],
            "test_id": case["test_id"],
            "input": case["input"],
            "test_type": case["test_type"],
            "collection": case.get("collection", "official"),
            "history_from": case.get("history_from"),
            "same_input_for_all_versions": len({row["input"] for row in version_outputs.values()}) == 1,
            "live_gemini_comparable": all(
                row["evaluation_mode"] == "gemini"
                for row in version_outputs.values()
            ),
            "versions": {
                version: {
                    "outcome": row["outcome"],
                    "evaluation_mode": row["evaluation_mode"],
                    "response_type": row["actual_output"].get("response_type"),
                    "status": row["actual_output"].get("status"),
                    "answer": row["actual_output"].get("answer"),
                    "error": row["actual_output"].get("error"),
                    "citations": [
                        {
                            "source_document": citation.get("source_document"),
                            "source_section": citation.get("source_section"),
                            "page": citation.get("page"),
                        }
                        for citation in row["actual_output"].get("citations", [])
                    ],
                }
                for version, row in version_outputs.items()
            },
        })

    comparison = {
        "executed_at_utc": summary["executed_at_utc"],
        "evaluation_mode": evaluation_mode,
        "gemini_configured": summary["gemini_configured"],
        "gemini_model": summary["gemini_model"],
        "prompt_comparable_case_count": summary["prompt_comparable_case_count"],
        "prompt_comparison_note": comparison_note,
        "versions": per_version,
        "case_comparisons": case_comparisons,
    }
    COMPARISON_PATH.write_text(json.dumps(comparison, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"{evaluation_mode}: {passed} passed, {failed} failed, {blocked} blocked "
        f"of {len(results)} runs; {len(cases)} inputs x {len(PROMPT_VERSIONS)} prompt versions"
    )
    print(f"Results: {RESULTS_PATH}")
    print(f"CSV: {CSV_PATH}")
    print(f"Prompt comparison: {COMPARISON_PATH}")


if __name__ == "__main__":
    main()
