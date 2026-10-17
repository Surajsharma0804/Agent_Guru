"""Model files are used only when they are the pinned bytes.

Kokoro's downloader renamed a file to its real name before checking its
hash, and its hashes were None, so whatever arrived was loaded.
"""

from __future__ import annotations

import hashlib
import io
import time

import pytest

from Agent_Guru.utils import verified_files as vf
from Agent_Guru.utils.verified_files import PinnedFile, VerificationError

DATA = b"model weights " * 1000


def pin(data: bytes = DATA, name: str = "model.onnx") -> PinnedFile:
    return PinnedFile(name, len(data), hashlib.sha256(data).hexdigest())


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, fail_after: int | None = None):
        super().__init__(data)
        self._fail_after = fail_after
        self._sent = 0

    def read(self, n=-1):
        if self._fail_after is not None and self._sent >= self._fail_after:
            raise ConnectionResetError("connection dropped")
        chunk = super().read(min(n, 4096) if n and n > 0 else 4096)
        self._sent += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def serve(monkeypatch, data: bytes, fail_after: int | None = None) -> list[str]:
    urls: list[str] = []

    def urlopen(request, timeout=None):
        urls.append(request.full_url)
        return FakeResponse(data, fail_after)

    monkeypatch.setattr(vf.urllib.request, "urlopen", urlopen)
    return urls


def test_a_good_download_is_verified_and_named(tmp_path, monkeypatch):
    serve(monkeypatch, DATA)
    vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin())
    assert (tmp_path / "model.onnx").read_bytes() == DATA  # nosec B101
    assert not list(tmp_path.glob("*.part"))  # nosec B101


def test_a_mismatching_download_never_gets_the_real_name(tmp_path, monkeypatch):
    serve(monkeypatch, b"X" + DATA[1:])  # same size, different bytes
    with pytest.raises(VerificationError, match="pinned sha256"):
        vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin())
    assert not (tmp_path / "model.onnx").exists() and not list(tmp_path.glob("*.part"))  # nosec B101


def test_an_interrupted_download_leaves_nothing(tmp_path, monkeypatch):
    serve(monkeypatch, DATA, fail_after=4096)
    with pytest.raises(ConnectionResetError):
        vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin())
    assert list(tmp_path.iterdir()) == []  # nosec B101


def test_a_bad_download_does_not_replace_a_verified_file(tmp_path, monkeypatch):
    (tmp_path / "model.onnx").write_bytes(DATA)
    serve(monkeypatch, b"tampered" + DATA[8:])
    with pytest.raises(VerificationError):
        vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin())
    assert (tmp_path / "model.onnx").read_bytes() == DATA  # nosec B101


def test_more_bytes_than_pinned_is_refused(tmp_path, monkeypatch):
    serve(monkeypatch, DATA + b"extra payload")
    with pytest.raises(VerificationError, match="more data"):
        vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin())
    assert not (tmp_path / "model.onnx").exists()  # nosec B101


def test_a_corrupted_cache_is_caught_even_after_a_stamp(tmp_path):
    (tmp_path / "model.onnx").write_bytes(DATA)
    vf.ensure_verified(tmp_path, [pin()])
    time.sleep(0.01)
    (tmp_path / "model.onnx").write_bytes(b"Y" + DATA[1:])
    with pytest.raises(VerificationError, match="pinned sha256"):
        vf.ensure_verified(tmp_path, [pin()])


def test_a_verified_folder_is_not_hashed_again(tmp_path, monkeypatch):
    (tmp_path / "model.onnx").write_bytes(DATA)
    vf.ensure_verified(tmp_path, [pin()])
    hashed: list[str] = []
    monkeypatch.setattr(vf, "file_digest", lambda path, kind="sha256": hashed.append(path.name) or "x")
    vf.ensure_verified(tmp_path, [pin()])  # offline start: stamp only, no network, no hash
    assert hashed == []  # nosec B101


def test_a_changed_pin_forces_a_full_check(tmp_path):
    (tmp_path / "model.onnx").write_bytes(DATA)
    vf.ensure_verified(tmp_path, [pin()])
    other = PinnedFile("model.onnx", len(DATA), "0" * 64)
    with pytest.raises(VerificationError):
        vf.ensure_verified(tmp_path, [other])


def test_copy_in_verifies_an_offline_source(tmp_path):
    source = tmp_path / "usb" / "model.onnx"
    source.parent.mkdir()
    source.write_bytes(b"Z" + DATA[1:])
    with pytest.raises(VerificationError):
        vf.copy_in(source, tmp_path / "cache" / "model.onnx", pin())
    assert not (tmp_path / "cache" / "model.onnx").exists()  # nosec B101


def test_git_blob_ids_are_computed_as_git_does(tmp_path):
    (tmp_path / "f.txt").write_bytes(b"hello\n")
    assert vf.file_digest(tmp_path / "f.txt", "git-sha1") == "ce013625030ba8dba906f756967f9e9ca394464a"  # nosec B101
