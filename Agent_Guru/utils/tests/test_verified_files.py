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


# Resumable downloads, used by the installer. Without resume a cut-off
# download started again from zero, and its message did not name the host.


class RangeServer:
    """Serves DATA, honours "Range: bytes=N-" with a 206 unless told to ignore it, can drop mid-way."""

    def __init__(self, data: bytes = DATA, *, honour_range: bool = True, drop_after: int | None = None):
        self.data, self.honour_range, self.drop_after = data, honour_range, drop_after
        self.ranges: list[str | None] = []

    def __call__(self, request, timeout=None):
        wanted = request.get_header("Range")
        self.ranges.append(wanted)
        start = int(wanted.split("=")[1].rstrip("-")) if wanted and self.honour_range else 0
        response = FakeResponse(self.data[start:], self.drop_after)
        response.status = 206 if start else 200
        self.drop_after = None  # only the first connection drops
        return response


def test_a_dropped_download_keeps_its_bytes_and_names_the_host(tmp_path, monkeypatch):
    server = RangeServer(drop_after=4096)
    monkeypatch.setattr(vf.urllib.request, "urlopen", server)
    with pytest.raises(vf.DownloadError) as caught:
        vf.download("https://files.example.test/w/model.onnx", tmp_path / "model.onnx", pin(), resume=True)
    message = str(caught.value)
    assert message.startswith("files.example.test: model.onnx:") and f"after 4096 of {len(DATA)} bytes" in message  # nosec B101
    assert (tmp_path / "model.onnx.part").stat().st_size == 4096 and not (tmp_path / "model.onnx").exists()  # nosec B101


def test_the_next_attempt_asks_only_for_the_rest(tmp_path, monkeypatch):
    server = RangeServer(drop_after=4096)
    monkeypatch.setattr(vf.urllib.request, "urlopen", server)
    with pytest.raises(vf.DownloadError):
        vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin(), resume=True)
    vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin(), resume=True)
    assert server.ranges == [None, "bytes=4096-"]  # nosec B101
    assert (tmp_path / "model.onnx").read_bytes() == DATA and not list(tmp_path.glob("*.part"))  # nosec B101


def test_a_server_that_ignores_range_gets_a_fresh_start(tmp_path, monkeypatch):
    (tmp_path / "model.onnx.part").write_bytes(DATA[:4096])
    monkeypatch.setattr(vf.urllib.request, "urlopen", RangeServer(honour_range=False))
    vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin(), resume=True)
    assert (tmp_path / "model.onnx").read_bytes() == DATA  # nosec B101  not 4096 bytes twice


def test_a_wrong_partial_fails_the_hash_and_is_thrown_away(tmp_path, monkeypatch):
    (tmp_path / "model.onnx.part").write_bytes(b"Z" * 4096)  # not the start of DATA
    monkeypatch.setattr(vf.urllib.request, "urlopen", RangeServer())
    with pytest.raises(VerificationError):
        vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin(), resume=True)
    assert not list(tmp_path.iterdir())  # nosec B101  the next attempt starts clean


def test_a_partial_longer_than_the_pin_is_discarded(tmp_path, monkeypatch):
    (tmp_path / "model.onnx.part").write_bytes(DATA + b"more")
    server = RangeServer()
    monkeypatch.setattr(vf.urllib.request, "urlopen", server)
    vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin(), resume=True)
    assert server.ranges == [None] and (tmp_path / "model.onnx").read_bytes() == DATA  # nosec B101


def test_a_cancel_stops_at_once_and_keeps_the_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(vf.urllib.request, "urlopen", RangeServer())
    with pytest.raises(vf.DownloadCancelled):
        vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin(), resume=True,
                    should_stop=lambda: True)
    assert (tmp_path / "model.onnx.part").stat().st_size == 4096  # nosec B101  one chunk, then the stop


def test_a_complete_partial_is_verified_without_a_request(tmp_path, monkeypatch):
    (tmp_path / "model.onnx.part").write_bytes(DATA)
    server = RangeServer()
    monkeypatch.setattr(vf.urllib.request, "urlopen", server)
    vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin(), resume=True)
    assert server.ranges == [] and (tmp_path / "model.onnx").read_bytes() == DATA  # nosec B101


def test_too_many_bytes_while_resuming_throws_the_partial_away(tmp_path, monkeypatch):
    # A kept partial that already overflowed would be resumed from forever.
    monkeypatch.setattr(vf.urllib.request, "urlopen", RangeServer(DATA + b"extra payload"))
    with pytest.raises(VerificationError, match="more data"):
        vf.download("https://example.test/model.onnx", tmp_path / "model.onnx", pin(), resume=True)
    assert not list(tmp_path.iterdir())  # nosec B101
