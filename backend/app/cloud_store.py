import os
from urllib.parse import quote, urlsplit
from typing import Any

import requests


class CloudStoreError(RuntimeError):
    pass


class CloudObjectAlreadyExistsError(CloudStoreError):
    pass


def _settings() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url and not key:
        if os.getenv("CAMPUSANSWER_REQUIRE_CLOUD_STORAGE", "").strip().lower() == "true":
            raise CloudStoreError("Configure Supabase persistence before using this deployment.")
        return None
    if not url or not key:
        raise CloudStoreError("Set both SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CloudStoreError("SUPABASE_URL must be an HTTPS project URL.")
    return url, key


def supabase_is_configured() -> bool:
    return _settings() is not None


def _request(
    method: str,
    url: str,
    *,
    params: dict[str, str] | None = None,
    json_body: Any = None,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    raw_response: bool = False,
) -> Any:
    settings = _settings()
    if settings is None:
        raise CloudStoreError("Supabase persistence is not configured.")
    base_url, service_key = settings
    request_headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }
    if headers:
        request_headers.update(headers)
    try:
        response = requests.request(
            method,
            f"{base_url}{url}",
            params=params,
            json=json_body,
            data=body,
            headers=request_headers,
            timeout=15,
        )
    except requests.RequestException as error:
        raise CloudStoreError("Supabase could not be reached; the operation was not completed.") from error
    if response.status_code == 409:
        raise CloudObjectAlreadyExistsError("A document with this filename already exists.")
    if not response.ok:
        raise CloudStoreError(f"Supabase returned HTTP {response.status_code}; the operation was not completed.")
    if raw_response:
        return response.content
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as error:
        raise CloudStoreError("Supabase returned an unreadable response.") from error


def table_request(
    method: str,
    table: str,
    *,
    params: dict[str, str] | None = None,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
) -> Any:
    return _request(
        method,
        f"/rest/v1/{table}",
        params=params,
        json_body=json_body,
        headers=headers,
    )


def _bucket() -> str:
    return quote(os.getenv("SUPABASE_STORAGE_BUCKET", "campusanswer-documents").strip(), safe="")


def list_uploaded_documents() -> list[tuple[str, int]]:
    result = _request(
        "POST",
        f"/storage/v1/object/list/{_bucket()}",
        json_body={
            "prefix": "",
            "limit": 101,
            "offset": 0,
            "sortBy": {"column": "name", "order": "asc"},
        },
    )
    if not isinstance(result, list):
        raise CloudStoreError("Supabase Storage returned an invalid object listing.")
    if len(result) > 100:
        raise CloudStoreError("The uploaded-document limit of 100 files has been reached.")
    objects = []
    for item in result:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise CloudStoreError("Supabase Storage returned an invalid object listing.")
        metadata = item.get("metadata") or {}
        try:
            size = int(metadata.get("size", 0))
        except (TypeError, ValueError) as error:
            raise CloudStoreError("Supabase Storage returned invalid document-size metadata.") from error
        if size < 0:
            raise CloudStoreError("Supabase Storage returned invalid document-size metadata.")
        objects.append((item["name"], size))
    return objects


def download_uploaded_document(filename: str) -> bytes:
    result = _request(
        "GET",
        f"/storage/v1/object/{_bucket()}/{quote(filename, safe='')}",
        headers={"Accept": "application/octet-stream"},
        raw_response=True,
    )
    if not isinstance(result, bytes):
        raise CloudStoreError("Supabase Storage returned an invalid document.")
    return result


def upload_document(filename: str, content: bytes, content_type: str) -> None:
    _request(
        "POST",
        f"/storage/v1/object/{_bucket()}/{quote(filename, safe='')}",
        body=content,
        headers={"Content-Type": content_type, "x-upsert": "false"},
    )
