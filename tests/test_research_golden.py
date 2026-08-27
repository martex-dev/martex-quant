"""Golden regression for the research corpus (MI Lab Layer 1, Step 0).

These tests are the safety net for the consolidation: they prove that
refactoring the duplicated panel/bootstrap/forward-return machinery changed
no published number.

Three separate guarantees, deliberately kept apart so a failure names its
own cause:

1. ``test_golden_stdout`` — the script still prints exactly what it printed
   when the baseline was frozen. This is the STOP condition. A mismatch is
   never resolved by updating the golden; it is investigated.
2. ``test_frozen_fingerprint_categories`` — inputs, config, environment and
   RNG are unchanged. ``code`` is allowed to change: that is the refactor.
3. ``test_rng_draw_sequence`` — CPython's RNG still produces the exact draw
   sequence every published CI was computed from.

Nothing here writes a golden. Freezing is done deliberately via
``scripts/freeze_research_baseline.py --write``.

CI note: these are a LOCAL gate and skip on a hosted runner. Two independent
reasons, both structural rather than incidental:

- ``/data/`` is gitignored, so GitHub Actions has no market data. Most specs
  skip on that alone.
- The fingerprint hashes its declared inputs byte for byte, and this
  repository stores text with CRLF. A Linux checkout has LF, so every
  markdown input hashes differently and reports a smaller byte count
  (PROJECT_MEMORY.md: 16,640 -> 16,429). The environment category also
  records exact interpreter and package versions, which a hosted runner
  resolves independently. Neither can be satisfied on both platforms from one
  frozen baseline, so the spec whose inputs are all committed markdown —
  research_graph_report — would fail in CI forever while proving nothing.

The skip is therefore keyed on the runner, and locally it is keyed only on
inputs being entirely absent: data that is present but CHANGED is a hard
failure, never a skip. The local gate is unchanged in strength.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

import pytest

from martex_quant.research import baseline
from martex_quant.research.baseline import ScriptSpec

ROOT = Path(__file__).resolve().parents[1]
IDS = [spec.name for spec in baseline.SPECS]

# Only scripts whose output is a function of their inputs alone can carry a
# byte-exact fixture. Time-dependent scripts are audited separately, in
# test_time_dependent_scripts_run_and_declare_their_dependencies.
GATED_SPECS = [spec for spec in baseline.SPECS if spec.requires_exact_stdout]
GATED_IDS = [spec.name for spec in GATED_SPECS]


def _stored_fingerprints() -> dict[str, Any]:
    path = ROOT / baseline.GOLDEN_DIR / baseline.FINGERPRINT_FILE
    if not path.exists():
        return {}
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


# --- fast structural tests (no market data needed) ----------------------------------


def test_spec_names_are_unique() -> None:
    names = [spec.name for spec in baseline.SPECS]
    assert len(names) == len(set(names))


# Scripts that are tooling, not research: they fetch data over the network or
# serve the dashboard, produce no ledger number, and are deliberately outside
# the frozen baseline.
NON_RESEARCH_SCRIPTS = {
    "pull_frontier",
    "pull_intraday",
    # Data collector for the H65 wide carry universe. Hits the network and
    # writes caches; it produces no research output to freeze.
    "pull_carry_universe",
    "dashboard_service",
    "freeze_research_baseline",
    # Meme layer: live data collectors and a report over data that is still
    # accruing. They read the network and the wall clock, so they have no
    # deterministic output to freeze; the layer's regression cover is the unit
    # tests over economics/panel/outcomes instead.
    "meme_record",
    "meme_panel",
    "meme_cohort_report",
    "meme_base_rate",
}


def test_every_research_script_has_a_spec() -> None:
    """A research script without a spec silently escapes regression cover.

    This test is why the baseline covers the whole research corpus rather
    than only the scripts Layer 1 edits: it failed on first run and exposed
    five strategy-grade studies — the ones holding DSR 0.990/0.992/1.000 —
    that the original 13-script plan had missed.
    """
    on_disk = {path.stem for path in (ROOT / "scripts").glob("*.py")} - NON_RESEARCH_SCRIPTS
    declared = {spec.name for spec in baseline.SPECS}
    assert not on_disk - declared, f"research scripts without a baseline spec: {on_disk - declared}"
    assert not declared - on_disk, f"specs without a script: {declared - on_disk}"


def test_rng_draw_sequence() -> None:
    """The RNG contract: seed, draw count, and draw ORDER are all frozen.

    Every published confidence interval is a function of this sequence.
    Written out explicitly rather than only as a hash so that a failure is
    readable, and so the values themselves are in version control.
    """
    rng = random.Random(20260810)
    first_ten = [rng.randint(0, 9_999) for _ in range(10)]
    assert first_ten == [5291, 797, 5815, 74, 7788, 887, 9419, 9740, 6899, 1565]

    # Draw COUNT matters as much as order: the bootstrap consumes exactly
    # n_blocks draws per iteration, so any change to that budget shifts every
    # subsequent draw. Pinning the 11th draw catches an off-by-one that
    # pinning only the first ten would miss.
    assert rng.randint(0, 9_999) == 11

    probe = baseline.rng_fingerprint()
    assert probe["n_draws"] == 512
    assert probe["sha256"] == ("b76b24ee69e7e28c51266e2bab73cf87a793674294488e5ff6411df288f1a62b")


def test_numeric_differences_reports_the_changed_value() -> None:
    expected = "sharpe 1.47  MDD -29.0%\n"
    actual = "sharpe 1.47  MDD -31.5%\n"
    diffs = baseline.numeric_differences(expected, actual)
    assert len(diffs) == 1
    assert "-29.0% -> -31.5%" in diffs[0]


def test_numeric_differences_detects_structural_change() -> None:
    diffs = baseline.numeric_differences("a 1 2\n", "a 1\n")
    assert diffs and "COUNT changed" in diffs[0]


def test_time_dependent_scripts_declare_their_dependencies_and_hold_no_golden() -> None:
    """A time-dependent script must say so and must not own a fixture.

    The registry may not quietly represent a script whose output moves with
    the calendar as a frozen historical golden — that is the honesty this
    classification exists to enforce.
    """
    for spec in baseline.SPECS:
        if spec.requires_exact_stdout:
            continue
        assert spec.external_dependencies, f"{spec.name}: time-dependent but no deps recorded"
        assert not (ROOT / spec.golden_path).exists(), (
            f"{spec.name} is time-dependent but still owns "
            f"{spec.golden_path}. A fixture that must be regenerated daily is "
            "not a golden; archive it under tests/golden/archive/ instead."
        )


def test_non_deterministic_scripts_are_labelled_and_documented() -> None:
    """A pinned baseline is forward-looking, never a historical reproduction,
    and the defect that makes it so must be on the record."""
    for spec in baseline.SPECS:
        if spec.reproducibility != "non_deterministic_pinned":
            continue
        assert spec.external_dependencies
        assert spec.name in baseline.REPRODUCIBILITY_DEFECTS


def test_archived_output_is_preserved_with_an_explanation() -> None:
    """The 2026-08-10 phase3_studies capture stays as evidence."""
    archive = ROOT / baseline.GOLDEN_DIR / "archive"
    assert (archive / "phase3_studies.2026-08-10.out").exists()
    readme = (archive / "README.md").read_text(encoding="utf-8")
    assert "not a permanent byte-exact golden" in readme.lower()


# --- golden regression (needs the local data lake) ----------------------------------


def _skip_if_unverifiable(spec: ScriptSpec) -> None:
    """Skip where the baseline cannot be meaningfully compared.

    On a hosted runner that is always: line endings and pinned-by-accident
    package versions differ from the machine that froze the baseline (see the
    module docstring). Locally it is only when the declared inputs are absent
    entirely — a changed input is a failure, which is the whole point.
    """
    if os.environ.get("CI"):
        pytest.skip(f"{spec.name}: frozen baselines are a local gate (CI runner)")
    if not baseline.inputs_present(spec, ROOT):
        pytest.skip(f"{spec.name}: declared inputs absent (no local data lake)")


@pytest.mark.slow
@pytest.mark.parametrize("spec", GATED_SPECS, ids=GATED_IDS)
def test_golden_stdout(spec: ScriptSpec) -> None:
    _skip_if_unverifiable(spec)
    golden = ROOT / spec.golden_path
    assert golden.exists(), (
        f"no frozen golden for {spec.name}. "
        "Run scripts/freeze_research_baseline.py --write deliberately."
    )

    expected = baseline.read_golden(spec, ROOT)
    actual = baseline.run_script(spec, ROOT)
    if actual == expected:
        return

    lines = [
        f"GOLDEN MISMATCH for {spec.name} ({spec.hypotheses}) — STOP.",
        "Investigate the semantic difference. Do NOT update the golden to make",
        "this pass: a changed golden is a change to research history.",
        "",
        "Numeric differences:",
    ]
    lines.extend(f"  {d}" for d in baseline.numeric_differences(expected, actual))
    pytest.fail("\n".join(lines))


@pytest.mark.slow
@pytest.mark.parametrize("spec", baseline.SPECS, ids=IDS)
def test_frozen_fingerprint_categories(spec: ScriptSpec) -> None:
    """Inputs, config, environment and RNG must be unchanged.

    ``code`` is intentionally excluded — Layer 1 changes code on purpose.
    """
    _skip_if_unverifiable(spec)
    stored = _stored_fingerprints().get(spec.name)
    assert stored is not None, f"no frozen fingerprint for {spec.name}"

    report = baseline.compare_fingerprints(stored, baseline.fingerprint(spec, ROOT))
    frozen_hits = {c: report[c] for c in baseline.FROZEN_CATEGORIES if c in report}
    if not frozen_hits:
        return

    lines = [
        f"FROZEN FINGERPRINT CHANGED for {spec.name} — the baseline is no longer valid.",
        "This is NOT a code problem; the goldens were produced against different",
        "inputs/config/environment/RNG and cannot be trusted until re-frozen",
        "deliberately.",
        "",
    ]
    for category, differences in frozen_hits.items():
        lines.append(f"{category}:")
        lines.extend(f"  {d}" for d in differences[:10])
        if len(differences) > 10:
            lines.append(f"  ... {len(differences) - 10} more")
    pytest.fail("\n".join(lines))
