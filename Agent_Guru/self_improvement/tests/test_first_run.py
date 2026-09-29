"""A new install starts with an empty self-improvement database.

Two components crashed on it. MetaLearner.update_patterns() read a table that
was only created when the first execution was stored ("no such table:
execution_features"), and ImprovementVerifier.verify_improvement() divided by
the number of tasks in its baseline window (ZeroDivisionError). Every new user
hit both; nobody who already had data ever did, so they went unnoticed.
"""

from __future__ import annotations

import json

import pytest

from Agent_Guru.self_improvement.database_schema import DatabaseSchema


@pytest.fixture
def empty_db(tmp_path) -> str:
    path = str(tmp_path / "self_improvement.db")
    DatabaseSchema.create_schema(path)
    return path


class TestMetaLearnerOnAnEmptyDatabase:
    def test_update_patterns_before_any_execution(self, empty_db):
        from Agent_Guru.self_improvement.meta_learner import MetaLearner

        learner = MetaLearner(empty_db)

        learner.update_patterns()

    def test_feature_correlations_before_any_execution(self, empty_db):
        from Agent_Guru.self_improvement.meta_learner import MetaLearner

        assert MetaLearner(empty_db).analyze_feature_correlations() == {}


class TestImprovementVerifierOnAnEmptyDatabase:
    def test_verification_reports_instead_of_crashing(self, empty_db):
        from Agent_Guru.self_improvement.validation.verify_improvement import (
            ImprovementVerifier,
        )

        metrics = ImprovementVerifier(empty_db).verify_improvement().improvement_metrics

        assert metrics.is_significant is False
        assert metrics.p_value == 1.0
        assert metrics.confidence_interval == (-1.0, 1.0)
        assert metrics.meets_target is False

    def test_both_reports_generate_and_the_json_is_valid(self, empty_db):
        from Agent_Guru.self_improvement.validation.verify_improvement import (
            ImprovementVerifier,
        )

        verifier = ImprovementVerifier(empty_db)
        report = verifier.verify_improvement()

        json.loads(verifier.generate_report_json(report))
        assert verifier.generate_report_markdown(report)
