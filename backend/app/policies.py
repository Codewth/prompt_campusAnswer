import os
import re
from pathlib import Path

from pypdf import PdfReader

from .models import PolicyDocument, PolicySection


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = PROJECT_ROOT / "sample-policies"
DEFAULT_UPLOAD_DIR = PROJECT_ROOT / "backend" / "documents"
SECTION_PATTERN = re.compile(r"^##\s+Section\s+([^|]+)\|\s*(.+?)\s*$", re.MULTILINE)


def _upload_dir() -> Path:
    return Path(os.getenv("CAMPUSANSWER_DOCUMENTS_DIR", "").strip() or DEFAULT_UPLOAD_DIR).expanduser()


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8")


def parse_document(path: Path, fictional: bool) -> PolicyDocument:
    raw = _read_text(path)
    lines = raw.splitlines()
    title = next((line.lstrip("# ").strip() for line in lines if line.startswith("# ")), path.stem)
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
        filename=path.name,
        fictional=fictional,
        sections=sections,
        collection="demo",
        source_type="fictional" if fictional else "uploaded",
    )


def list_documents() -> list[PolicyDocument]:
    docs: list[PolicyDocument] = []
    for directory, fictional in ((SAMPLE_DIR, True), (_upload_dir(), False)):
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() in {".txt", ".pdf"}:
                docs.append(parse_document(path, fictional))
    return docs


def save_upload(filename: str, content: bytes) -> PolicyDocument:
    upload_dir = _upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in {".txt", ".pdf"}:
        raise ValueError("Only TXT and text-based PDF documents are supported.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("Files must be 5 MB or smaller.")
    destination = upload_dir / safe_name
    if destination.exists():
        raise ValueError("A document with this filename already exists in the local library.")
    destination.write_bytes(content)
    document = parse_document(destination, fictional=False)
    if not document.sections:
        destination.unlink(missing_ok=True)
        raise ValueError("No sections found. Use headings formatted as '## Section 1.2 | Title'.")
    return document
