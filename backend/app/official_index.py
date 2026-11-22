import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from .models import PolicyDocument, PolicySection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "CampusAnswer_Official_Sources"
CHUNKS_PATH = SOURCE_DIR / "rag_chunks.jsonl"
SOURCES_PATH = SOURCE_DIR / "sources.json"
REPORT_PATH = SOURCE_DIR / "ingestion_report.json"
INDEX_PATH = SOURCE_DIR / "vector-index.sqlite3"
TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}")
STOP_WORDS = {
    "a", "about", "after", "all", "also", "an", "and", "are", "as", "be", "can", "could",
    "does", "for", "from", "how", "in", "is", "it", "me", "my", "of", "on", "or", "please",
    "rule", "rules", "should", "tell", "the", "this", "to", "what", "when", "where", "which",
    "who", "would",
}
SOURCE_CATEGORIES = {
    "attendance": {"academics", "examinations"},
    "exams": {"academics", "examinations"},
    "fees": {"fees"},
    "hostel": {"hostel"},
    "scholarships": {"scholarships"},
    "campus": {"library"},
}


class OfficialIndexUnavailableError(RuntimeError):
    pass


def _tokens(text: str) -> list[str]:
    tokens = []
    for token in TOKEN_PATTERN.findall(text.lower()):
        if token in STOP_WORDS:
            continue
        if token == "makeup":
            tokens.extend(("make", "up"))
        elif token in {"exam", "exams"}:
            tokens.append("examination")
        else:
            tokens.append(token)
    return tokens


def _load_chunks(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Official RAG chunks were not found at {path}. Run the official-source ingestion first.")
    chunks = []
    seen = set()
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON in official chunk file at line {line_number}.") from error
            required = ("id", "document_id", "document_title", "academic_year", "page", "source_url", "text")
            if not isinstance(item, dict) or any(key not in item for key in required):
                raise ValueError(f"Official chunk at line {line_number} is missing required metadata.")
            if item["id"] in seen:
                raise ValueError(f"Duplicate official chunk id at line {line_number}: {item['id']}")
            if not isinstance(item["page"], int) or item["page"] < 1:
                raise ValueError(f"Official chunk at line {line_number} has an invalid page number.")
            if not isinstance(item["text"], str) or not item["text"].strip():
                continue
            seen.add(item["id"])
            chunks.append(item)
    if not chunks:
        raise ValueError("The official chunk file contains no searchable text.")
    return chunks


def build_official_index(chunks_path: Path = CHUNKS_PATH, index_path: Path = INDEX_PATH) -> int:
    chunks = _load_chunks(chunks_path)
    corpus = []
    document_frequencies: Counter[str] = Counter()
    for chunk in chunks:
        terms = _tokens(f"{chunk['document_title']} {chunk['text']}")
        frequencies = Counter(terms)
        corpus.append(frequencies)
        document_frequencies.update(frequencies.keys())

    document_count = len(chunks)
    vectors = []
    for frequencies in corpus:
        weights = {
            term: (1 + math.log(count)) * (math.log((document_count + 1) / (document_frequencies[term] + 1)) + 1)
            for term, count in frequencies.items()
        }
        norm = math.sqrt(sum(weight * weight for weight in weights.values()))
        vectors.append({term: weight / norm for term, weight in weights.items()} if norm else {})

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(index_path) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS official_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                document_title TEXT NOT NULL,
                category TEXT NOT NULL,
                academic_year TEXT NOT NULL,
                page INTEGER NOT NULL,
                source_url TEXT NOT NULL,
                source_page TEXT NOT NULL,
                extraction_method TEXT NOT NULL,
                text TEXT NOT NULL,
                vector_json TEXT NOT NULL
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS official_chunks_document_page ON official_chunks(document_id, page)")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS official_term_stats (
                term TEXT PRIMARY KEY,
                document_frequency INTEGER NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS official_index_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )"""
        )
        with connection:
            connection.execute("DELETE FROM official_chunks")
            connection.execute("DELETE FROM official_term_stats")
            connection.execute("DELETE FROM official_index_meta")
            connection.executemany(
                """INSERT INTO official_chunks (
                    id, document_id, document_title, category, academic_year, page,
                    source_url, source_page, extraction_method, text, vector_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        chunk["id"],
                        chunk["document_id"],
                        chunk["document_title"],
                        chunk.get("category", ""),
                        str(chunk["academic_year"]),
                        chunk["page"],
                        chunk["source_url"],
                        chunk.get("source_page", ""),
                        chunk.get("extraction_method", "embedded_text"),
                        chunk["text"],
                        json.dumps(vector, ensure_ascii=False),
                    )
                    for chunk, vector in zip(chunks, vectors)
                ],
            )
            connection.executemany(
                "INSERT INTO official_term_stats (term, document_frequency) VALUES (?, ?)",
                document_frequencies.items(),
            )
            connection.executemany(
                "INSERT INTO official_index_meta (key, value) VALUES (?, ?)",
                [("documents", str(document_count)), ("method", "sparse_tfidf_cosine_v1")],
            )
    return document_count


