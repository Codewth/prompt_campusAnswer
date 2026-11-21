# CampusAnswer

**CampusAnswer: A Document-Grounded Prompt Workflow for University Policy Q&A**  
Team GroundTruth · Problem C1 · SCSE4041 — Prompt Engineering · Milestone 2

> **Demonstration project only.** The policies in `sample-policies/` are fictional examples for software and prompt-workflow testing. They are **not** Bennett University policies. Do not rely on this prototype for actual university requirements.

CampusAnswer is a responsive university helpdesk prototype. It retrieves local policy sections, answers only from supplied evidence, verifies citations, and acknowledges missing or conflicting information. Gemini is optional; without a key, responses use deterministic document lookup and are labeled **DEMO LOOKUP** (not live AI).

## Project structure

```text
frontend/                 React + Vite + Tailwind dashboard
backend/app/              FastAPI API, policy parser, retrieval, and answer workflow
backend/tests/            Focused backend tests
backend/run_evaluation.py Execute test-data/test-cases.json and save results
prompts/v1..v3/           Baseline, improved, and final prompt iterations
prompts/final/            Prompt used when a non-versioned final prompt is needed
sample-policies/          Clearly fictional local demonstration documents
test-data/                Test inputs and generated evaluation results
docs/                     Milestone report, technical report, prompt log, diagrams
.env.example              Optional Gemini and frontend configuration template
```

## Requirements

- Python 3.10 or later
- Node.js 20 or later and npm
- Gemini API key only for live Gemini responses; deterministic demo mode needs no credentials

## Install

From the project root, in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

cd frontend
npm install
cd ..
```

If PowerShell prevents activating scripts, you can invoke the venv interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

## Run locally

Open two terminals at the project root.

**Terminal 1 — API**

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

API health: <http://localhost:8000/api/health> · Interactive API docs: <http://localhost:8000/docs>

**Terminal 2 — frontend**

```powershell
cd frontend
npm run dev
```

Open <http://localhost:5174>. The frontend expects the API at `http://localhost:8000`.

## Gemini configuration

By default, the application uses deterministic retrieval and clearly labels each response **DEMO LOOKUP**. To enable Gemini:

1. Copy `.env.example` to `.env` at the project root.
2. Set `GEMINI_API_KEY` in `.env`; do not commit `.env` or paste a key into source code.
3. Optionally set `GEMINI_MODEL` to a model available to your API account. The default is `gemini-3.8-flash`, listed as a stable model in the [Gemini API model catalog](https://ai.google.dev/gemini-api/docs/models) (checked November 2026).
4. Restart the backend. Gemini errors are reported by the API; they do not silently turn into demo answers.

The Gemini workflow passes only the retrieved document excerpts, question, and prompt to the model. The response is parsed as JSON. A supported response is accepted only if its document and section match retrieved evidence, its quotation is an exact substring of that evidence, and its answer is itself contained verbatim in a verified quote. Otherwise, the API returns an uncertainty response. This conservative policy avoids unsupported paraphrases.

## Documents

- The sample documents are plain text and intentionally labeled fictional in the library.
- Upload TXT or text-based PDF files through the local demo interface; files are stored under `backend/documents/` (ignored by Git) and displayed as **LOCAL UPLOAD**.
- For a TXT document, format sections as:

  ```text
  # Document title
  ## Section 1.2 | Section title
  The exact section wording goes here.
  ```

- Maximum upload size is 5 MB. Reusing an existing filename is rejected rather than overwritten.
- This is a local demonstration uploader, not an authenticated production administrator workflow. Only upload documents you are authorized to use.
- For reproducible tests, the bundled fictional samples include a deliberate contradictory hostel amendment.

## Testing and evaluation

Run the backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Execute all input cases and write actual results:

```powershell
.\.venv\Scripts\python.exe backend\run_evaluation.py
```

Output is saved to `test-data/demo-evaluation-results.json`, including each expected/actual result, pass/fail, prompt version, mode, run timestamp, and summary. Each input is executed once for each of V1, V2, and V3 with the same configured model settings. The evaluation runner uses the configured backend; with no Gemini key it reports `deterministic_demo`, and with a key it reports `live_gemini`. A deterministic run does not establish that one prompt version performs better than another.

The currently recorded run is deterministic demo mode: **39/39 checks passed (100.0%)**, with **13/13** for each version. These results validate category, status, and citation-presence expectations in the local lookup path; they are not live-model quality measurements and do not show that one prompt is better.

To show the current executed result in the dashboard, copy the generated file into Vite's public directory:

```powershell
Copy-Item test-data\demo-evaluation-results.json frontend\public\demo-evaluation-results.json
```

Rerun the evaluation and copy again to refresh the dashboard results.

## Prompt versions

- `prompts/v1/prompt.txt` — required Milestone 1 baseline.
- `prompts/v2/prompt.txt` — classification, evidence, structured output, uncertainty, and refusal constraints.
- `prompts/v3/prompt.txt` — grounding, exact quote, conflict, unrelated/multiple questions, injection handling, JSON, and confidence rules.
- `prompts/final/prompt.txt` — final production-oriented workflow prompt.

`docs/prompt-iteration-log.md` records design changes without claiming comparative effectiveness absent a controlled live-model evaluation.

## Milestone 2 documentation

- Seven-section report scaffold: `docs/milestone2-report.md`
- Concise technical report: `docs/technical-report.md`
- Prompt iteration log: `docs/prompt-iteration-log.md`
- Mermaid diagrams: `docs/diagrams/`
- Team contribution table is intentionally blank pending verified task and evidence records.

## Team

| Name | Student ID | Role |
|---|---|---|
| Devansh Mishra | S24CSEU1328 | Team Leader |
| Pranav Agrawal | S24CSEU1336 | Team Member |
| Ansh Sharma | S24CSEU1332 | Team Member |
| Nirnay Pratap Singh | S24CSEU1368 | Team Member |

Individual contributions are not inferred. Fill the placeholders in `docs/milestone2-report.md` from verified evidence.

## Limitations

- Sample policies are fictional and not official Bennett University guidance.
- Local document retrieval uses lightweight lexical matching, not a production search index or semantic retriever.
- Contradiction detection is deliberately narrow (same section title with differing text); it is not a comprehensive policy conflict resolver.
- Quotation and answer checks are conservative and may decline a valid paraphrase.
- Uploads are unauthenticated and local-only; this prototype is not suitable for deployment with sensitive documents.
- Evaluation results are specific to their recorded run and mode. Deterministic demo outcomes are not Gemini model quality measurements.
