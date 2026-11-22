# CampusAnswer official Bennett University sources

The source list records six PDFs linked from Bennett University public pages. It preserves the listed title, academic year or document date, source URL, and source page. Metadata does not establish that a policy is current; check the cited document and year before applying it.

## Ingest and index (Windows PowerShell)

From the repository root, install the Python dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Install Tesseract OCR and make `tesseract.exe` available on `PATH`, or set `TESSERACT_EXE` to its full path. Then download/extract and index:

```powershell
Push-Location CampusAnswer_Official_Sources
..\.venv\Scripts\python.exe .\ingest_official_policies.py --ocr
Pop-Location
.\.venv\Scripts\python.exe backend\index_official_sources.py
```

The ingestion script writes:

- `pdfs\` — downloaded PDFs
- `extracted-text\` — page-marked text, including OCR output where requested
- `rag_chunks.jsonl` — page-aware chunks with title, category, academic year, source URL, and extraction method
- `ingestion_report.json` — download/extraction status, page counts, OCR pages, low-text pages, and file hashes

Review `ingestion_report.json` before indexing. A `needs_ocr` status or remaining low-text page means that page was not indexed; do not infer its contents. OCR text can contain recognition errors, so verify cited wording in the linked original PDF. The PDFs, extracted text, chunk file, report, and SQLite index are local generated data and are ignored by Git.

## Retrieval behavior

The repository did not contain a vector database. CampusAnswer now builds a local SQLite sparse TF-IDF vector index from `rag_chunks.jsonl`; it does not call an embedding API. Official-source chat retrieval is kept separate from fictional demo policies and local demo uploads. Unsupported questions return no citations. When retrieved official attendance excerpts conflict, the response cites each conflicting excerpt without selecting one. Citations show the document title, page, academic year/document date, URL, and retrieved quotation.

Gemini is required for general-knowledge answers and policy responses that need generation. Without a key, those requests return an explicit service-unavailable error; the application does not present deterministic lookup as an AI response. Safe greetings, known local conflicts, and missing-evidence decisions can still be handled without Gemini. With Gemini configured, generated policy answers and quotations must pass the evidence verification checks.

Sources were listed as found on the Bennett University Registrar and Examination pages on 22 November 2026. A listed source page date is not a guarantee of current policy.
