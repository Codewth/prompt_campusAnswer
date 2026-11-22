import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app import cloud_store, policies, profiles, revocations
from app.main import app
from app.models import ProfileUpdate
from app.policies import MAX_UPLOAD_BYTES


class FakeResponse:
    def __init__(self, payload=None, status_code=200, content=None):
        self.status_code = status_code
        self.ok = status_code < 400
        self.content = content if content is not None else (
            json.dumps(payload).encode("utf-8") if payload is not None else b""
        )
        self.payload = payload

    def json(self):
        return self.payload


def _set_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://campusanswer-test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "server-only-test-key")


def test_cloud_profile_is_scoped_to_uid_and_upserted(monkeypatch):
    _set_supabase(monkeypatch)
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "GET":
            return FakeResponse([])
        if method == "POST":
            return FakeResponse([{**kwargs["json"], "theme": "light"}])
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr(cloud_store.requests, "request", fake_request)
    initial = profiles.get_profile("user-1", "student@example.edu", None, "Google Name")
    assert initial["name"] == "Google Name"

    saved = profiles.save_profile(
        "user-1",
        ProfileUpdate(
            name="Student",
            university="Bennett University",
            enrollment_number="S24CSEU0001",
            course="B.Tech",
            specialization="Computer Science",
            academic_year="3rd year",
            semester="6",
            batch="2024",
        ),
        "student@example.edu",
        None,
    )
    assert saved["uid"] == "user-1"
    assert saved["name"] == "Student"
    assert saved["theme"] == "light"
    assert calls[0][2]["params"]["uid"] == "eq.user-1"
    assert calls[1][2]["params"]["on_conflict"] == "uid"


def test_cloud_theme_update_preserves_edited_profile_name(monkeypatch):
    _set_supabase(monkeypatch)
    existing = {
        "uid": "user-1",
        "name": "Student Edited Name",
        "university": "Bennett University",
        "enrollment_number": "",
        "course": "",
        "specialization": "",
        "academic_year": "",
        "semester": "",
        "batch": "",
        "theme": "light",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    upsert_payload = {}

    def fake_request(method, url, **kwargs):
        nonlocal upsert_payload
        if method == "GET":
            return FakeResponse([existing])
        if method == "POST":
            upsert_payload = kwargs["json"]
            return FakeResponse([{**existing, **upsert_payload}])
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr(cloud_store.requests, "request", fake_request)
    saved = profiles.save_theme("user-1", "dark", "student@example.edu", None, "Google Name")
    assert saved["name"] == "Student Edited Name"
    assert "name" not in upsert_payload
    assert saved["theme"] == "dark"


def test_logout_revocation_uses_persistent_cloud_store(monkeypatch):
    _set_supabase(monkeypatch)
    token = "firebase-token-for-test"
    expected_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method in {"DELETE", "POST"}:
            return FakeResponse(status_code=204)
        if method == "GET":
            return FakeResponse([{"token_hash": expected_hash}])
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr(cloud_store.requests, "request", fake_request)
    revocations.revoke_token(token, "user-1", 2_000_000_000)
    assert revocations.is_token_revoked(token)
    inserted = next(call[2]["json"] for call in calls if call[0] == "POST")
    assert inserted == {
        "token_hash": expected_hash,
        "user_id": "user-1",
        "expires_at": 2_000_000_000,
    }
    assert token not in json.dumps(inserted)


def test_uploaded_documents_use_private_cloud_storage(monkeypatch, tmp_path):
    _set_supabase(monkeypatch)
    upload_dir = tmp_path / "must-not-be-used"
    monkeypatch.setenv("CAMPUSANSWER_DOCUMENTS_DIR", str(upload_dir))
    content = b"# Cloud Policy\n\n## Section 1.1 | Attendance\nStudents must follow the listed schedule."
    uploaded = []
    policies._invalidate_cloud_documents_cache()
    object_listings = iter([[], [("attendance.txt", len(content))]])
    monkeypatch.setattr(policies, "upload_document", lambda *args: uploaded.append(args))
    monkeypatch.setattr(policies, "list_uploaded_documents", lambda: next(object_listings))
    monkeypatch.setattr(policies, "download_uploaded_document", lambda name: content)

    saved = policies.save_upload(r"C:\temporary\attendance.txt", content)
    listed = policies.list_documents()

    assert saved.filename == "attendance.txt"
    assert uploaded[0] == (
        "attendance.txt",
        content,
        "text/plain; charset=utf-8",
    )
    assert any(document.filename == "attendance.txt" for document in listed)
    assert not upload_dir.exists()


def test_supabase_storage_listing_and_download_preserve_file_bytes(monkeypatch):
    _set_supabase(monkeypatch)
    content = b"# Policy\n\n## Section 1.1 | Rules\nExact source text."
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/storage/v1/object/list/campusanswer-documents"):
            return FakeResponse([{"name": "policy.txt", "metadata": {"size": len(content)}}])
        if url.endswith("/storage/v1/object/campusanswer-documents/policy.txt"):
            return FakeResponse(content=content)
        if method == "POST":
            return FakeResponse({})
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr(cloud_store.requests, "request", fake_request)
    assert cloud_store.list_uploaded_documents() == [("policy.txt", len(content))]
    assert cloud_store.download_uploaded_document("policy.txt") == content
    cloud_store.upload_document("policy.txt", content, "text/plain")
    assert calls[1][2]["headers"]["apikey"] == "server-only-test-key"
    assert calls[2][2]["data"] == content


def test_duplicate_cloud_upload_returns_validation_error(monkeypatch):
    _set_supabase(monkeypatch)
    monkeypatch.setattr(policies, "list_uploaded_documents", lambda: [])

    def already_exists(*args):
        raise cloud_store.CloudObjectAlreadyExistsError("A document with this filename already exists.")

    monkeypatch.setattr(policies, "upload_document", already_exists)
    content = b"# Cloud Policy\n\n## Section 1.1 | Attendance\nStudents must follow the listed schedule."
    with pytest.raises(ValueError, match="already exists"):
        policies.save_upload("attendance.txt", content)


def test_upload_byte_limit_is_enforced_before_document_parsing():
    with pytest.raises(ValueError, match="5 MB or smaller"):
        policies.save_upload("large.txt", b"x" * (MAX_UPLOAD_BYTES + 1))


def test_free_deployment_health_requires_cloud_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("CAMPUSANSWER_REQUIRE_CLOUD_STORAGE", "true")
    local_database = tmp_path / "not-used.sqlite"
    monkeypatch.setenv("CAMPUSANSWER_AUTH_DATABASE", str(local_database))
    with pytest.raises(cloud_store.CloudStoreError, match="Configure Supabase"):
        profiles.get_profile("user-1", None, None, None)
    assert not local_database.exists()
    with TestClient(app) as client:
        missing = client.get("/api/health")
    assert missing.status_code == 503

    _set_supabase(monkeypatch)
    with TestClient(app) as client:
        configured = client.get("/api/health")
    assert configured.status_code == 200
    assert configured.json() == {"status": "ok", "persistence": "supabase"}
