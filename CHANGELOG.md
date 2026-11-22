# Changelog

## 1.0.0 — CampusAnswer Milestone 2 prototype

- Added Firebase Google sign-in, server-side ID-token verification, protected policy APIs, and administrator email allowlisting for uploads.
- Added Firebase configuration and local service-account ignore rules, and pinned a patched gRPC dependency override for the Firebase web SDK.
- Added the React/Vite responsive dashboard, policy library, chat, evaluation view, and project overview.
- Added the FastAPI hybrid conversation, general-knowledge, and document-grounded policy workflow with explicit Gemini-unavailable errors.
- Added separate fictional samples and official-source retrieval, with citation verification and source metadata.
- Added 18 evaluation inputs, three versioned policy prompts, JSON/CSV outputs, and a prompt-comparison summary that distinguishes blocked Gemini runs.
- Added citation verification and explicit handling for missing evidence, out-of-scope questions, multi-question requests, and contradictory sample sections.
- Added authenticated student profiles, per-user SQLite persistence, editable academic details, and saved light/dark theme preferences.
- Updated Milestone 2 reports and Mermaid diagrams to describe the actual hybrid routing and recorded evaluation limitations.
