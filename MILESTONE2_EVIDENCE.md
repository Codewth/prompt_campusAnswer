# CampusAnswer — Milestone 2 Evidence

This report distinguishes executed checks from configuration-dependent work that was not verified. Fictional sample policy text is demonstration content only and is not Bennett University guidance.

## Verified feature audit

| Area | Evidence from this workspace |
|---|---|
| Public and protected navigation | Browser opened `/` and rendered the public homepage; `/about` rendered the AI engine, architecture, feature grid, and interactive steps. After authentication hydration, **Get started** linked to `/dashboard`. A signed-in `/dashboard` remained on that route after a browser refresh. |
| Authentication and profile | The browser session showed the signed-in Google account, sidebar menu, and protected workspace routes. Backend regression tests cover unauthenticated API rejection, per-UID profile persistence/isolation, validation, and logout revocation. A prior browser check confirmed profile/theme persistence. Fresh registration and browser sign-out were not performed during this audit. |
| Hybrid chat | Browser sent “Hello” and received the **General conversation** label. “What is Python?” returned the explicit Gemini configuration error with HTTP 503; no AI answer was fabricated. |
| Official-source RAG and citations | Browser attendance query returned **Policy information unavailable** with two source cards, page numbers, academic-year/date metadata, quotes, and official PDF links. The indexed sources visibly state different 75% and 70% figures; the answer does not select one. |
| Documents | Browser loaded the protected policy library and rendered official-source and fictional-sample labels. Backend tests verify official index retrieval and preservation of title, academic year, source URL, page, and extraction method. Backend tests also verify that only allowlisted administrators can upload; a browser upload was not performed. |
| Prompt evaluation | Browser loaded the protected evaluation dashboard and displayed 18 V3 cases and the Gemini-unavailable status. Results are generated from the runner, not hand-entered. |
| Prompt assets and documentation | V1, V2, V3, and final prompt files exist; the final prompt is aligned to V3. Five Mermaid workflow/architecture diagrams and the seven-section report scaffold are present. |
| Build and API health | Backend health endpoint returned HTTP 200. Frontend production build completed successfully. Backend pytest suite passed 27 tests. |

## Executed evaluation results

Command:

```powershell
.\.venv\Scripts\python.exe backend\run_evaluation.py
```

The runner executed **18 distinct inputs × 3 prompt versions = 54 attempts** at **2026-11-22 11:07 UTC**. The test mix is 10 normal, 6 edge, and 2 invalid inputs. It includes greetings, Python and RAG general-knowledge questions, official attendance conflict, exam failure, a follow-up that reuses the actual preceding response from that prompt run, prime minister, hostel policy and missing exact timing, fee deadline, scholarship, missing sample-policy evidence, a fictional hostel conflict, ambiguous and mixed questions, current-policy uncertainty, and prompt injection.

| Prompt | Attempts | Passed | Failed | Blocked | Pass rate among evaluable runs |
|---|---:|---:|---:|---:|---:|
| V1 | 18 | 10 | 0 | 8 | 100% (10/10) |
| V2 | 18 | 10 | 0 | 8 | 100% (10/10) |
| V3 | 18 | 10 | 0 | 8 | 100% (10/10) |
| **Total** | **54** | **30** | **0** | **24** | **100% (30/30)** |

`GEMINI_API_KEY` was not configured for this run. All 24 generation-dependent attempts were recorded as **blocked** and excluded from the pass-rate denominator. **Zero inputs completed with Gemini under all three versions.** Therefore these results validate the completed deterministic routing, conflict, clarification, and missing-evidence checks only; they do not measure Gemini answer quality or show that one prompt is better.

Generated artifacts:

- `test-data/demo-evaluation-results.json` — complete expected and actual output per prompt run.
- `test-data/evaluation-results.csv` — spreadsheet-friendly case results.
- `test-data/prompt-comparison-log.json` — version summaries and comparability status.
- `frontend/public/demo-evaluation-results.json` — dashboard copy written by the same runner.

## Tests and browser checks

Executed commands and results:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
# 27 passed, 1 third-party deprecation warning

cd frontend
npm.cmd run build
# Vite production build succeeded

Invoke-WebRequest http://localhost:8000/api/health
# HTTP 200: {"status":"ok"}
```

Browser checks were performed against the running local app at `http://localhost:5175`: public homepage at `/`; protected dashboard refresh; chat greeting; general-knowledge request returning the expected `GEMINI_API_KEY` service error (503); official attendance conflict with two citations and PDF links; policy-library load; and evaluation dashboard load with 18 cases. The visible 503 was the expected no-key response, not a frontend crash. No live Gemini response, new account registration, or logout flow was exercised in this browser session.

## Limitations and unresolved risks

- Live Gemini generation and a comparative V1/V2/V3 prompt evaluation remain unverified until a valid API key is configured and the runner records completed model responses.
- Official-source ingestion contains dated documents and OCR artifacts. Source dates do not prove a rule is current; the attendance documents currently conflict. Review extracted text against original PDFs and have an authorized university source owner confirm policy currency before relying on or publishing answers.
- Retrieval is local sparse lexical retrieval, not a production semantic/vector service. Conflict detection is limited and can miss conflicts outside implemented checks. Citation verification is deliberately strict and can reject paraphrases.
- Backend auth tests stub Firebase token verification; live login was present in the browser, but fresh registration, logout/revocation, and administrator upload were not tested in this run.
- Local development uses SQLite and local file uploads. Free production configuration now uses Supabase for profile/session persistence and private uploaded-document storage; Render is configured for its Free instance without a disk. These cloud paths are covered by mocked regression tests but still require a configured Supabase project and live verification.
- Production still needs provider-managed secrets, explicit CORS/Firebase domains, upload controls/scanning, rate limits, monitoring, backups, and a source-update owner.
- No production deployment was run.

## Commands to reproduce locally

From the repository root in PowerShell:

```powershell
# Backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload

# Frontend, in another terminal
cd frontend
npm.cmd run dev
# http://localhost:5175

# Backend tests
cd ..
.\.venv\Scripts\python.exe -m pytest backend\tests -q

# Frontend production build
cd frontend
npm.cmd run build

# Generate JSON, CSV, comparison log, and dashboard data
cd ..
.\.venv\Scripts\python.exe backend\run_evaluation.py
```

For general answers and Gemini-generated policy answers, create a local `.env` from `.env.example`, configure `GEMINI_API_KEY` and a model available to the Google AI account, then restart the backend. Do not commit the `.env` file.

## Remaining submission work

- Fill **Assigned Team ID**, **Batch**, and **Faculty name** in `docs/milestone2-report.md`.
- Add the final repository URL, deployed prototype URL (if applicable), and demo reel URL.
- Complete the team-contribution table only with member-confirmed tasks and evidence.
- Configure and verify Gemini; rerun the identical test suite for all prompt versions and include the actual live outputs and comparison only if all statuses are recorded honestly.
- Have the team review official-source extraction, source dates, and the contradictory attendance evidence.
- Complete a deployment review and test fresh sign-in, registration, logout/revocation, and protected routes in the target hosted environment.
