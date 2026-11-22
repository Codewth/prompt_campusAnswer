# CampusAnswer

**CampusAnswer: A Document-Grounded Prompt Workflow for University Policy Q&A**  
Team GroundTruth · Problem C1 · SCSE4041 — Prompt Engineering · Milestone 2

> **Demonstration project only.** The policies in `sample-policies/` are fictional examples for software and prompt-workflow testing. They are **not** Bennett University policies. Official-source PDFs are a separate indexed collection and their dates do not prove current validity.

CampusAnswer is a responsive hybrid assistant. Safe greetings use predefined replies; general questions use Gemini; university-policy questions retrieve from the selected local document collection and use Gemini only when generation is needed. The backend verifies policy citations against retrieved text. Local conflict, clarification, and evidence-absence responses can be returned without Gemini. If Gemini is not configured or unavailable for a response that needs generation, the API reports an error instead of presenting deterministic lookup as an AI answer.

## Project structure

```text
frontend/                 React + Vite + Tailwind dashboard with Firebase Google sign-in
backend/app/              FastAPI API, Firebase token checks, official/demo retrieval, and hybrid answer workflow
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
- Firebase project with Google sign-in enabled (required for app access)
- Gemini API key for general-knowledge answers and policy responses requiring generation; safe greetings and local policy conflict/uncertainty checks do not need it

## Install

From the project root, in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

cd frontend
npm.cmd install
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
npm.cmd run dev
```

Open <http://localhost:5175>. Port 5174 is reserved for the separate CampusFind app in this development environment. The frontend expects the API at `http://localhost:8000`.

## Google sign-in and Firebase setup

CampusAnswer requires Google sign-in before accessing policy questions or documents. The backend verifies Firebase ID tokens; the browser never gets Firebase Admin credentials.

