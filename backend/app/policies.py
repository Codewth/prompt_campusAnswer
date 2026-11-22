from io import BytesIO
import os
import re
from pathlib import Path
from threading import Lock
import time

from pypdf import PdfReader

from .cloud_store import (
    CloudObjectAlreadyExistsError,
    CloudStoreError,
    download_uploaded_document,
    list_uploaded_documents,
    supabase_is_configured,
    upload_document,
)
from .models import PolicyDocument, PolicySection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = PROJECT_ROOT / "sample-policies"
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "backend" / "documents"
SECTION_PATTERN = re.compile(r"^##\s+Section\s+([^|]+)\|\s*(.+?)\s*$", re.MULTILINE)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_CLOUD_DOCUMENT_BYTES = 25 * 1024 * 1024
CLOUD_DOCUMENT_CACHE_SECONDS = 60
_cloud_documents_lock = Lock()
_cloud_documents_cache: tuple[float, list[PolicyDocument]] | None = None


def _upload_dir() -> Path:
    return Path(os.getenv("CAMPUSANSWER_DOCUMENTS_DIR", "").strip() or DEFAULT_UPLOAD_DIR).expanduser()


def _read_text(path: Path) -> str:
    return _read_content(path.name, path.read_bytes())


def _read_content(filename: str, content: bytes) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    return content.decode("utf-8")


def parse_document(path: Path, fictional: bool) -> PolicyDocument:
    return _parse_document(path.name, _read_text(path), fictional)


def _parse_document(filename: str, raw: str, fictional: bool) -> PolicyDocument:
    lines = raw.splitlines()
    title = next((line.lstrip("# ").strip() for line in lines if line.startswith("# ")), Path(filename).stem)
    matches = list(SECTION_PATTERN.finditer(raw))
    sections: list[PolicySection] = []
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        text = raw[body_start:body_end].strip()
        if text:
            sections.append(
                PolicySection(
                    document=title,
                    section=match.group(1).strip(),
                    title=match.group(2).strip(),
                    text=text,
                    fictional=fictional,
                    collection="demo",
                    source_type="fictional" if fictional else "uploaded",
                )
            )
    return PolicyDocument(
        title=title,
        filename=filename,
        fictional=fictional,
        sections=sections,
        collection="demo",
        source_type="fictional" if fictional else "uploaded",
    )


def _uploaded_cloud_documents() -> list[PolicyDocument]:
    global _cloud_documents_cache
    with _cloud_documents_lock:
        now = time.monotonic()
        if (
            _cloud_documents_cache is not None
            and now - _cloud_documents_cache[0] < CLOUD_DOCUMENT_CACHE_SECONDS
        ):
            return list(_cloud_documents_cache[1])

        objects = list_uploaded_documents()
        if sum(size for _, size in objects) > MAX_CLOUD_DOCUMENT_BYTES:
            raise CloudStoreError("Uploaded policy documents exceed the 25 MB runtime limit.")
        documents = []
        for filename, size in objects:
            if Path(filename).suffix.lower() not in {".txt", ".pdf"}:
                continue
            if size > 5 * 1024 * 1024:
                raise CloudStoreError(f"Uploaded document {filename!r} exceeds the 5 MB limit.")
            content = download_uploaded_document(filename)
            documents.append(_parse_document(filename, _read_content(filename, content), fictional=False))
        _cloud_documents_cache = (now, documents)
        return list(documents)


def _invalidate_cloud_documents_cache() -> None:
    global _cloud_documents_cache
    with _cloud_documents_lock:
        _cloud_documents_cache = None


def list_documents() -> list[PolicyDocument]:
    docs: list[PolicyDocument] = []
    if SAMPLE_DIR.exists():
        for path in sorted(SAMPLE_DIR.iterdir()):
            if path.suffix.lower() in {".txt", ".pdf"}:
                docs.append(parse_document(path, fictional=True))
    if supabase_is_configured():
        docs.extend(_uploaded_cloud_documents())
    else:
        upload_dir = _upload_dir()
        if upload_dir.exists():
            for path in sorted(upload_dir.iterdir()):
                if path.suffix.lower() in {".txt", ".pdf"}:
                    docs.append(parse_document(path, fictional=False))
    return docs


def save_upload(filename: str, content: bytes) -> PolicyDocument:
    safe_name = Path(filename.replace("\\", "/")).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in {".txt", ".pdf"}:
        raise ValueError("Only TXT and text-based PDF documents are supported.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Files must be 5 MB or smaller.")
    document = _parse_document(safe_name, _read_content(safe_name, content), fictional=False)
    if not document.sections:
        raise ValueError("No sections found. Use headings formatted as '## Section 1.2 | Title'.")
    if supabase_is_configured():
        objects = list_uploaded_documents()
        if any(existing_name == safe_name for existing_name, _ in objects):
            raise ValueError("A document with this filename already exists in the library.")
        if sum(size for _, size in objects) + len(content) > MAX_CLOUD_DOCUMENT_BYTES:
            raise ValueError("Cloud document storage is limited to 25 MB for this deployment.")
        content_type = "application/pdf" if suffix == ".pdf" else "text/plain; charset=utf-8"
        try:
            upload_document(safe_name, content, content_type)
        except CloudObjectAlreadyExistsError as error:
            raise ValueError(str(error)) from error
        _invalidate_cloud_documents_cache()
    else:
        upload_dir = _upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        destination = upload_dir / safe_name
        if destination.exists():
            raise ValueError("A document with this filename already exists in the local library.")
        destination.write_bytes(content)
    return document
