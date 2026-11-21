import json
from datetime import datetime, timezone
from pathlib import Path

from app.engine import answer_question


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "test-data" / "test-cases.json"
RESULTS_PATH = ROOT / "test-data" / "demo-evaluation-results.json"


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    results = []
    test_number = 0
    for version in ("v1", "v2", "v3"):
        for case in cases:
            test_number += 1
            actual = answer_question(case["input"], version).model_dump()
            passed = (
                actual["category"] == case["expected"]["category"]
                and actual["status"] == case["expected"]["status"]
                and (not case["expected"].get("citation_required") or bool(actual["citations"]))
            )
            results.append({
                "test_number": test_number,
                "test_case_number": case["test_number"],
                "input": case["input"],
                "test_type": case["test_type"],
                "expected_output": case["expected"],
                "actual_output": actual,
                "pass": passed,
                "prompt_version": version,
                "evaluation_mode": actual["mode"],
            })
    summary = {
        "evaluation_mode": "deterministic_demo" if all(row["evaluation_mode"] == "demo" for row in results) else "live_gemini",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(row["pass"] for row in results),
        "pass_percentage": round(100 * sum(row["pass"] for row in results) / len(results), 1) if results else 0,
        "results": results,
    }
    RESULTS_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{summary['evaluation_mode']}: {summary['passed']}/{summary['total']} passed ({summary['pass_percentage']}%)")
    print(f"Results: {RESULTS_PATH}")
    if summary["passed"] != summary["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
