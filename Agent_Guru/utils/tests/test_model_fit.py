"""One GPU-fit rule for `agent-guru models` and the installer's planner."""

from __future__ import annotations

import subprocess  # nosec B404 - runs this interpreter on a fixed script
import sys
from pathlib import Path

from Agent_Guru.utils import model_fit

REPO = Path(__file__).resolve().parents[3]


def test_a_model_needs_its_weights_plus_a_fifth_plus_500_mb():
    assert model_fit.needs_mb(1000) == 1700  # nosec B101
    assert model_fit.needs_mb(9830.4) == 12296  # nosec B101  gemma4's 9.6 GB


def test_the_three_answers_at_their_boundaries():
    # 2000 MB on disk needs 2900 MB; 30 % of the weights is 600 MB.
    assert model_fit.gpu_fit(2000, 2900) == "fits"  # nosec B101
    assert model_fit.gpu_fit(2000, 2899) == "partial"  # nosec B101
    assert model_fit.gpu_fit(2000, 600) == "partial"  # nosec B101
    assert model_fit.gpu_fit(2000, 599) == "cpu"  # nosec B101


def test_the_catalog_uses_this_rule_and_not_a_copy():
    from Agent_Guru.llm import model_catalog

    assert model_catalog.gpu_fit is model_fit.gpu_fit  # nosec B101
    assert model_catalog.needs_mb is model_fit.needs_mb  # nosec B101


def test_importing_it_loads_nothing_outside_the_standard_library():
    # The installer's launcher imports it before Agent Guru's packages exist.
    code = ("import sys; before = set(sys.modules); import Agent_Guru.utils.model_fit; "
            "print(sorted(m for m in set(sys.modules) - before if not m.startswith(('Agent_Guru', '_'))))")
    run = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(REPO)!r}); {code}"],  # nosec B603
                         capture_output=True, text=True, timeout=60, check=True)
    assert run.stdout.strip() == "[]", run.stdout  # nosec B101