def search_official(question: str, category: str, limit: int = 10, index_path: Path = INDEX_PATH) -> list[PolicySection]:
    if not index_path.is_file():
        raise OfficialIndexUnavailableError(
            "The official source index is not available. Run the official-source ingestion and indexing commands."
        )
    query_frequencies = Counter(_tokens(question))
    if not query_frequencies:
        return []

    with sqlite3.connect(index_path) as connection:
        stats = dict(connection.execute("SELECT term, document_frequency FROM official_term_stats"))
        row = connection.execute("SELECT value FROM official_index_meta WHERE key = 'documents'").fetchone()
        if not row:
            raise OfficialIndexUnavailableError("The official source index has no document-count metadata.")
        document_count = int(row[0])
        query_weights = {
            term: (1 + math.log(count)) * (math.log((document_count + 1) / (stats[term] + 1)) + 1)
            for term, count in query_frequencies.items()
            if term in stats
        }
        query_norm = math.sqrt(sum(weight * weight for weight in query_weights.values()))
        if not query_norm:
            return []
        query_vector = {term: weight / query_norm for term, weight in query_weights.items()}
        rows = connection.execute(
            """SELECT id, document_id, document_title, category, academic_year, page,
                      source_url, source_page, extraction_method, text, vector_json
               FROM official_chunks"""
        ).fetchall()

    allowed_categories = SOURCE_CATEGORIES.get(category, set())
    query_term_count = len(query_weights)
    ranked = []
    for row in rows:
        if row[3] not in allowed_categories:
            continue
        vector = json.loads(row[10])
        overlap = set(query_vector).intersection(vector)
        coverage = len(overlap) / query_term_count if query_term_count else 0
        score = sum(weight * vector.get(term, 0.0) for term, weight in query_vector.items())
        if score > 0 and coverage >= 0.3:
            ranked.append((score, row))
    ranked.sort(key=lambda result: result[0], reverse=True)

    matches = []
    for _, row in ranked[:limit]:
        chunk_id, document_id, title, source_category, academic_year, page, source_url, source_page, extraction_method, text, _ = row
        excerpt_id = chunk_id.rsplit("-c", 1)[-1]
        matches.append(
            PolicySection(
                document=title,
                section=f"Page {page}, excerpt {excerpt_id}",
                title=f"Page {page}, excerpt {excerpt_id}",
                text=text,
                fictional=False,
                collection="official",
                source_type="official",
                document_id=document_id,
                academic_year=academic_year,
                source_url=source_url,
                source_page=source_page,
                page=page,
                extraction_method=extraction_method,
            )
        )
    return matches


def list_official_documents(index_path: Path = INDEX_PATH) -> list[PolicyDocument]:
    if not SOURCES_PATH.is_file():
        return []
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    reports = {}
    if REPORT_PATH.is_file():
        reports = {item["id"]: item for item in json.loads(REPORT_PATH.read_text(encoding="utf-8"))}

    indexed_chunks: dict[str, list[tuple]] = defaultdict(list)
    if index_path.is_file():
        with sqlite3.connect(index_path) as connection:
            for row in connection.execute(
                """SELECT document_id, document_title, academic_year, page, source_url,
                          source_page, extraction_method, text
                   FROM official_chunks ORDER BY document_id, page, id"""
            ):
                indexed_chunks[row[0]].append(row)

    documents = []
    for source in sources:
        report = reports.get(source["id"], {})
        rows = indexed_chunks.get(source["id"], [])
        pages = defaultdict(list)
        for row in rows:
            pages[row[3]].append(row)
        sections = []
        for page_number, page_rows in sorted(pages.items()):
            first = page_rows[0]
            sections.append(
                PolicySection(
                    document=source["title"],
                    section=f"Page {page_number}",
                    title=f"Page {page_number}",
                    text="\n".join(row[7] for row in page_rows),
                    fictional=False,
                    collection="official",
                    source_type="official",
                    document_id=source["id"],
                    academic_year=source["academic_year"],
                    source_url=source["url"],
                    source_page=source["source_page"],
                    page=page_number,
                    extraction_method=first[6],
                )
            )
        documents.append(
            PolicyDocument(
                title=source["title"],
                filename=source["file"],
                fictional=False,
                sections=sections,
                collection="official",
                source_type="official",
                academic_year=source["academic_year"],
                source_url=source["url"],
                source_page=source["source_page"],
                category=source.get("category"),
                pages=report.get("pages"),
                indexed_chunks=len(rows),
                extraction_status=report.get("status", "not_ingested"),
            )
        )
    return documents
