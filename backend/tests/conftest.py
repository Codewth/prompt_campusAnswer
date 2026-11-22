import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest


@pytest.fixture(autouse=True)
def isolate_supabase_environment(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("CAMPUSANSWER_REQUIRE_CLOUD_STORAGE", raising=False)
