"""Documents can be added through the local API, with the owner's key, and nothing else gets in."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from Agent_Guru.integration import local_api  # noqa: E402

KEY = "test-owner-key-1234567890"


class Store:
    def __init__(self):
        self.added = []

    async def add(self, path):
        self.added.append(path)
        return SimpleNamespace(name=path.name, status="added", passages=3)

    def documents(self):
        return [{"name": p.name} for p in self.added]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(local_api, "owner_key", lambda **k: KEY)
    monkeypatch.setenv("LOCALAPPDATA" if __import__("os").name == "nt" else "XDG_DATA_HOME", str(tmp_path))
    events = SimpleNamespace(published=[])
    events.publish = lambda event, **d: events.published.append((event, d))
    orchestrator = SimpleNamespace(_documents=Store(), events=events)
    return TestClient(local_api.create_app(orchestrator)), orchestrator, tmp_path


def test_a_document_is_saved_and_added(client):
    http, orch, tmp = client
    answer = http.post("/v1/documents", params={"name": "lease 2026.txt"}, content=b"Two months notice.",
                       headers={"X-API-Key": KEY})
    assert answer.status_code == 200 and answer.json() == {"name": "lease 2026.txt", "status": "added", "passages": 3}  # nosec B101
    (saved,) = orch._documents.added
    assert saved.read_bytes() == b"Two months notice." and saved.parent.name == "uploads"  # nosec B101
    assert http.get("/v1/documents", headers={"X-API-Key": KEY}).json() == [{"name": "lease 2026.txt"}]  # nosec B101


def test_no_key_no_document(client):
    http, orch, _ = client
    assert http.post("/v1/documents", params={"name": "a.txt"}, content=b"x").status_code in (401, 403)  # nosec B101
    assert orch._documents.added == []  # nosec B101


@pytest.mark.parametrize(("name", "size", "code"), [
    ("tool.exe", 2, 415), ("notes.txt", 0, 413), ("big.pdf", 20 * 1024 * 1024 + 1, 413),
])
def test_only_documents_of_a_sane_size(client, name, size, code):
    http, orch, _ = client
    assert http.post("/v1/documents", params={"name": name}, content=b"x" * size, headers={"X-API-Key": KEY}).status_code == code  # nosec B101
    assert orch._documents.added == []  # nosec B101


def test_a_name_cannot_leave_the_uploads_folder(client):
    http, orch, tmp = client
    answer = http.post("/v1/documents", params={"name": "..\\..\\evil.txt"}, content=b"x", headers={"X-API-Key": KEY})
    assert answer.status_code == 200  # nosec B101
    (saved,) = orch._documents.added
    assert saved.parent.name == "uploads" and ".." not in saved.name  # nosec B101
