"""Frozen research baseline: golden stdout plus input fingerprints.

MI Lab Layer 1 consolidates duplicated analytical machinery (6 panel
builders, 16 bootstrap definitions, 11 forward-return definitions). Before
any of that moves, this module freezes what the research scripts print
TODAY and fingerprints everything that could make them print something
else.

Coverage is the WHOLE research corpus (30 scripts), not only the scripts
Layer 1 edits. The original plan covered 13; the integrity test
``test_every_research_script_has_a_spec`` failed on first run and exposed
five strategy-grade studies carrying the ledger's DSR 0.990/0.992/1.000.
The acceptance criterion is "no ledger value changed" — so everything that
produces a ledger value is frozen.

Why the fingerprint is not optional: ``.gitignore`` excludes ``/data/``
entirely, so the lake, the funding/perp caches and the intraday panels
have NO git history. The goldens are therefore reproducible only as long
as those files stay byte-identical, and this fingerprint is the only
record of what produced them.

The fingerprint separates five causes of a golden mismatch, because
"the numbers moved" is useless without knowing why:

``code``         our source changed — EXPECTED during Layer 1
``inputs``       a data file changed — the baseline is invalid
``config``       config/universe.json changed — the baseline is invalid
``environment``  Python or a library version changed — results untrusted
``rng``          Python's RNG sequence changed — every CI is untrusted

Only ``code`` may differ while the goldens still mean something. That is
the entire point of the refactor: change the code, keep the numbers.

Nothing here writes a golden. Freezing is a deliberate act performed by
``scripts/freeze_research_baseline.py`` with an explicit flag, because
updating a golden is a change to research history, not a test fixup.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

import polars as pl

from martex_quant.data.models import Interval
from martex_quant.data.store.parquet_store import ParquetStore

GOLDEN_DIR = Path("tests") / "golden"
FINGERPRINT_FILE = "fingerprints.json"
SCRIPT_DIR = Path("scripts")

# Libraries whose version could plausibly move a number. Recorded, not pinned.
_TRACKED_DISTRIBUTIONS = ("polars", "pyarrow", "pydantic", "ccxt", "numpy")

# The RNG probe: a fixed draw sequence that changes if CPython's Mersenne
# Twister or randint ever changes behaviour. Every published CI depends on
# this sequence, so it is fingerprinted explicitly.
_RNG_PROBE_SEED = 20260810
_RNG_PROBE_DRAWS = 512
_RNG_PROBE_HI = 9_999

# Pinned so hash()-derived seeds are stable; see run_script and
# REPRODUCIBILITY_DEFECTS below.
PYTHON_HASH_SEED = "0"

# Defects found while freezing the baseline. Recorded, NOT fixed: correcting
# them would change a published number, which Layer 1 is forbidden to do.
# Each is a candidate for a separate, pre-registered correction.
REPRODUCIBILITY_DEFECTS: dict[str, str] = {
    "adaptive_sizing_study": (
        "Seeds its Monte Carlo with random.Random(hash(name) % 100_000). "
        "CPython randomises str hashing per process, so the study's PUBLISHED "
        "digits can never be reproduced exactly — repeated runs moved pass "
        "rates by roughly 0.5pp (e.g. static 0.85x: 61.5% / 62.4% / 61.7%). "
        "The qualitative finding it supports ('adaptive sizing does not beat "
        "the static frontier') is stable across seeds; the exact figures are "
        "not. Its golden is therefore a FORWARD-LOOKING baseline captured "
        "under PYTHONHASHSEED=0, not a reproduction of history. "
        "Correction candidate: take an explicit seed parameter."
    ),
    "phase3_studies": (
        "The H05 carry sub-study (scripts/phase3_studies.py:184) anchors its "
        "funding-history fetch to datetime.now(tz=UTC) - 4 years AND pulls "
        "live from Binance, so its window slides by one day every day and it "
        "requires network access. Frozen 2026-08-10; on 2026-08-11 five of "
        "its 100 lines changed — the window 2022-08-11..2026-08-10 became "
        "2022-08-12..2026-08-11, moving DOGE's annualized carry 7.87% -> "
        "7.86%. Lines 1-91 (Studies 2-7: daily TSMOM, vol-filter, mean "
        "reversion, vol-target, Donchian) are byte-identical and reproduce "
        "exactly; only the carry section drifts. "
        "Correction candidate: pin the carry window to an explicit date "
        "range and read from a cache, as h08/h10 already do for funding. "
        "That WOULD change the published carry figures, so it needs its own "
        "pre-registration and is out of Layer 1's scope."
    ),
}

LEGACY8 = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "LTCUSDT",
)
INTRADAY_15M = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "LTCUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "TRXUSDT",
    "PEPEUSDT",
)
INTRADAY_TAKER = INTRADAY_15M[:-1]  # h53 excludes PEPEUSDT
H44_FUNDING = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT")
V2_ALTS = ("ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LTCUSDT")

# Derived equity streams cached by h41_h42_fub1_studies and consumed by the
# combo / fade / sprint studies. They are INPUTS to those scripts but are
# themselves computed artifacts — a reproducibility weak point recorded in
# docs/research/mi-layer1-consolidation-plan.md.
STREAM_CACHE = (
    "data/tmp/h4x_streams/v1_stream.parquet",
    "data/tmp/h4x_streams/v1_stop_stream.parquet",
    "data/tmp/h4x_streams/rot_champion_stream.parquet",
    "data/tmp/h4x_streams/rot_stop_stream.parquet",
    "data/tmp/h4x_streams/blend_stream.parquet",
)


# How reproducible a script actually is. This is a property of the SCRIPT,
# not of our test harness, and it is declared rather than discovered so the
# registry cannot quietly misrepresent a fixture.
#
# "deterministic"
#     Same inputs -> same stdout, forever. A byte-exact golden IS a
#     historical reproduction. 28 of the 30 scripts.
#
# "non_deterministic_pinned"
#     The script's own output is not reproducible (adaptive_sizing_study
#     seeds from hash(str)), but pinning the environment makes it stable
#     GOING FORWARD. Its golden is gated, but it is a forward-looking
#     baseline and must never be described as reproducing history.
#
# "time_dependent"
#     Output depends on wall-clock time and/or a live network fetch, so no
#     byte-exact golden can be permanent. Still run and audited — exit
#     status, input fingerprints — but deliberately NOT stdout-gated.
Reproducibility = Literal["deterministic", "non_deterministic_pinned", "time_dependent"]


@dataclass(frozen=True)
class ScriptSpec:
    """One research script and everything it reads.

    Inputs are declared by hand rather than discovered, so that the
    declaration itself is reviewable: a missing input is a visible gap in
    this table, not a silent hole in the fingerprint.
    """

    name: str  # script stem under scripts/
    hypotheses: str  # which ledger entries this script produced
    seeds: tuple[int, ...]  # RNG seeds used, for audit
    daily_symbols: tuple[str, ...] = ()  # read from the lake at 1d
    hourly_symbols: tuple[str, ...] = ()  # read from the lake at 1h
    uses_universe: bool = False  # reads config/universe.json for its symbols
    data_files: tuple[str, ...] = ()  # explicit repo-relative paths
    args: tuple[str, ...] = ()  # CLI arguments the script requires
    reproducibility: Reproducibility = "deterministic"
    external_dependencies: tuple[str, ...] = ()  # live/network/clock inputs
    seed_note: str = ""

    @property
    def script_path(self) -> Path:
        return SCRIPT_DIR / f"{self.name}.py"

    @property
    def golden_path(self) -> Path:
        return GOLDEN_DIR / f"{self.name}.out"

    @property
    def requires_exact_stdout(self) -> bool:
        """Whether a byte-exact stdout golden is meaningful for this script."""
        return self.reproducibility != "time_dependent"


def _funding(symbols: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"data/funding/{s}.parquet" for s in symbols)


def _perp(symbols: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"data/perp/{s}.parquet" for s in symbols)


def _intraday(symbols: tuple[str, ...], suffix: str) -> tuple[str, ...]:
    return tuple(f"data/intraday/{s}_{suffix}.parquet" for s in symbols)


SPECS: tuple[ScriptSpec, ...] = (
    ScriptSpec(
        name="h08_funding_killtest",
        hypotheses="H08",
        seeds=(8,),
        daily_symbols=LEGACY8,
        data_files=_funding(LEGACY8),
    ),
    ScriptSpec(
        name="h09_calendar_killtest",
        hypotheses="H09",
        seeds=(9,),
        daily_symbols=LEGACY8,
        hourly_symbols=LEGACY8,
    ),
    ScriptSpec(
        name="h10_basis_killtest",
        hypotheses="H10",
        seeds=(10,),
        daily_symbols=LEGACY8,
        data_files=_perp(LEGACY8),
    ),
    ScriptSpec(
        name="h11_rotation_killtest",
        hypotheses="H11",
        seeds=(11,),
        daily_symbols=LEGACY8,
    ),
    ScriptSpec(
        name="h13_h14_killtests",
        hypotheses="H13, H14",
        seeds=(13, 14, 15, 16, 141),
        daily_symbols=LEGACY8,
        seed_note="H13 uses seed=13+i for i in 0..3 (13,14,15,16); H14 uses Random(14) and 141.",
    ),
    ScriptSpec(
        name="h15_21_killtests",
        hypotheses="H15-H21",
        seeds=(151, 152, 161, 162, 163, 171, 181, 182, 191, 192, 201, 202, 203, 211),
        hourly_symbols=LEGACY8,
        uses_universe=True,
    ),
    ScriptSpec(
        name="h22_h23_studies",
        hypotheses="H22, H23",
        seeds=(22, 231, 232),
        uses_universe=True,
        data_files=_funding(LEGACY8),
    ),
    ScriptSpec(
        name="h24_32_killtests",
        hypotheses="H24-H32",
        seeds=(2401, 2402, 2410, 2510, 2610, 2710, 2810, 2910, 3010, 3110, 3210),
        uses_universe=True,
    ),
    ScriptSpec(
        name="h33_40_killtests",
        hypotheses="H33-H40",
        seeds=(3310, 3410, 3510, 3610, 3710, 3810, 3910, 4010),
        uses_universe=True,
        data_files=_perp(LEGACY8),
    ),
    ScriptSpec(
        name="h44_50_killtests",
        hypotheses="H44-H50",
        seeds=(4410, 4510, 4610, 4710, 4810, 4910, 5010),
        data_files=_intraday(INTRADAY_15M, "15m") + _funding(H44_FUNDING),
    ),
    ScriptSpec(
        name="h52_55_57_studies",
        hypotheses="H52, H55, H56, H57",
        seeds=(5510, 5511, 5610, 5710),
        data_files=_intraday(INTRADAY_15M, "15m")
        + ("data/tmp/h4x_streams/rot_stop_stream.parquet",),
        seed_note=(
            "H52 uses no RNG (deterministic fill replay). NOTE: "
            "rot_stop_stream.parquet is a DERIVED cache from an earlier run, "
            "not raw data — see the Layer 1 plan's reproducibility caveat."
        ),
    ),
    ScriptSpec(
        name="h53_killtest",
        hypotheses="H53",
        seeds=(5310,),
        data_files=_intraday(INTRADAY_TAKER, "tb15m"),
    ),
    ScriptSpec(
        name="v2_m1_killtest",
        hypotheses="V2-M1",
        seeds=(11,),
        daily_symbols=("BTCUSDT",) + V2_ALTS,
        seed_note="Block length is 60 days here, not the usual 30.",
    ),
    # --- strategy-grade studies ------------------------------------------------
    # These produce the DSR figures the ledger's validated specs rest on. They
    # do not use the duplicated bootstrap machinery (verified: no RNG at all),
    # so Layer 1 will not touch them — but they are frozen anyway, because the
    # acceptance criterion is "no ledger value changed", and these ARE the
    # ledger values.
    ScriptSpec(
        name="h11_strategy_study",
        hypotheses="H11 strategy grade",
        seeds=(),
        daily_symbols=LEGACY8,
    ),
    ScriptSpec(
        name="h12_combined_study",
        hypotheses="H12",
        seeds=(),
        daily_symbols=LEGACY8,
    ),
    ScriptSpec(
        name="h41_h42_fub1_studies",
        hypotheses="H41, H42a, H42b, FU-B1",
        seeds=(),
        daily_symbols=LEGACY8,
        uses_universe=True,
        data_files=STREAM_CACHE,
        seed_note=(
            "PRODUCES the data/tmp/h4x_streams caches that h43/h51/h52 and the "
            "sprint studies consume; recomputes and rewrites them when absent."
        ),
    ),
    ScriptSpec(
        name="h43_combo_study",
        hypotheses="H43, H43a",
        seeds=(),
        uses_universe=True,
        data_files=(
            "data/tmp/h4x_streams/v1_stream.parquet",
            "data/tmp/h4x_streams/rot_champion_stream.parquet",
            "data/tmp/h4x_streams/rot_stop_stream.parquet",
        ),
    ),
    ScriptSpec(
        name="h62_carry_study",
        hypotheses="H62 delta-neutral funding carry (trial 126)",
        seeds=(20260827,),
        uses_universe=False,
        # Its universe is the 8-symbol list FIXED by the pre-registration,
        # not config/universe.json. Fingerprinting the three input caches is
        # what makes a data refresh visible: funding and perp are static
        # files outside the lake's catalog/validation path.
        data_files=(
            "data/funding/BTCUSDT.parquet",
            "data/perp/BTCUSDT.parquet",
            "data/tmp/h4x_streams/rot_stop_stream.parquet",
        ),
        seed_note=(
            "Block bootstrap seeded 20260827 via stats.bootstrap.daily_mean_ci. "
            "The carry engine itself is deterministic -- no RNG."
        ),
    ),
    ScriptSpec(
        name="h43a_bounce_census",
        hypotheses="H43a bounce-day census (descriptive, 0 trials)",
        seeds=(),
        uses_universe=True,
        data_files=("data/tmp/h4x_streams/rot_stop_stream.parquet",),
        seed_note=(
            "No RNG: pure description over the cached H43a book. Rebuilds it "
            "with h43_combo_study's construction and refuses to print if the "
            "published 317 bounce days / 82% mean idle do not reproduce."
        ),
    ),
    ScriptSpec(
        name="h51_fade_study",
        hypotheses="H51a, H51b",
        seeds=(),
        data_files=_intraday(INTRADAY_15M, "15m")
        + ("data/tmp/h4x_streams/rot_stop_stream.parquet",),
    ),
    # --- phase studies and selection --------------------------------------------
    ScriptSpec(
        name="tsmom_study",
        hypotheses="H01 (TSMOM 1h)",
        seeds=(),
        hourly_symbols=LEGACY8,
    ),
    ScriptSpec(
        name="phase3_studies",
        hypotheses="H02-H07",
        seeds=(),
        daily_symbols=LEGACY8,
        hourly_symbols=LEGACY8,
        args=("--study", "all"),
        reproducibility="time_dependent",
        external_dependencies=(
            "datetime.now(tz=UTC) - 4 years anchors the H05 carry window",
            "live Binance funding-history fetch via ccxt (binanceusdm)",
        ),
        seed_note=(
            "Slowest script in the baseline (~4 minutes). Studies 2-7 are "
            "deterministic and reproduce byte-exactly; the H05 carry section "
            "is not, so the script as a whole cannot hold a permanent golden."
        ),
    ),
    ScriptSpec(
        name="phase3_verdict",
        hypotheses="Phase 3 verdict",
        seeds=(),
        daily_symbols=LEGACY8,
    ),
    ScriptSpec(
        name="wide_rotation_study",
        hypotheses="H11 wide universe (rotation DSR 0.990)",
        seeds=(),
        uses_universe=True,
    ),
    ScriptSpec(
        name="final_selection",
        hypotheses="Final selection",
        seeds=(),
        daily_symbols=LEGACY8,
    ),
    # --- prop-firm simulation ----------------------------------------------------
    ScriptSpec(
        name="phase4_propsim",
        hypotheses="Phase 4 prop simulation",
        seeds=(),
        daily_symbols=LEGACY8,
        seed_note="Monte Carlo seeded inside martex_quant.risk_management.prop_sim.",
    ),
    ScriptSpec(
        name="phase5_realfirm",
        hypotheses="Phase 5 real-firm rules",
        seeds=(),
        daily_symbols=LEGACY8,
    ),
    ScriptSpec(
        name="july_sprint_study",
        hypotheses="July sprint sizing",
        seeds=(),
        uses_universe=True,
        data_files=("data/tmp/h4x_streams/rot_stop_stream.parquet",),
    ),
    ScriptSpec(
        name="firm_choice_study",
        hypotheses="Firm choice",
        seeds=(),
        uses_universe=True,
        data_files=("data/tmp/h4x_streams/rot_stop_stream.parquet",),
        seed_note="Imports build_streams from july_sprint_study; same inputs.",
    ),
    ScriptSpec(
        name="owncap_sizing_study",
        hypotheses="Own-capital sizing",
        seeds=(),
        uses_universe=True,
        data_files=("data/tmp/h4x_streams/rot_stop_stream.parquet",),
    ),
    ScriptSpec(
        name="adaptive_sizing_study",
        hypotheses="Adaptive sizing (negative result)",
        seeds=(),
        uses_universe=True,
        data_files=("data/tmp/h4x_streams/rot_stop_stream.parquet",),
        reproducibility="non_deterministic_pinned",
        external_dependencies=("CPython per-process hash randomisation (seeds from hash(str))",),
        seed_note=(
            "Imports build_streams from july_sprint_study; same inputs. Its "
            "golden is a FORWARD-LOOKING baseline captured under "
            "PYTHONHASHSEED=0, never a reproduction of the published figures."
        ),
    ),
    ScriptSpec(
        name="single_attempt_study",
        hypotheses="Single-attempt revision (canonical eval config)",
        seeds=(),
        uses_universe=True,
        data_files=("data/tmp/h4x_streams/rot_stop_stream.parquet",),
        seed_note="Imports build_streams from july_sprint_study; same inputs.",
    ),
    ScriptSpec(
        name="research_graph_report",
        hypotheses="Stage 12 research graph over the load-bearing spine",
        seeds=(),
        uses_universe=False,
        # The graph's nodes and edges are literals that MIRROR these
        # documents. Fingerprinting them is what makes a stale graph
        # detectable: if the corpus moves and the literals do not, the
        # inputs category changes and says so.
        data_files=(
            "PROJECT_MEMORY.md",
            "docs/hypotheses/58-learned-indicator-ensemble.md",
            "docs/hypotheses/59-live-drawdown-consistency.md",
        ),
        seed_note=(
            "Pure structure: the nodes and edges are literals in the script, "
            "each citing the committed document it was read from. No market "
            "data, no RNG, no lake reads."
        ),
    ),
    ScriptSpec(
        name="dsr_recheck",
        hypotheses="Re-deflation of the momentum books at the current ledger total",
        seeds=(),
        uses_universe=True,
        data_files=(
            "data/tmp/h4x_streams/rot_stop_stream.parquet",
            "data/tmp/h4x_streams/rot_champion_stream.parquet",
        ),
        reproducibility="time_dependent",
        external_dependencies=(
            "docs/research/ledger/trials.toml — the ledger total, which changes "
            "by design whenever research is registered",
        ),
        seed_note=(
            "Classified time_dependent for the honest reason rather than the "
            "literal one: its output moves with the LEDGER, not the calendar. "
            "A golden would have to be re-frozen every time the ledger grows, "
            "and a fixture regenerated on every ledger change is not a golden. "
            "Its estimator reconstructions are themselves exact and are guarded "
            "by the script's own reproduce-first check, which refuses to report "
            "a recomputed figure when the published one cannot be reproduced."
        ),
    ),
    ScriptSpec(
        name="h59_drawdown_consistency",
        hypotheses="H59 live-vs-backtest drawdown consistency (ledger +0, diagnostic)",
        seeds=(5901, 5902, 5903),
        uses_universe=True,
        data_files=(
            "data/tmp/h4x_streams/rot_stop_stream.parquet",
            "data/tmp/h4x_streams/rot_champion_stream.parquet",
            "data/tmp/h4x_streams/v1_stream.parquet",
        ),
        reproducibility="time_dependent",
        external_dependencies=(
            "data/paper/*/equity.jsonl — the live paper record, which grows daily",
        ),
        seed_note=(
            "Genuinely time-dependent: it reads a live record that gains a mark "
            "every day, so both the live figure and the window length K move. "
            "Re-running it later answers a different question by design — the "
            "registration schedules exactly that at 60 and 90 days."
        ),
    ),
    ScriptSpec(
        name="h58_ensemble_study",
        hypotheses="H58 learned indicator ensemble (killed: equal weights won)",
        seeds=(5801, 5802, 5803, 5804, 5805, 5806),
        uses_universe=True,
        seed_note=(
            "Bootstrap seeds are per-cell and fixed in the script. sklearn's "
            "random_state is passed the same per-cell seed; lbfgs/liblinear are "
            "deterministic here regardless, so the estimates do not depend on it."
        ),
    ),
)


def spec_by_name(name: str) -> ScriptSpec:
    for spec in SPECS:
        if spec.name == name:
            return spec
    raise KeyError(f"unknown research script: {name}")


# --- fingerprint construction -------------------------------------------------------


_FILE_CACHE: dict[str, dict[str, Any]] = {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_fingerprint(path: Path) -> dict[str, Any]:
    """Hash, size, and — for parquet — row count and schema.

    Row count and schema are recorded separately from the hash because they
    say WHAT changed: a differing hash with identical rows/schema means the
    values moved, while a differing row count means the dataset grew.
    """
    key = str(path)
    cached = _FILE_CACHE.get(key)
    if cached is not None:
        return cached

    if not path.exists():
        info: dict[str, Any] = {"present": False}
    else:
        info = {
            "present": True,
            "sha256": _sha256_file(path),
            "bytes": path.stat().st_size,
        }
        if path.suffix == ".parquet":
            frame = pl.read_parquet(path)
            info["rows"] = frame.height
            info["schema"] = {name: str(dtype) for name, dtype in frame.schema.items()}
    _FILE_CACHE[key] = info
    return info


def _universe_symbols(root: Path) -> tuple[str, ...]:
    path = root / "config" / "universe.json"
    if not path.exists():
        return ()
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    symbols: list[str] = payload["symbols"]
    return tuple(symbols)


def input_paths(spec: ScriptSpec, root: Path) -> list[Path]:
    """Every file the script reads, as absolute paths, deterministically ordered."""
    store = ParquetStore(root / "data" / "lake")
    paths: list[Path] = []

    daily = spec.daily_symbols
    if spec.uses_universe:
        daily = daily + _universe_symbols(root)
    for symbol in dict.fromkeys(daily):  # de-duplicate, keep order
        paths.extend(sorted(store.dataset_dir(symbol, Interval.D1).glob("year=*/data.parquet")))
    for symbol in dict.fromkeys(spec.hourly_symbols):
        paths.extend(sorted(store.dataset_dir(symbol, Interval.H1).glob("year=*/data.parquet")))

    paths.extend(root / rel for rel in spec.data_files)
    return paths


def inputs_fingerprint(spec: ScriptSpec, root: Path) -> dict[str, Any]:
    return {
        str(path.relative_to(root).as_posix()): file_fingerprint(path)
        for path in input_paths(spec, root)
    }


def config_fingerprint(spec: ScriptSpec, root: Path) -> dict[str, Any]:
    """Configuration is fingerprinted for every script, even those that do not
    read it — a universe change must be visible everywhere it could matter."""
    path = root / "config" / "universe.json"
    if not path.exists():
        return {"config/universe.json": {"present": False}}
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return {
        "config/universe.json": {
            "present": True,
            "sha256": _sha256_file(path),
            "n_symbols": len(payload.get("symbols", [])),
            "rule": payload.get("rule", ""),
            "read_by_script": spec.uses_universe,
        }
    }


def _git_rev(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _package_sha256(root: Path) -> str:
    """One hash over all package sources — moves whenever our code moves."""
    digest = hashlib.sha256()
    package_root = root / "src" / "martex_quant"
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        digest.update(path.relative_to(package_root).as_posix().encode("utf-8"))
        digest.update(_sha256_file(path).encode("ascii"))
    return digest.hexdigest()


def code_fingerprint(spec: ScriptSpec, root: Path) -> dict[str, Any]:
    script = root / spec.script_path
    return {
        "script_sha256": _sha256_file(script) if script.exists() else "missing",
        "package_sha256": _package_sha256(root),
        "git_rev": _git_rev(root),
    }


def environment_fingerprint() -> dict[str, Any]:
    versions: dict[str, str] = {}
    for dist in _TRACKED_DISTRIBUTIONS:
        try:
            versions[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            versions[dist] = "absent"
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "python_hash_seed": PYTHON_HASH_SEED,
        "packages": versions,
    }


def rng_fingerprint() -> dict[str, Any]:
    """Hash of a fixed draw sequence.

    Every published CI is a function of ``random.Random(seed).randint``
    output. If CPython ever changes that sequence, this hash moves and every
    golden becomes untrustworthy for a reason that has nothing to do with
    our code.
    """
    rng = random.Random(_RNG_PROBE_SEED)
    draws = [rng.randint(0, _RNG_PROBE_HI) for _ in range(_RNG_PROBE_DRAWS)]
    digest = hashlib.sha256(",".join(str(d) for d in draws).encode("ascii")).hexdigest()
    return {
        "probe_seed": _RNG_PROBE_SEED,
        "n_draws": _RNG_PROBE_DRAWS,
        "upper_bound": _RNG_PROBE_HI,
        "sha256": digest,
    }


def fingerprint(spec: ScriptSpec, root: Path) -> dict[str, Any]:
    """The full five-category fingerprint for one script."""
    return {
        "script": spec.name,
        "hypotheses": spec.hypotheses,
        "reproducibility": spec.reproducibility,
        "external_dependencies": list(spec.external_dependencies),
        "seeds": list(spec.seeds),
        "seed_note": spec.seed_note,
        "code": code_fingerprint(spec, root),
        "inputs": inputs_fingerprint(spec, root),
        "config": config_fingerprint(spec, root),
        "environment": environment_fingerprint(),
        "rng": rng_fingerprint(),
        "reproducibility_defect": REPRODUCIBILITY_DEFECTS.get(spec.name, ""),
    }


# Categories that must NOT change for a golden to remain meaningful. ``code``
# is deliberately absent: changing our code while holding the numbers fixed
# is exactly what Layer 1 does.
FROZEN_CATEGORIES = ("inputs", "config", "environment", "rng")


def compare_fingerprints(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, list[str]]:
    """Per-category human-readable differences, so a failure names its cause."""
    report: dict[str, list[str]] = {}
    for category in ("code", *FROZEN_CATEGORIES):
        differences = _diff(expected.get(category), actual.get(category), category)
        if differences:
            report[category] = differences
    return report


def _diff(expected: Any, actual: Any, path: str) -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        out: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                out.append(f"{path}.{key}: ADDED ({actual[key]!r})")
            elif key not in actual:
                out.append(f"{path}.{key}: REMOVED (was {expected[key]!r})")
            else:
                out.extend(_diff(expected[key], actual[key], f"{path}.{key}"))
        return out
    if expected != actual:
        return [f"{path}: {expected!r} -> {actual!r}"]
    return []


# --- running a script ---------------------------------------------------------------


def run_script(spec: ScriptSpec, root: Path, timeout: float = 600.0) -> str:
    """Execute a research script and return its stdout, newline-normalised.

    Full environment is inherited (a stripped env breaks polars' CPU
    detection on Windows) with UTF-8 forced, because polars prints
    non-cp1252 characters and the default Windows console encoding would
    raise instead of printing.

    ``PYTHONHASHSEED`` is pinned. CPython randomises ``hash(str)`` per
    process, and ``scripts/adaptive_sizing_study.py`` seeds its Monte Carlo
    with ``hash(policy_name)`` — so that study is non-reproducible without
    this pin. Pinning is an ENVIRONMENT decision recorded in the
    fingerprint, not a code change: the script is left exactly as it ran.
    See ``REPRODUCIBILITY_DEFECTS``.
    """
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONHASHSEED": PYTHON_HASH_SEED,
    }
    completed = subprocess.run(
        [sys.executable, str(spec.script_path), *spec.args],
        cwd=root,
        capture_output=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"{spec.name} exited {completed.returncode}:\n{stderr}")
    return normalise(completed.stdout.decode("utf-8"))


def normalise(text: str) -> str:
    """CRLF -> LF so goldens compare identically regardless of git autocrlf."""
    return text.replace("\r\n", "\n")


def read_golden(spec: ScriptSpec, root: Path) -> str:
    return normalise((root / spec.golden_path).read_bytes().decode("utf-8"))


# --- structured numeric comparison --------------------------------------------------

# Stdout equality is the gate, but "the output differs" does not say WHICH
# quantity moved. These helpers extract every number so a failure can name
# the exact line and value that changed — without modifying the scripts.
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?")


@dataclass(frozen=True)
class NumericToken:
    line_no: int  # 1-indexed
    index: int  # position among numbers on that line
    text: str
    line: str


def numeric_tokens(text: str) -> list[NumericToken]:
    tokens: list[NumericToken] = []
    for line_no, line in enumerate(text.split("\n"), start=1):
        for index, match in enumerate(_NUMBER.finditer(line)):
            tokens.append(NumericToken(line_no=line_no, index=index, text=match.group(), line=line))
    return tokens


def numeric_differences(expected: str, actual: str, limit: int = 20) -> list[str]:
    """Which numbers changed, as ``line 7 value 2: -0.0187% -> -0.0190%``.

    Falls back to a structural message when the two outputs do not even have
    the same number of numeric tokens (a changed layout, not a changed value).
    """
    left, right = numeric_tokens(expected), numeric_tokens(actual)
    if len(left) != len(right):
        return [
            f"numeric token COUNT changed: {len(left)} -> {len(right)} "
            "(output structure differs, not just values)"
        ]
    out: list[str] = []
    for exp, act in zip(left, right, strict=True):
        if exp.text != act.text:
            out.append(
                f"line {exp.line_no} value {exp.index}: {exp.text} -> {act.text}"
                f"\n      expected line: {exp.line.strip()}"
                f"\n      actual   line: {act.line.strip()}"
            )
            if len(out) >= limit:
                out.append("... (further differences truncated)")
                break
    return out


def read_fingerprints(root: Path) -> dict[str, Any]:
    path = root / GOLDEN_DIR / FINGERPRINT_FILE
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def inputs_present(spec: ScriptSpec, root: Path) -> bool:
    """True when the script's declared inputs exist locally.

    CI has no market data (``/data/`` is gitignored), so the golden suite is
    a LOCAL gate. This distinguishes "no data at all" from "data changed" —
    the first is a skip, the second is a hard failure.
    """
    paths = input_paths(spec, root)
    return bool(paths) and all(path.exists() for path in paths)
