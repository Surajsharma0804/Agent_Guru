"""Optional models that are not installed are an info line at start, not warnings.

Every start logged "Neural Classifier initialization failed: ONNX model not
found ... Please convert the model first" and the same for the spaCy NER
model, each twice, plus two InsightFace warnings (round 12 soak). None of
those models is shipped and nothing in the app turns them on; the fast-path
rules and the LLM classify intents, and the Haar cascade finds faces. Six
warnings at every start for the expected install buried the ones that
matter. A model that is installed but fails to load still warns, and so does
a stub face embedding when one is actually produced.
"""

from __future__ import annotations

import logging

import numpy as np

from Agent_Guru.reasoning.intent.engine import IntentDetectionEngine, IntentEngineConfig
from Agent_Guru.reasoning.intent.ner_extractor import NERConfig
from Agent_Guru.reasoning.intent.neural_classifier import ClassifierConfig


def _engine(tmp_path, onnx_path):
    return IntentDetectionEngine(IntentEngineConfig(
        neural_config=ClassifierConfig(model_path=str(onnx_path)),
        ner_config=NERConfig(model_path=str(tmp_path / "no_ner_model")),
        enable_fast_path=False, enable_llm_fallback=False, enable_online_learning=False,
    ))


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def test_missing_intent_models_are_one_info_line(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    engine = _engine(tmp_path, tmp_path / "no_model.onnx")
    engine.initialize()
    assert not _warnings(caplog), _warnings(caplog)  # nosec B101
    said = [r.getMessage() for r in caplog.records if "Optional intent models not installed" in r.getMessage()]
    assert len(said) == 1 and "neural intent classifier" in said[0] and "NER" in said[0], said  # nosec B101
    assert engine.neural_classifier is None and engine.ner_extractor is None  # nosec B101


def test_an_installed_model_that_fails_to_load_still_warns(tmp_path, caplog):
    broken = tmp_path / "model.onnx"
    broken.write_bytes(b"not an onnx model")
    caplog.set_level(logging.INFO)
    _engine(tmp_path, broken).initialize()
    assert any("Neural Classifier initialization failed" in w for w in _warnings(caplog)), caplog.text  # nosec B101


def test_insightface_missing_is_info_at_start_and_a_warning_when_a_stub_is_used(monkeypatch, caplog):
    from Agent_Guru.vision import face_features
    from Agent_Guru.vision.detection import detector

    monkeypatch.setattr(face_features, "_INSIGHTFACE_AVAILABLE", False)
    monkeypatch.setattr(detector, "_INSIGHTFACE_AVAILABLE", False)
    caplog.set_level(logging.INFO)
    extractor = face_features.FaceFeatureExtractor()
    detector.FaceDetector()
    assert not _warnings(caplog), _warnings(caplog)  # nosec B101
    assert sum("InsightFace not installed (optional)" in r.getMessage() for r in caplog.records) == 2  # nosec B101

    caplog.clear()
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    extractor._stub_extract(image, image.tobytes())
    assert any("stub embedding" in w for w in _warnings(caplog)), caplog.text  # nosec B101
