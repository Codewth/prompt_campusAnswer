import hashlib
import os
import sqlite3
import time
from pathlib import Path

from .cloud_store import supabase_is_configured, table_request


DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "auth-sessions.sqlite"


def _database_path() -> Path:
    return Path(os.getenv("CAMPUSANSWER_AUTH_DATABASE", str(DEFAULT_DATABASE))).expanduser()


def _connect() -> sqlite3.Connection:
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS revoked_tokens (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at INTEGER NOT NULL)"
    )
    return connection


def revoke_token(token: str, user_id: str, expires_at: int) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if supabase_is_configured():
        table_request(
            "DELETE",
            "revoked_tokens",
            params={"expires_at": f"lte.{int(time.time())}"},
            headers={"Prefer": "return=minimal"},
        )
        table_request(
            "POST",
            "revoked_tokens",
            params={"on_conflict": "token_hash"},
            json_body={"token_hash": token_hash, "user_id": user_id, "expires_at": expires_at},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
        return
    with _connect() as connection:
        connection.execute("DELETE FROM revoked_tokens WHERE expires_at <= unixepoch()")
        connection.execute(
            "INSERT OR REPLACE INTO revoked_tokens(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user_id, expires_at),
        )


def is_token_revoked(token: str) -> bool:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if supabase_is_configured():
        rows = table_request(
            "GET",
            "revoked_tokens",
            params={
                "select": "token_hash",
                "token_hash": f"eq.{token_hash}",
                "expires_at": f"gt.{int(time.time())}",
            },
        )
        if not isinstance(rows, list):
            raise RuntimeError("Supabase returned an invalid revoked-token response.")
        return bool(rows)
    with _connect() as connection:
        connection.execute("DELETE FROM revoked_tokens WHERE expires_at <= unixepoch()")
        return connection.execute(
            "SELECT 1 FROM revoked_tokens WHERE token_hash = ? AND expires_at > unixepoch()",
            (token_hash,),
        ).fetchone() is not None
