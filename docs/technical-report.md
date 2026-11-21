# CampusAnswer — Technical Report

## Abstract

CampusAnswer is a student-project prototype for university policy question answering. Its primary design goal is not fluent generation alone: each supported answer must be traceable to supplied policy text, and missing or contradictory evidence must remain visible. The current workspace includes a responsive web client, Python API, local fictional policy library, three prompt iterations, and an executed evaluation harness.

## Architecture and tools

The React/Vite client provides five views: project overview, policy chat, policy library, prompt evaluation, and project information. The FastAPI backend exposes health, document listing, upload, and question-answer endpoints. Pydantic models define request and response shape. Policies are read from local TXT or text-based PDF files; sample files are clearly labeled fictional, while local uploads are stored separately and excluded from version control.

The answer pipeline classifies a question into attendance, exams, fees, hostel, or out-of-scope; applies lightweight lexical retrieval over document sections; and either returns a deterministic local response or sends the evidence and prompt to a configured Gemini model. Gemini is optional and its model name is controlled by `GEMINI_MODEL`. No credentials are embedded in source. The UI distinguishes a Gemini response from deterministic demo lookup.

## Prompt design and grounding

V1 reproduces the Milestone 1 baseline instruction. V2 adds category classification, structured JSON, explicit evidence checks, refusal, and missing-information behavior. V3 adds stronger source-only constraints, quote verification, conflict and multi-question handling, unrelated-question refusal, injection resistance, and conservative confidence rules. Their exact text is stored in separate prompt files.

The model is given only retrieved excerpts and the user question. A response is accepted as supported only if its document and section correspond to retrieved evidence, its quote is an exact substring of the cited section, and the answer itself occurs verbatim within a verified quote. This intentionally conservative check may reject useful paraphrases but reduces unsupported claims. Conflicting same-title sections are surfaced without choosing a winner. Deterministic mode quotes the selected section directly and is not represented as a live model answer.

## Testing and measured output

The test set contains 13 distinct inputs covering core supported topics, absent information, unrelated input, ambiguous/exception requests, multiple questions, an instruction-injection attempt, and an intentionally contradictory hostel policy amendment. Each input is executed under V1, V2, and V3 with matching settings. Backend unit tests exercise classification, exact citation text, unsupported responses, multi-question handling, and source-instruction resilience.

**Measured run:** `deterministic_demo`, executed `2026-11-21T20:53:50Z`: **39/39 passed (100.0%)**; each of V1, V2, and V3 passed 13/13 checks. The JSON file contains each output and timestamp. Since prompt text does not affect the deterministic lookup branch, these checks are not Gemini response quality measurements and do not establish that one prompt version outperforms another. A controlled comparison requires running identical cases and settings under each live prompt/model version.

## Limitations and responsible use

All included sample policies are invented for demonstration and are not official Bennett University guidance. Lexical matching is a small local prototype rather than semantic or production search. Conflict detection currently flags differing text under matching section titles; subtler conflicts can be missed. Strict answer-in-quote verification sacrifices paraphrase flexibility. The upload route is unauthenticated and local-only, so the prototype is unsuitable for sensitive documents or public deployment without access control, storage protections, audit logging, and broader policy validation.

## Reproducibility

Install dependencies and run the API, frontend, tests, and evaluator using the commands in `README.md`. Store API credentials only in an ignored local `.env`. The report scaffold and contribution table are in `docs/milestone2-report.md`; project-specific submission links and verified individual contributions remain placeholders for the team.
