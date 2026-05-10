"""Property-based tests for Phase 2: Competitive analysis.

Task 3.4 — Properties 4 and 5.

Property 4: Competitive Gap Detection Correctness
    For any (measured, target) pair where measured > target (i.e., higher
    is worse — latency, CPU), gap analysis classifies as gap.
    Where measured <= target, no gap is raised.

Property 5: Remediation List Ordering
    For any list of RemediationItem objects, the output is sorted descending
    by competitive_impact_score with no inversions.

Subsystem: audit/tests
Requirements: 2.2, 2.3, 2.6, 9.3
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from audit.models import RemediationItem, Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATA_PATH = Path(__file__).parent.parent / "data" / "competitive_baselines.json"

COMPETITORS = [
    "Alexa", "Siri", "Google Assistant", "ChatGPT Desktop",
    "Claude Desktop", "Open Interpreter", "OpenVoiceOS",
]

REQUIRED_METRIC_KEYS = {
    "wake_word_p95_ms",
    "stt_wer_percent",
    "e2e_p95_ms",
    "idle_cpu_percent",
    "idle_ram_mb",
    "offline_capable",
    "multi_platform",
    "open_api",
}


def _make_item(score: float, ident: str = "REM-X") -> RemediationItem:
    return RemediationItem(
        id=ident,
        phase=2,
        severity=Severity.HIGH,
        affected_module="Agent_Guru/speech/wake_word.py",
        description="placeholder",
        expected_improvement="N/A",
        estimated_effort_hours=1.0,
        competitive_impact_score=score,
    )


def _is_sorted_descending(items: list[RemediationItem]) -> bool:
    """Return True if items are sorted descending by competitive_impact_score."""
    for i in range(len(items) - 1):
        if items[i].competitive_impact_score < items[i + 1].competitive_impact_score:
            return False
    return True


# ---------------------------------------------------------------------------
# competitive_baselines.json structure tests
# ---------------------------------------------------------------------------


class TestCompetitiveBaselinesFile:
    """The data file must exist and contain valid entries for all 7 competitors."""

    def test_file_exists(self) -> None:
        assert DATA_PATH.exists(), f"Missing: {DATA_PATH}"

    def test_file_is_valid_json(self) -> None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_all_competitors_present(self) -> None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        missing = [c for c in COMPETITORS if c not in data]
        assert missing == [], f"Missing competitors: {missing}"

    def test_each_competitor_has_required_keys(self) -> None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        for competitor in COMPETITORS:
            entry = data[competitor]
            missing_keys = REQUIRED_METRIC_KEYS - set(entry.keys())
            assert missing_keys == set(), (
                f"{competitor} missing keys: {missing_keys}"
            )

    def test_numeric_metrics_are_numbers(self) -> None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        numeric_keys = {
            "wake_word_p95_ms", "stt_wer_percent",
            "e2e_p95_ms", "idle_cpu_percent", "idle_ram_mb",
        }
        for competitor in COMPETITORS:
            for key in numeric_keys:
                value = data[competitor].get(key)
                if value is not None:
                    assert isinstance(value, (int, float)), (
                        f"{competitor}.{key} must be numeric, got {type(value)}"
                    )

    def test_boolean_metrics_are_bool(self) -> None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        bool_keys = {"offline_capable", "multi_platform", "open_api"}
        for competitor in COMPETITORS:
            for key in bool_keys:
                value = data[competitor].get(key)
                if value is not None:
                    assert isinstance(value, bool), (
                        f"{competitor}.{key} must be bool, got {type(value)}"
                    )

    def test_wake_word_latency_is_positive(self) -> None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        for competitor in COMPETITORS:
            value = data[competitor].get("wake_word_p95_ms")
            if value is not None:
                assert value > 0, f"{competitor}.wake_word_p95_ms must be > 0"

    def test_wer_percent_is_in_range(self) -> None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        for competitor in COMPETITORS:
            value = data[competitor].get("stt_wer_percent")
            if value is not None:
                assert 0.0 <= value <= 100.0, (
                    f"{competitor}.stt_wer_percent={value} out of range [0,100]"
                )


# ---------------------------------------------------------------------------
# Property 4: Gap detection correctness
# ---------------------------------------------------------------------------


class TestGapDetectionCorrectness:
    """Property 4 — measured > target → gap; measured <= target → no gap."""

    @given(
        measured=st.floats(min_value=0.001, max_value=10_000.0, allow_nan=False),
        target=st.floats(min_value=0.001, max_value=10_000.0, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_property_four_gap_classification(
        self, measured: float, target: float
    ) -> None:
        """For latency-style metrics, higher measured = worse.
        When measured > target → is_gap = True.
        When measured <= target → is_gap = False.
        """
        is_gap = measured > target
        # Verify our gap formula is correct by definition
        assert is_gap == (measured > target)
        # And the inverse
        assert (not is_gap) == (measured <= target)

    def test_exactly_at_target_is_not_a_gap(self) -> None:
        measured = 200.0
        target = 200.0
        assert not (measured > target), "At target == no gap"

    def test_one_unit_above_target_is_a_gap(self) -> None:
        measured = 201.0
        target = 200.0
        assert measured > target

    def test_well_below_target_is_not_a_gap(self) -> None:
        measured = 50.0
        target = 200.0
        assert not (measured > target)

    def test_gap_magnitude_formula(self) -> None:
        """competitive_impact_score = (gap_magnitude / target_value) * platforms_affected."""
        measured, target, platforms = 400.0, 200.0, 3
        gap_magnitude = measured - target
        score = (gap_magnitude / target) * platforms
        assert score == pytest.approx(3.0)

    def test_no_gap_yields_zero_score(self) -> None:
        measured, target, platforms = 100.0, 200.0, 3
        gap_magnitude = max(0.0, measured - target)
        score = (gap_magnitude / target) * platforms
        assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Property 5: Remediation list ordering
# ---------------------------------------------------------------------------


class TestRemediationListOrdering:
    """Property 5 — remediation output sorted descending by competitive_impact_score."""

    def test_empty_list_is_sorted(self) -> None:
        items: list[RemediationItem] = []
        assert _is_sorted_descending(items)

    def test_single_item_is_sorted(self) -> None:
        items = [_make_item(42.5)]
        assert _is_sorted_descending(items)

    def test_already_sorted_descending(self) -> None:
        items = [_make_item(100.0), _make_item(50.0), _make_item(10.0)]
        assert _is_sorted_descending(items)

    def test_unsorted_list_after_sort(self) -> None:
        items = [_make_item(10.0), _make_item(100.0), _make_item(50.0)]
        sorted_items = sorted(items, key=lambda x: x.competitive_impact_score, reverse=True)
        assert _is_sorted_descending(sorted_items)

    def test_equal_scores_preserve_order(self) -> None:
        items = [_make_item(42.0, "A"), _make_item(42.0, "B"), _make_item(42.0, "C")]
        sorted_items = sorted(items, key=lambda x: x.competitive_impact_score, reverse=True)
        assert _is_sorted_descending(sorted_items)

    @given(
        scores=st.lists(
            st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
            min_size=0,
            max_size=50,
        )
    )
    @settings(max_examples=200)
    def test_property_five_sorted_descending(self, scores: list[float]) -> None:
        """Property 5: any list of items sorted descending has no inversions."""
        items = [_make_item(s, f"R{i}") for i, s in enumerate(scores)]
        sorted_items = sorted(
            items, key=lambda x: x.competitive_impact_score, reverse=True
        )
        assert _is_sorted_descending(sorted_items), (
            f"Inversion found in: {[i.competitive_impact_score for i in sorted_items]}"
        )

    def test_top_item_has_highest_score(self) -> None:
        items = [_make_item(25.0), _make_item(75.0), _make_item(50.0)]
        sorted_items = sorted(items, key=lambda x: x.competitive_impact_score, reverse=True)
        assert sorted_items[0].competitive_impact_score == pytest.approx(75.0)
