# CampusAnswer — Technical Report

## Abstract

CampusAnswer is a university helpdesk prototype with separate routes for conversation, general AI knowledge, and document-grounded university policy questions. Its policy workflow retrieves from a local collection, sends only retrieved evidence to a selected prompt and Gemini when generation is required, and validates source citations before returning a supported answer. Missing or conflicting policy evidence is not silently resolved.

## Architecture and tools

The React/Vite client provides a public homepage and protected dashboard, chat, policy library, prompt evaluation, and profile pages. Firebase Google sign-in supplies ID tokens; FastAPI verifies tokens and protects profile, chat, document, and upload endpoints. Student details and theme preference are stored by authenticated UID in a local SQLite database. Uploads require a server-side administrator allowlist.

The Python/FastAPI backend uses Pydantic response models and three evidence paths: predefined safe replies for greetings; Gemini generation for general questions; and category-aware retrieval for university policy. Official PDFs are ingested into a local sparse SQLite index that preserves document title, academic year/date, source URL, page, and extraction metadata. Fictional sample policies and local uploads remain separate from that official index.

## Prompt design and grounding

V1 reproduces the Milestone 1 baseline. V2 adds classification context and structured evidence handling. V3 strengthens untrusted-input handling, direct evidence constraints, exact quotations, currentness, conflicts, ambiguity, and confidence. The three policy prompts are separate files; general-knowledge output uses its own prompt and carries no policy citations.

For generated policy responses, the backend accepts a supported answer only when the cited document and section match retrieved evidence, the source quote is an exact substring, and the answer is itself contained in a verified quote. The response includes source metadata such as page and URL where indexed. Local source conflicts, absent evidence, and missing exact requested details may be returned without model generation. A Gemini-required request with no usable Gemini configuration returns an explicit service error.

## Testing and measured output

The evaluation dataset contains 18 distinct inputs: 10 normal, 6 edge, and 2 invalid cases. It includes general conversation and knowledge, attendance conflict, exam failure, a policy follow-up using the actual prior response, hostel rules and timing, fees, scholarships, absent evidence, conflicting fictional hostel documents, mixed/ambiguous questions, currentness, and prompt injection. Each input is run under V1, V2, and V3.

The recorded run has no `GEMINI_API_KEY`. It made **54 attempts**: **30 passed, 0 failed, and 24 blocked** because Gemini generation was unavailable. Each prompt version had 10 passed local checks and 8 blocked runs. The 100% pass rate applies only to the 30 completed local checks; **zero cases completed with Gemini for all three prompt versions**, so no prompt-quality comparison was measured. Results are saved in JSON and CSV, with a separate comparison summary.

The backend regression suite passed 27 tests. Browser checks against the running local app verified the public root, protected dashboard after refresh, chat greeting, the explicit Gemini-unavailable error, official attendance conflict citations, policy-library rendering, and evaluation dashboard output. This did not test a fresh registration or a live Gemini response.

## Limitations and responsible use

Fictional samples are not Bennett University guidance. The official index has a real source-date/currentness limitation: for example, indexed attendance documents state 70% and 75% requirements in different source years, and the assistant reports a conflict rather than selecting one. A cited document's date does not establish that it is currently authoritative. Retrieval uses a local sparse lexical index, not production-scale semantic search. Text extraction can have OCR artifacts; source PDF pages need human review. Conflict detection is limited and may miss conflicts that do not match the implemented claim patterns. Strict answer-in-quote verification can reject valid paraphrases.

The current evaluation did not test live Gemini responses because no key was configured. Backend unit tests use mocked Firebase token verification; they do not prove a live OAuth sign-in. Local SQLite and file uploads are not shared durable production storage. The prototype needs deployment hardening, source freshness review, access controls, monitoring, and live service configuration before public use.

## Reproducibility

Install, configure, start, test, and run evaluation with the commands in `README.md`. Store API credentials only in an ignored local `.env`; `.env.example` contains placeholders. The seven-section report scaffold, contribution placeholders, prompt iteration log, and five Mermaid diagrams are in `docs/`.
