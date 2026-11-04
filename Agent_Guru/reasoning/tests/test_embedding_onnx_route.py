"""Memory embeddings through onnxruntime when the ONNX export is installed.

embedding.py imported torch at module scope only to choose "cuda" or "cpu",
so every import of the memory package loaded torch, and an install needed
torch, transformers and sentence-transformers for memory search: 221 MB more
to download for the core (Windows, Python 3.13, against the lock). With the
real all-MiniLM-L6-v2 export the two routes gave the same vectors (lowest
cosine 1.000000 over 38 texts); these tests pin the mechanics with a tiny
model built here, so nothing is downloaded.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - runs this interpreter on a fixed script
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[3]
VOCAB = {"[PAD]": 0, "[UNK]": 1, "hello": 2, "world": 3, "blue": 4, "sky": 5}
DIM = 4
#: One row per token id. Row 0 ([PAD]) is huge, so pooling that let padding
#: in would move every padded vector far from the unpadded one.
TABLE = np.array([[100, 100, 100, 100], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [1, 1, 0, 0], [0, 0, 1, 1]],
                 dtype=np.float32)


def write_tiny_model(folder: Path) -> None:
    """model.onnx: last_hidden_state = TABLE[input_ids]; tokenizer.json: whitespace word level."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper
    from tokenizers import Tokenizer, models, pre_tokenizers

    folder.mkdir(parents=True, exist_ok=True)
    graph = helper.make_graph(
        [helper.make_node("Gather", ["table", "input_ids"], ["last_hidden_state"], axis=0)],
        "tiny",
        [helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["b", "s"]),
         helper.make_tensor_value_info("attention_mask", TensorProto.INT64, ["b", "s"]),
         helper.make_tensor_value_info("token_type_ids", TensorProto.INT64, ["b", "s"])],
        [helper.make_tensor_value_info("last_hidden_state", TensorProto.FLOAT, ["b", "s", DIM])],
        initializer=[numpy_helper.from_array(TABLE, "table")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.save(model, str(folder / "model.onnx"))
    tok = Tokenizer(models.WordLevel(VOCAB, unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    tok.save(str(folder / "tokenizer.json"))


def expected(text: str) -> np.ndarray:
    rows = TABLE[[VOCAB.get(w, 1) for w in text.split()]]
    v = rows.mean(axis=0)
    return v / np.linalg.norm(v)


def test_the_encoder_pools_over_real_tokens_only_and_normalises(tmp_path):
    from Agent_Guru.reasoning.memory.embedding import _OnnxSentenceEncoder

    write_tiny_model(tmp_path)
    enc = _OnnxSentenceEncoder(tmp_path)
    texts = ["hello", "hello world blue sky", "sky"]
    batch = enc.encode(texts, batch_size=3, normalize_embeddings=True)
    assert batch.shape == (3, DIM)  # nosec B101
    for text, vector in zip(texts, batch, strict=True):
        # The short texts are padded to four tokens in this batch; a pooling
        # that counted [PAD] would be dominated by its row of 100s.
        np.testing.assert_allclose(vector, expected(text), rtol=1e-6)
        np.testing.assert_allclose(enc.encode(text, normalize_embeddings=True), expected(text), rtol=1e-6)
    assert enc.get_sentence_embedding_dimension() == DIM  # nosec B101


def test_it_rejects_an_argument_sentence_transformers_has_but_it_does_not(tmp_path):
    from Agent_Guru.reasoning.memory.embedding import _OnnxSentenceEncoder

    write_tiny_model(tmp_path)
    with pytest.raises(TypeError):
        _OnnxSentenceEncoder(tmp_path).encode("hello", output_value="token_embeddings")


_CHILD = r"""
import sys
from Agent_Guru.utils.profile_isolation import isolate_profile
isolate_profile(sys.argv[1])
from Agent_Guru.utils.path_utils import app_data_dir
sys.path.insert(0, sys.argv[2])
from test_embedding_onnx_route import write_tiny_model
write_tiny_model(app_data_dir("models", "embedding", "all-MiniLM-L6-v2"))
import Agent_Guru.reasoning.memory  # the package import that used to load torch
print("after-import", "torch" in sys.modules)
from Agent_Guru.reasoning.memory.embedding import EmbeddingGenerator
gen = EmbeddingGenerator()
vector = gen.generate("hello world")
print("route", type(gen.model).__name__, gen.device, len(vector))
print("after-generate", "torch" in sys.modules, "sentence_transformers" in sys.modules)
"""


@pytest.mark.timeout(120)
def test_an_install_with_the_onnx_export_never_loads_torch(tmp_path):
    # A fresh interpreter: this test process has usually imported torch
    # already through other tests, so only a new one can show it is not needed.
    env = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_GURU_")}
    env["PYTHONPATH"] = str(REPO)
    run = subprocess.run([sys.executable, "-c", _CHILD, str(tmp_path / "profile"), str(Path(__file__).parent)],  # nosec B603
                         cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=110, check=False)
    assert run.returncode == 0, run.stderr[-2000:]  # nosec B101
    lines = run.stdout.splitlines()
    assert "after-import False" in lines, run.stdout  # nosec B101
    assert f"route _OnnxSentenceEncoder cpu {DIM}" in lines, run.stdout  # nosec B101
    assert "after-generate False False" in lines, run.stdout  # nosec B101


def test_without_the_export_the_sentence_transformers_route_is_unchanged(monkeypatch, tmp_path):
    import types

    from Agent_Guru.reasoning.memory import embedding

    made = []

    class _StandIn:
        def __init__(self, name, device=None, local_files_only=False):
            made.append(name)

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = _StandIn
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setattr(embedding, "_MODEL_CACHE", {})
    monkeypatch.setattr(embedding, "_onnx_folder", lambda name: tmp_path / "not-installed")
    assert isinstance(embedding._load_model("sentence-transformers/all-MiniLM-L6-v2", "cpu"), _StandIn)  # nosec B101
    assert made == ["sentence-transformers/all-MiniLM-L6-v2"]  # nosec B101
