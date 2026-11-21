# Prompt iteration log

The prompt files live separately in `prompts/v1/`, `prompts/v2/`, `prompts/v3/`, and `prompts/final/`. The iterations describe design intent; they do not claim a measured improvement without a controlled, comparable live-model experiment.

| Version | Design change | Reason |
|---|---|---|
| V1 — Baseline | Uses the supplied Milestone 1 helpdesk prompt: answer only from the excerpt, quote the section, acknowledge gaps, and do not guess. | Establish a concise starting point with the central grounding rule. |
| V2 — Improved | Adds category classification, JSON output fields, direct evidence checking, refusal for unrelated topics, and explicit missing-information handling. | Make outputs machine-readable and clarify what to do when a question is unsupported. |
| V3 — Final | Treats questions and excerpts as untrusted data; handles multiple questions, conflicts, unrelated queries, exact quotations, and conservative confidence rules. | Address common prompt injection and ambiguity cases, and make the result contract more consistent. |
| Final workflow prompt | Preserves V3 constraints in a standalone final prompt used by the Gemini workflow for the final prompt variant. | Keep an easy-to-reference final prompt separate from version experiment files. |

## Evaluation notes

- The deterministic evaluator executes all 13 identical test inputs against V1, V2, and V3 and writes each actual result to `test-data/demo-evaluation-results.json`.
- With no API key, test outcomes are `deterministic_demo`, not model responses. Prompt files do not affect deterministic lookup outcomes.
- The recorded deterministic run passed 13/13 cases per version (39/39 total). Because the lookup branch does not invoke or vary model prompting, those results verify workflow behavior only and do not compare prompt quality.
- To compare live prompt versions, execute each case under each prompt with the same model, settings, and evidence, preserve each run, and report only measured results. No comparative claim is made here.
