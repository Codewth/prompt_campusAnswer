import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from .models import ProfileUpdate
from .revocations import DEFAULT_DATABASE


ProfileTheme = Literal["light", "dark"]
PROFILE_FIELDS = (
    "name",
    "university",
    "enrollment_number",
    "course",
    "specialization",
    "academic_year",
    "semester",
    "batch",
)


def _database_path() -> Path:
    return Path(
        os.getenv("CAMPUSANSWER_PROFILE_DATABASE", "").strip()
        or os.getenv("CAMPUSANSWER_AUTH_DATABASE", "").strip()
        or DEFAULT_DATABASE
    ).expanduser()


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS student_profiles (
            uid TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            university TEXT NOT NULL DEFAULT '',
            enrollment_number TEXT NOT NULL DEFAULT '',
            course TEXT NOT NULL DEFAULT '',
            specialization TEXT NOT NULL DEFAULT '',
            academic_year TEXT NOT NULL DEFAULT '',
            semester TEXT NOT NULL DEFAULT '',
            batch TEXT NOT NULL DEFAULT '',
            theme TEXT NOT NULL DEFAULT 'light' CHECK (theme IN ('light', 'dark')),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    return connection


def get_profile(
    uid: str,
    email: str | None,
    photo_url: str | None,
    identity_name: str | None,
) -> dict:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM student_profiles WHERE uid = ?",
            (uid,),
        ).fetchone()
    saved = dict(row) if row else {}
    return {
        "uid": uid,
        "name": saved.get("name") or identity_name,
        "email": email,
        "photo_url": photo_url,
        **{field: saved.get(field, "") for field in PROFILE_FIELDS if field != "name"},
        "theme": saved.get("theme", "light"),
        "updated_at": saved.get("updated_at"),
    }


def save_profile(
    uid: str,
    update: ProfileUpdate,
    email: str | None,
    photo_url: str | None,
) -> dict:
    values = update.model_dump()
    with closing(_connect()) as connection:
        with connection:
            connection.execute(
                """INSERT INTO student_profiles (
                    uid, name, university, enrollment_number, course,
                    specialization, academic_year, semester, batch, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(uid) DO UPDATE SET
                    name = excluded.name,
                    university = excluded.university,
                    enrollment_number = excluded.enrollment_number,
                    course = excluded.course,
                    specialization = excluded.specialization,
                    academic_year = excluded.academic_year,
                    semester = excluded.semester,
                    batch = excluded.batch,
                    updated_at = CURRENT_TIMESTAMP""",
                (
                    uid,
                    *(values[field] for field in PROFILE_FIELDS),
                ),
            )
        row = connection.execute(
            "SELECT * FROM student_profiles WHERE uid = ?",
            (uid,),
        ).fetchone()
    saved = dict(row)
    return {
        "uid": uid,
        "name": saved["name"],
        "email": email,
        "photo_url": photo_url,
        **{field: saved[field] for field in PROFILE_FIELDS if field != "name"},
        "theme": saved["theme"],
        "updated_at": saved["updated_at"],
    }


def save_theme(
    uid: str,
    theme: ProfileTheme,
    email: str | None,
    photo_url: str | None,
    identity_name: str | None,
) -> dict:
    with closing(_connect()) as connection:
        with connection:
            connection.execute(
                """INSERT INTO student_profiles (uid, name, theme)
                VALUES (?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    theme = excluded.theme,
                    updated_at = CURRENT_TIMESTAMP""",
                (uid, identity_name or "", theme),
            )
        row = connection.execute(
            "SELECT * FROM student_profiles WHERE uid = ?",
            (uid,),
        ).fetchone()
    saved = dict(row)
    return {
        "uid": uid,
        "name": saved["name"] or identity_name,
        "email": email,
        "photo_url": photo_url,
        **{field: saved[field] for field in PROFILE_FIELDS if field != "name"},
        "theme": saved["theme"],
        "updated_at": saved["updated_at"],
    }