1. In the [Firebase Console](https://console.firebase.google.com/), create/select a project and add a Web app.
2. In **Authentication → Sign-in method**, enable **Google**. Add `localhost` to **Authentication → Settings → Authorized domains** for local testing.
3. Copy the root `.env.example` to `.env`. Fill the `VITE_FIREBASE_*` values from the Web app config and set `FIREBASE_PROJECT_ID`.
4. For the basic local demo, a Firebase Admin key is optional: the backend verifies Firebase ID-token signatures with Google's public signing keys and the configured project ID. To enable Firebase-wide refresh-token revocation checks, store a Firebase Admin service-account key **outside Git** and set `FIREBASE_SERVICE_ACCOUNT_PATH` (or `GOOGLE_APPLICATION_CREDENTIALS`) to its absolute local path.
5. Set `FIREBASE_ADMIN_EMAILS` to a comma-separated allowlist of administrator email addresses. Only these verified accounts can upload policy files; other signed-in users can ask questions and read documents.
6. Restart both the API and Vite after editing `.env`.

Never commit `.env`, service-account JSON, private keys, or credentials. Firebase Web app configuration is injected into the frontend build; restrict the Firebase API key to the appropriate APIs and authorized domains in Google Cloud. If Firebase is not configured, the application displays a setup screen and protected API routes fail closed.

**Authentication flow:** Firebase Google popup sign-in → Firebase ID token → `Authorization: Bearer …` → signature, project, time, and session verification → protected FastAPI endpoint. Public routes are `/`, `/about`, `/login`, and `/register`; `/dashboard`, `/chat`, `/documents`, `/evaluation`, and `/profile` require a verified account. Unauthenticated protected-route visits return to `/login` with the original destination preserved. `POST /api/auth/logout` revokes the active ID token in the local SQLite session ledger; if Firebase Admin credentials are configured, it also revokes Firebase refresh tokens. `GET /api/auth/me`, `GET /api/profile`, `PUT /api/profile`, `PATCH /api/profile/settings`, `GET /api/documents`, and `POST /api/ask` require a verified account. `POST /api/documents/upload` additionally requires an email in `FIREBASE_ADMIN_EMAILS`.

### Student profile and account settings

The authenticated sidebar account menu links to **My Profile**, **Account Settings**, and **Sign Out**. The profile page uses the signed-in Firebase account for the read-only email and Google photo/name fallback; missing student details are displayed as **Not provided** and are never guessed. Editable name, university, enrollment number, course, specialization, academic year, semester, and batch values are stored by verified Firebase UID in the local SQLite `student_profiles` table. The table shares `backend/auth-sessions.sqlite` with the local session ledger by default; `CAMPUSANSWER_PROFILE_DATABASE` can override its path. Theme preference is stored in the same row and restored after sign-in.

Without Firebase Admin credentials, the backend can block the ID token used at logout but cannot revoke Firebase refresh tokens on other devices. The local session ledger is application-local and is not shared across multiple backend deployments. For deployment, configure Firebase Admin credentials and use a shared durable session/revocation store.

The backend tests stub only the token verifier to exercise route authorization; they do not represent a live Firebase sign-in test. Complete one sign-in in a configured Firebase project to verify the real OAuth setup.

## Gemini configuration

General knowledge and evidence-backed answer generation require Gemini. Without a configured key, those requests return a clear service-unavailable error; the application does not pretend a deterministic result was generated by AI. Predefined greetings, some local policy conflict responses, and explicit missing-evidence responses remain available without a key.

1. Copy `.env.example` to `.env` at the project root.
2. Set `GEMINI_API_KEY` in `.env`; do not commit `.env` or paste a key into source code.
3. Optionally set `GEMINI_MODEL` to a model available to your API account. The default is `gemini-3.8-flash`, listed as a stable model in the [Gemini API model catalog](https://ai.google.dev/gemini-api/docs/models) (checked against the current catalog).
4. Restart the backend. Gemini errors are reported by the API; they do not silently turn into demo answers.

The Gemini policy workflow passes the retrieved document excerpts, question, relevant history, and selected prompt to the model. The response is parsed as JSON. A supported response is accepted only if its document and section match retrieved evidence, its quotation is an exact substring of that evidence, and its answer is itself contained verbatim in a verified quote. Otherwise, the API returns an uncertainty response. This conservative policy avoids unsupported paraphrases. General-knowledge answers use a separate prompt and carry no policy citations.

## Documents

- The sample documents are plain text and intentionally labeled fictional in the library.
- Allowlisted administrators can upload TXT or text-based PDF files; local files are stored under `backend/documents/` (ignored by Git) and displayed as **LOCAL UPLOAD**. Production uploads use the private Supabase bucket described below.
- For a TXT document, format sections as:

  ```text
  # Document title
  ## Section 1.2 | Section title
  The exact section wording goes here.
  ```

- Maximum upload size is 5 MB. Reusing an existing filename is rejected rather than overwritten.
- The free hosted configuration caps uploaded documents at 100 files and 25 MB total to bound memory use; parsed policy text is cached in-process for one minute.
- Uploads require a verified Firebase account whose email is listed in `FIREBASE_ADMIN_EMAILS`. Only upload documents you are authorized to use.
- For reproducible tests, the bundled fictional samples include a deliberate contradictory hostel amendment.

## Official Bennett sources

The optional `CampusAnswer_Official_Sources/` package keeps six public-source PDFs separate from fictional samples and local uploads. Follow its README to download, extract, OCR when needed, and build the local SQLite sparse TF-IDF index. The index preserves title, academic year or document date, source URL, page, and extraction method. It is local lexical retrieval, not an embedding database.

The official collection is selected by default in chat. An attendance question that retrieves both the 70% SCSET rules excerpt and the 75% 2024-25 Examination Manual excerpt returns a conflict and cites both; it does not select one as authoritative. Other unsupported questions do not receive fabricated citations. A cited source date does not establish that the policy is still in force, and OCR quotations should be checked against the linked PDF page.

## Testing and evaluation

Run the backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Execute all input cases against V1, V2, and V3 and write actual results:

```powershell
.\.venv\Scripts\python.exe backend\run_evaluation.py
```

The runner executes 18 distinct inputs (including edge, injection, missing-evidence, ambiguous, mixed-query, fee, hostel, and scholarship cases) under each prompt version. It writes the actual expected/output records to `test-data/demo-evaluation-results.json`, a tabular export to `test-data/evaluation-results.csv`, a prompt comparison summary to `test-data/prompt-comparison-log.json`, and mirrors the dashboard JSON to `frontend/public/`. Gemini-required errors are recorded as **blocked**, not passes or ordinary model failures; blocked runs are excluded from pass percentages. V1, V2, and V3 use identical inputs and the same configured model/settings.

The checked-in output in this workspace records **54 attempts**: **30 passed, 0 failed, and 24 blocked** because `GEMINI_API_KEY` was not configured. Each version had 10 passed local checks and 8 blocked generation cases. The 100% pass rate is among the 30 evaluable local checks only; it is **not** a Gemini quality result. No input completed with Gemini under all three prompts, so prompt effectiveness has not been compared. Rerun the script after configuring Gemini to capture live outputs.

## Prompt versions

- `prompts/v1/prompt.txt` — required Milestone 1 baseline.
- `prompts/v2/prompt.txt` — classification, evidence, structured output, uncertainty, and refusal constraints.
- `prompts/v3/prompt.txt` — grounding, exact quote, conflict, unrelated/multiple questions, injection handling, JSON, and confidence rules.
- `prompts/final/prompt.txt` — final production-oriented workflow prompt.

`docs/prompt-iteration-log.md` records design changes and the actual evaluation limitations without claiming comparative effectiveness absent comparable live-model outputs.

## Milestone 2 documentation

- Seven-section report scaffold: `docs/milestone2-report.md`
- Concise technical report: `docs/technical-report.md`
- Prompt iteration log: `docs/prompt-iteration-log.md`
- Mermaid diagrams: `docs/diagrams/`
- Verified run evidence and submission checklist: `MILESTONE2_EVIDENCE.md`
- Team contribution table is intentionally blank pending verified task and evidence records.

## Team

| Name | Student ID | Role |
|---|---|---|
| Devansh Mishra | S24CSEU1328 | Team Leader |
| Pranav Agrawal | S24CSEU1336 | Team Member |
| Ansh Sharma | S24CSEU1332 | Team Member |
| Nirnay Pratap Singh | S24CSEU1368 | Team Member |

Individual contributions are not inferred. Fill the placeholders in `docs/milestone2-report.md` from verified evidence.

## Render and Vercel deployment

Deployment configuration is included but does not contain credentials:

- `render.yaml` defines a Docker FastAPI service on Render's **Free** instance type. It deliberately has no Render disk or paid database. Render Free filesystems are ephemeral, so the app requires Supabase configuration before its health check succeeds.
- Create a Supabase **Free** project and run [`backend/migrations/001_supabase_free_storage.sql`](./backend/migrations/001_supabase_free_storage.sql) in its SQL Editor. This creates private profile/session tables and the private policy-document bucket. Profiles and revoked-session hashes use Supabase PostgREST; uploaded TXT/PDF documents use Supabase Storage. Keep the service-role key server-side only.
- The official PDFs, extracted chunks, and sparse TF-IDF index are rebuilt into the Docker image by `Dockerfile`; they are not stored on Render's temporary filesystem. Check the Render build log and ingestion report for extraction failures or pages still needing OCR.
- `frontend/vercel.json` provides SPA fallback rewrites so direct React Router URLs can refresh. In Vercel, import the GitHub repository and set **Root Directory** to `frontend`; use `npm run build` and `dist`.

Configure these values in the providers' environment-variable/secret settings, not in Git or chat:

- **Render:** set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `FIREBASE_PROJECT_ID`, `GEMINI_API_KEY`, `FIREBASE_ADMIN_EMAILS`, and `CAMPUSANSWER_CORS_ORIGINS` to the exact production Vercel origin (no wildcard). Keep `CAMPUSANSWER_REQUIRE_CLOUD_STORAGE=true` and `SUPABASE_STORAGE_BUCKET=campusanswer-documents`. Render Blueprint prompts for values marked `sync: false`.
- **Vercel:** set `VITE_API_URL` to the Render service origin, plus the `VITE_FIREBASE_*` web configuration values from Firebase.
- **Firebase:** add the Vercel production domain under Authentication → Authorized domains, enable Google sign-in, and restrict the Web API key to the required Firebase APIs and domains.

Use only free plans and do not enable paid add-ons or billing. Current free-tier limits include Render's spin-down after 15 minutes idle and 750 instance hours/month, Supabase's 500 MB database and 1 GB Storage quotas, and Supabase project pausing after one week of inactivity. A paused Supabase Free project must be resumed before requests can use it; its data is not kept on Render's ephemeral filesystem. Vercel Hobby and Gemini API quotas also apply. Monitor each provider's current quota pages; exceeding or changing free-tier limits may suspend service or require manual action.

Preview Vercel domains are not automatically allowed by production CORS. After provider setup, test health, Google sign-in, profile persistence, upload authorization, Gemini, RAG citations, and direct-route refresh on the deployed domains. No live provider deployment is claimed until these checks pass.

## Limitations

- Sample policies are fictional and not official Bennett University guidance.
- Fictional-sample retrieval uses lightweight lexical matching; official-source retrieval uses a local sparse TF-IDF index. Neither is a production semantic retriever.
- Gemini was not configured for the recorded evaluation. Live general-knowledge generation and generated policy responses were therefore not verified in that run.
- Contradiction detection is deliberately narrow (same section title with differing text); it is not a comprehensive policy conflict resolver.
- Quotation and answer checks are conservative and may decline a valid paraphrase.
- Uploads require a verified account on the server-side administrator allowlist. Production uploads use a private Supabase Storage bucket; local development can use `CAMPUSANSWER_DOCUMENTS_DIR`. This prototype is not suitable for sensitive documents without further storage protections, audit logging, and policy validation.
- Evaluation results are specific to their recorded run and mode. Deterministic demo outcomes are not Gemini model quality measurements.
