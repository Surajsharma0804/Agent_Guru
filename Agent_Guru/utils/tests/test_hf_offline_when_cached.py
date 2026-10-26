"""The test run goes offline for Hugging Face only when every model it loads is already cached.

With the models cached, loading them still sent 66 version checks to huggingface.co a run. The root
conftest sets HF_HUB_OFFLINE=1 when they are all cached and leaves a cold cache online, so CI's first
run still downloads them. Here the cache is a temporary folder laid out as huggingface_hub lays it out.
"""

from __future__ import annotations

import sys

import pytest

root_conftest = sys.modules["conftest"]


def _snapshot(cache, repo, files=("config.json",)):
    folder = cache / f"models--{repo.replace('/', '--')}" / "snapshots" / "abc123"
    folder.mkdir(parents=True)
    for name in files:
        (folder / name).write_text("{}", encoding="utf-8")


def test_every_model_cached_is_offline(tmp_path):
    for repo in root_conftest._HF_TEST_MODELS:
        _snapshot(tmp_path, repo)
    assert all(root_conftest._hf_cached(r, tmp_path) for r in root_conftest._HF_TEST_MODELS)  # nosec B101


def test_an_empty_cache_stays_online(tmp_path):
    assert not any(root_conftest._hf_cached(r, tmp_path) for r in root_conftest._HF_TEST_MODELS)  # nosec B101


def test_one_missing_model_keeps_the_download_path(tmp_path):
    for repo in root_conftest._HF_TEST_MODELS[1:]:
        _snapshot(tmp_path, repo)
    cached = [root_conftest._hf_cached(r, tmp_path) for r in root_conftest._HF_TEST_MODELS]
    assert cached[0] is False and not all(cached)  # nosec B101


def test_a_snapshot_folder_with_no_files_is_not_cached(tmp_path):
    _snapshot(tmp_path, "sentence-transformers/all-MiniLM-L6-v2", files=())
    assert not root_conftest._hf_cached("sentence-transformers/all-MiniLM-L6-v2", tmp_path)  # nosec B101


@pytest.mark.parametrize("env, expected", [
    ({"HF_HUB_CACHE": "{tmp}/hub-cache"}, "{tmp}/hub-cache"),
    ({"HF_HOME": "{tmp}/hf-home"}, "{tmp}/hf-home/hub"),
    ({"XDG_CACHE_HOME": "{tmp}/xdg"}, "{tmp}/xdg/huggingface/hub"),
])
def test_the_cache_is_found_where_huggingface_hub_looks(tmp_path, monkeypatch, env, expected):
    for name in ("HF_HUB_CACHE", "HF_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value.format(tmp=tmp_path))
    assert root_conftest._hf_hub_cache() == type(tmp_path)(expected.format(tmp=tmp_path))  # nosec B101
