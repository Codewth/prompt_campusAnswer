# Prompt iteration log

The policy-generation prompt files are in `prompts/v1/`, `prompts/v2/`, `prompts/v3/`, and `prompts/final/`. V1 preserves the Milestone 1 baseline; V2 and V3 add explicit controls. `prompts/final/prompt.txt` is kept aligned with V3. General-knowledge generation uses a separate prompt in `prompts/general/` and does not receive policy citations.

| Version | Design change | Reason |
|---|---|---|
| V1 — Baseline | Uses the Milestone 1 helpdesk instruction: answer only from the supplied excerpt, quote the supporting section, acknowledge gaps, and do not guess. | Establish a concise starting point with the central grounding rule. |
| V2 — Improved | Adds category context, structured JSON, explicit evidence checking, refusal for unrelated topics, and missing-information handling. | Make outputs machine-readable and specify behavior when a question is unsupported. |
| V3 — Final | Treats questions, history, and excerpts as untrusted data; adds exact-quote constraints, conflict and currentness handling, multiple-question behavior, and confidence rules. | Address prompt injection and ambiguity while keeping the policy evidence boundary explicit. |

## Executed evaluation

- `test-data/test-cases.json` contains 18 distinct inputs: 10 normal, 6 edge, and 2 invalid cases. It includes greetings, general knowledge, attendance conflict, exam failure, follow-up context, hostel rules and timing, fees, scholarships, missing evidence, mixed and ambiguous requests, and a prompt-injection attempt.
- The runner executed every input with V1, V2, and V3: **54 attempts**. The follow-up test used the actual prior response produced earlier in the same version run as history.
- The recorded run had no `GEMINI_API_KEY`: **30 passed, 0 failed, 24 blocked**. Per prompt version: 10 passed and 8 blocked. The 100% pass rate applies only to the 30 completed local checks; all 24 Gemini-required generation attempts were blocked and excluded from that percentage.
- Zero cases completed with Gemini under all three prompt versions. The current run therefore does not measure prompt quality or support a claim that one version is better.
- Exact per-case inputs, actual outputs, outcomes, and modes are in `test-data/demo-evaluation-results.json` and `test-data/evaluation-results.csv`. The comparison summary is in `test-data/prompt-comparison-log.json`.

To make a comparable live prompt evaluation, configure `GEMINI_API_KEY`, run `python backend/run_evaluation.py`, and verify that the generated summary reports completed Gemini outputs for the same cases across all versions. Keep blocked and failed runs visible; do not treat them as passes.
