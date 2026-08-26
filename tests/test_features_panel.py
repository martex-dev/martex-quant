"""Semantic distinctions in the canonical panel layer.

One test per difference the audit found (docs/research/mi-layer1-panel-audit.md).
The 30 golden fixtures are the end-to-end proof that migration changed no
published number; these tests pin down WHY each parameter exists, so a future
edit that collapses a distinction fails here with an explanatory name.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from martex_quant.data.models import OHLCV_SCHEMA, Interval
from martex_quant.data.store.parquet_store import ParquetStore
from martex_quant.features.diagnostics import compare_panels, format_comparison, panel_signature
from martex_quant.features.panel import (
    CACHE_DAY_DTYPE,
    Feature,
    align_day_to_cache_precision,
    amihud_illiquidity,
    daily_panel,
    forward_return,
    momentum,
    momentum_skip,
    relative_forward_return_difference,
    relative_forward_return_ratio,
    rolling_mean_of,
    trailing_percentile_rank,
    true_range,
    vol_excl_current,
    vol_incl_current,
)


def _write_symbol(store: ParquetStore, symbol: str, closes: list[float]) -> None:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    frame = pl.DataFrame(
        {
            "timestamp": [start + timedelta(days=i) for i in range(len(closes))],
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [100.0 + i for i in range(len(closes))],
        },
        schema=OHLCV_SCHEMA,
    )
    store.write(frame, symbol, Interval.D1)


@pytest.fixture
def store(tmp_path: Path) -> ParquetStore:
    s = ParquetStore(tmp_path / "lake")
    # A deliberate spike at index 20 so an including/excluding-current
    # volatility window disagrees visibly.
    closes = [100.0 + i for i in range(40)]
    closes[20] = 160.0
    _write_symbol(s, "AAAUSDT", closes)
    _write_symbol(s, "BBBUSDT", [50.0 + 2 * i for i in range(25)])
    return s


# --- the distinction that must never collapse ----------------------------------------


def test_vol_excl_and_incl_current_are_different_features(store: ParquetStore) -> None:
    """The measured non-equivalence from the audit, in miniature.

    If these ever agree, someone has merged the two conventions and H24's
    riskadj and H27's low-vol ranking have silently changed.
    """
    panel = daily_panel(
        store,
        ["AAAUSDT"],
        base_columns=("close", "ret"),
        feature_stages=[
            [
                vol_excl_current(5, name="vol_excl"),
                vol_incl_current(5, name="vol_incl"),
            ]
        ],
        on_missing_symbol="raise",
    ).drop_nulls(["vol_excl", "vol_incl"])

    assert panel.height > 0
    differences = (panel["vol_excl"] - panel["vol_incl"]).abs()
    assert differences.max() > 0.0
    # And the excluding variant is exactly the including variant shifted —
    # the whole difference is whether today's return is in the window.
    manual = panel.with_columns(
        check=pl.col("ret").shift(1).rolling_std(5),
    )
    assert manual.select((pl.col("vol_excl") == pl.col("check")).all()).item()


def test_there_is_no_ambiguous_volatility_constructor() -> None:
    """Guards the API shape itself: a bare vol()/volatility() would let a
    caller pick a convention by accident."""
    import martex_quant.features.panel as panel_module

    assert not hasattr(panel_module, "volatility")
    assert not hasattr(panel_module, "vol")


def test_volatility_constructors_require_an_explicit_name() -> None:
    with pytest.raises(TypeError):
        vol_excl_current(30)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        vol_incl_current(90)  # type: ignore[call-arg]


# --- feature definitions --------------------------------------------------------------


def test_momentum_and_forward_return_definitions(store: ParquetStore) -> None:
    panel = daily_panel(
        store,
        ["AAAUSDT"],
        base_columns=("close",),
        feature_stages=[[momentum(3), forward_return(2), momentum_skip(5, 2)]],
        on_missing_symbol="raise",
    )
    closes = panel["close"].to_list()
    assert panel["r3"][10] == pytest.approx(closes[10] / closes[7] - 1.0)
    assert panel["fwd2"][10] == pytest.approx(closes[12] / closes[10] - 1.0)
    assert panel["r5skip2"][10] == pytest.approx(closes[8] / closes[5] - 1.0)
    # Forward returns are null at the tail, never wrapped or zero-filled.
    assert panel["fwd2"][-1] is None


def test_amihud_uses_close_times_volume_as_published(store: ParquetStore) -> None:
    """Correction candidate 2: preserved exactly, not switched to a
    textbook dollar-volume denominator."""
    panel = daily_panel(
        store,
        ["AAAUSDT"],
        base_columns=("close", "volume", "ret"),
        feature_stages=[[amihud_illiquidity(3, name="illiq3")]],
        on_missing_symbol="raise",
    )
    rows = panel.drop_nulls(["illiq3"]).head(1).to_dicts()[0]
    idx = panel["illiq3"].to_list().index(rows["illiq3"])
    manual = [
        abs(panel["ret"][i]) / (panel["close"][i] * panel["volume"][i])
        for i in range(idx - 2, idx + 1)
    ]
    assert rows["illiq3"] == pytest.approx(sum(manual) / 3)


# --- assembly semantics ---------------------------------------------------------------


def test_base_column_order_is_preserved(store: ParquetStore) -> None:
    """h13_h14 selects ret BEFORE close; the others after. Output column
    order is an observable of each historical panel."""
    ret_first = daily_panel(
        store,
        ["AAAUSDT"],
        base_columns=("ret", "close"),
        feature_stages=[],
        on_missing_symbol="raise",
    )
    close_first = daily_panel(
        store,
        ["AAAUSDT"],
        base_columns=("close", "ret"),
        feature_stages=[],
        on_missing_symbol="raise",
    )
    assert ret_first.columns == ["day", "ret", "close", "symbol"]
    assert close_first.columns == ["day", "close", "ret", "symbol"]


def test_feature_stages_run_in_order_so_atr_can_read_tr(store: ParquetStore) -> None:
    """h33_40's atr14 reads the tr column a previous with_columns produced.
    A single flattened stage would raise ColumnNotFound."""
    panel = daily_panel(
        store,
        ["AAAUSDT"],
        base_columns=("close", "high", "low", "ret"),
        feature_stages=[[true_range()], [rolling_mean_of("tr", 4, name="atr4")]],
        on_missing_symbol="raise",
    )
    assert panel["atr4"].drop_nulls().len() > 0

    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        daily_panel(
            store,
            ["AAAUSDT"],
            base_columns=("close", "high", "low", "ret"),
            feature_stages=[[true_range(), rolling_mean_of("tr", 4, name="atr4")]],
            on_missing_symbol="raise",
        )


def test_missing_symbol_policy(store: ParquetStore) -> None:
    skipped = daily_panel(
        store,
        ["AAAUSDT", "NOPEUSDT"],
        base_columns=("close",),
        feature_stages=[],
        on_missing_symbol="skip",
    )
    assert skipped["symbol"].unique().to_list() == ["AAAUSDT"]

    with pytest.raises(FileNotFoundError):
        daily_panel(
            store,
            ["AAAUSDT", "NOPEUSDT"],
            base_columns=("close",),
            feature_stages=[],
            on_missing_symbol="raise",
        )


def test_drop_nulls_is_applied_once_after_concat(store: ParquetStore) -> None:
    kept = daily_panel(
        store,
        ["AAAUSDT", "BBBUSDT"],
        base_columns=("close", "ret"),
        feature_stages=[[momentum(3)]],
        on_missing_symbol="raise",
    )
    dropped = daily_panel(
        store,
        ["AAAUSDT", "BBBUSDT"],
        base_columns=("close", "ret"),
        feature_stages=[[momentum(3)]],
        on_missing_symbol="raise",
        drop_nulls=("r3",),
    )
    # Three leading nulls per symbol, and both symbols survive the drop.
    assert kept.height - dropped.height == 6
    assert sorted(dropped["symbol"].unique().to_list()) == ["AAAUSDT", "BBBUSDT"]


def test_windows_are_computed_per_symbol_not_across_the_concatenated_frame(
    store: ParquetStore,
) -> None:
    """The invariant that makes every historical panel correct.

    Computing r3 after concatenation would let BBBUSDT's first rows read
    AAAUSDT's last closes. The per-symbol loop makes that impossible.
    """
    panel = daily_panel(
        store,
        ["AAAUSDT", "BBBUSDT"],
        base_columns=("close",),
        feature_stages=[[momentum(3)]],
        on_missing_symbol="raise",
    )
    second = panel.filter(pl.col("symbol") == "BBBUSDT")
    assert second["r3"].head(3).null_count() == 3

    leaked = panel.select("close").with_columns(
        r3_global=pl.col("close") / pl.col("close").shift(3) - 1.0
    )
    boundary = panel.filter(pl.col("symbol") == "AAAUSDT").height
    assert leaked["r3_global"][boundary] is not None  # the leak we avoid


def test_per_symbol_hook_runs_before_the_symbol_tag(store: ParquetStore) -> None:
    def add_flag(frame: pl.DataFrame) -> pl.DataFrame:
        assert "symbol" not in frame.columns
        return frame.with_columns(flag=pl.lit(1))

    panel = daily_panel(
        store,
        ["AAAUSDT"],
        base_columns=("close",),
        feature_stages=[],
        on_missing_symbol="raise",
        per_symbol_hook=add_flag,
    )
    assert panel.columns == ["day", "close", "flag", "symbol"]


# --- trailing percentile rank ---------------------------------------------------------


def test_trailing_percentile_ranks_against_window_plus_one_observations() -> None:
    """Correction candidate 3: a 'window of 3' ranks against 4 values,
    because the span is values[i-3 : i+1]. Consistent in all six historical
    copies and preserved."""
    values: list[float | None] = [1.0, 2.0, 3.0, 4.0, 0.5]
    ranks = trailing_percentile_rank(values, window=3, skip_nulls=False)
    assert ranks[:3] == [None, None, None]
    assert ranks[3] == pytest.approx(4 / 4)  # 4.0 is >= all of [1,2,3,4]
    assert ranks[4] == pytest.approx(1 / 4)  # 0.5 beats only itself in [2,3,4,0.5]


def test_trailing_percentile_skip_nulls_changes_the_denominator() -> None:
    """h13_h14's copy is the only one that filters nulls out of the window,
    which changes the denominator, and returns None for a null value."""
    values: list[float | None] = [1.0, None, 3.0, 4.0, 2.0]
    skipping = trailing_percentile_rank(values, window=3, skip_nulls=True)
    assert skipping[1] is None  # current value is None
    assert skipping[3] == pytest.approx(3 / 3)  # window [1,None,3,4] -> [1,3,4]
    assert skipping[4] == pytest.approx(1 / 3)  # window [None,3,4,2] -> [3,4,2]

    not_skipping = trailing_percentile_rank(values, window=3, skip_nulls=False)
    assert not_skipping[3] == pytest.approx(3 / 4)  # None stays in the denominator
    assert skipping[3] != not_skipping[3]


def test_feature_is_a_plain_named_expression() -> None:
    f = momentum(7)
    assert isinstance(f, Feature)
    assert f.name == "r7"


# --- timestamp precision (cache provenance, not a bug to fix) ------------------------


def test_align_day_to_cache_precision_preserves_the_ms_us_distinction(
    store: ParquetStore,
) -> None:
    """The lake is millisecond; the funding/perp/stream caches are microsecond.

    Both precisions are real. The helper exists so the cast is named and its
    reason visible, NOT so one precision can be normalised away.
    """
    lake_native = daily_panel(
        store,
        ["AAAUSDT"],
        base_columns=("close",),
        feature_stages=[],
        on_missing_symbol="raise",
    )
    assert lake_native.schema["day"] == pl.Datetime("ms", "UTC")

    cache_aligned = align_day_to_cache_precision(lake_native)
    assert cache_aligned.schema["day"] == CACHE_DAY_DTYPE
    assert cache_aligned.schema["day"] == pl.Datetime("us", "UTC")

    # Same instants, different precision — no value is altered by the cast.
    assert cache_aligned["day"].dt.timestamp("ms").to_list() == (
        lake_native["day"].dt.timestamp("ms").to_list()
    )


def test_joining_across_precisions_without_aligning_yields_nothing(
    store: ParquetStore,
) -> None:
    """Why the cast exists at all: polars will not match ms against us, so an
    unaligned join is silently empty rather than an error."""
    ms_frame = daily_panel(
        store,
        ["AAAUSDT"],
        base_columns=("close",),
        feature_stages=[],
        on_missing_symbol="raise",
    ).select("day", "close")
    us_frame = align_day_to_cache_precision(ms_frame).rename({"close": "cached_close"})

    with pytest.raises(pl.exceptions.SchemaError):
        ms_frame.join(us_frame, on="day", how="inner")

    aligned = align_day_to_cache_precision(ms_frame).join(us_frame, on="day", how="inner")
    assert aligned.height == ms_frame.height


# --- structural diagnostics ----------------------------------------------------------


def test_panel_signature_captures_the_protected_invariants(store: ParquetStore) -> None:
    panel = daily_panel(
        store,
        ["AAAUSDT", "BBBUSDT"],
        base_columns=("close", "ret"),
        feature_stages=[[momentum(3)]],
        on_missing_symbol="raise",
    )
    signature = panel_signature(panel)
    assert signature["rows"] == panel.height
    assert signature["columns"] == ["day", "close", "ret", "r3", "symbol"]
    assert signature["dtypes"]["day"] == "Datetime(time_unit='ms', time_zone='UTC')"
    assert signature["null_counts"]["r3"] == 6  # three leading nulls per symbol
    assert signature["n_symbols"] == 2
    assert signature["symbols"] == ["AAAUSDT", "BBBUSDT"]
    assert "first_day" in signature and "last_day" in signature


def test_compare_panels_is_silent_on_identical_panels(store: ParquetStore) -> None:
    def build() -> pl.DataFrame:
        return daily_panel(
            store,
            ["AAAUSDT"],
            base_columns=("close", "ret"),
            feature_stages=[[momentum(3)]],
            on_missing_symbol="raise",
        )

    assert compare_panels(build(), build()) == []


def test_compare_panels_names_a_drop_nulls_placement_change(store: ParquetStore) -> None:
    """The diagnostic a stdout golden cannot give you: WHICH property moved."""
    kwargs: dict[str, object] = {
        "base_columns": ("close", "ret"),
        "feature_stages": [[momentum(3)]],
        "on_missing_symbol": "raise",
    }
    inside = daily_panel(store, ["AAAUSDT"], drop_nulls=("r3",), **kwargs)  # type: ignore[arg-type]
    outside = daily_panel(store, ["AAAUSDT"], **kwargs)  # type: ignore[arg-type]

    differences = compare_panels(outside, inside)
    assert any(d.startswith("rows:") for d in differences)
    assert any(d.startswith("null_counts:") for d in differences)
    assert "structural difference" in format_comparison(differences)


def test_compare_panels_names_the_volatility_convention(store: ParquetStore) -> None:
    kwargs: dict[str, object] = {
        "base_columns": ("close", "ret"),
        "on_missing_symbol": "raise",
    }
    excl = daily_panel(
        store, ["AAAUSDT"], feature_stages=[[vol_excl_current(5, name="vol5")]], **kwargs
    )  # type: ignore[arg-type]
    incl = daily_panel(
        store, ["AAAUSDT"], feature_stages=[[vol_incl_current(5, name="vol5")]], **kwargs
    )  # type: ignore[arg-type]

    differences = compare_panels(excl, incl)
    assert differences, "the two conventions must not compare equal"
    assert any("vol5" in d for d in differences)


# --- forward returns: equivalence with the historical expressions ---------------------


def _pair_frame() -> pl.DataFrame:
    rng = random.Random(4)
    a, b = [100.0], [50.0]
    for _ in range(59):
        a.append(a[-1] * (1.0 + rng.gauss(0.004, 0.03)))
        b.append(b[-1] * (1.0 + rng.gauss(0.002, 0.02)))
    return pl.DataFrame({"close": a, "close_b": b, "eth": a, "btc": b, "alt": b})


@pytest.mark.parametrize(
    ("horizon", "price_column", "name"),
    [
        (7, "close", None),  # daily panels
        (8, "close", "fwd8"),  # h44_50 H49/H50, 8 bars = 2h
        (4, "close", "fwd1h"),  # h52_55_57 H55, h53 — 4 bars named by duration
        (1, "close", "fwd15"),  # h52_55_57 H55
        (30, "btc", "btc_fwd"),  # v2_m1 quadrant table
        (30, "alt", "alt_fwd"),
    ],
)
def test_forward_return_matches_the_historical_expression(
    horizon: int, price_column: str, name: str | None
) -> None:
    frame = _pair_frame()
    historical = frame.with_columns(
        **{
            name or f"fwd{horizon}": pl.col(price_column).shift(-horizon) / pl.col(price_column)
            - 1.0
        }
    )
    feature = forward_return(horizon, price_column=price_column, name=name)
    canonical = frame.with_columns(**{feature.name: feature.expr})
    assert feature.name == (name or f"fwd{horizon}")
    assert compare_panels(historical, canonical) == []


def test_relative_ratio_matches_h33_40_and_h52_expressions() -> None:
    frame = _pair_frame()
    historical = frame.with_columns(
        fwd_ratio=(pl.col("close").shift(-7) / pl.col("close"))
        / (pl.col("close_b").shift(-7) / pl.col("close_b"))
        - 1.0
    )
    feature = relative_forward_return_ratio(
        7, numerator="close", denominator="close_b", name="fwd_ratio"
    )
    canonical = frame.with_columns(**{feature.name: feature.expr})
    assert compare_panels(historical, canonical) == []


def test_relative_difference_matches_the_v2_m1_expression() -> None:
    frame = _pair_frame()
    historical = frame.with_columns(
        fwd_rel=(pl.col("btc").shift(-30) / pl.col("btc") - 1.0)
        - (pl.col("alt").shift(-30) / pl.col("alt") - 1.0)
    )
    feature = relative_forward_return_difference(
        30, minuend="btc", subtrahend="alt", name="fwd_rel"
    )
    canonical = frame.with_columns(**{feature.name: feature.expr})
    assert compare_panels(historical, canonical) == []


def test_ratio_and_difference_are_not_the_same_quantity() -> None:
    """ratio = (r_a - r_b)/(1 + r_b); difference = r_a - r_b.

    Equal only when r_b == 0. Substituting one for the other would silently
    change H35, H56 or the V2 dominance study.
    """
    frame = _pair_frame()
    ratio = relative_forward_return_ratio(7, numerator="eth", denominator="btc", name="x")
    difference = relative_forward_return_difference(7, minuend="eth", subtrahend="btc", name="x")
    both = frame.with_columns(as_ratio=ratio.expr, as_difference=difference.expr).drop_nulls(
        ["as_ratio", "as_difference"]
    )
    gap = (both["as_ratio"] - both["as_difference"]).abs().max()
    assert gap is not None and float(gap) > 1e-3

    # And the exact algebraic relationship, so the distinction is documented
    # rather than merely asserted.
    check = both.with_columns(
        r_a=pl.col("eth").shift(-7) / pl.col("eth") - 1.0,
        r_b=pl.col("btc").shift(-7) / pl.col("btc") - 1.0,
    ).drop_nulls(["r_a", "r_b"])
    expected = (check["r_a"] - check["r_b"]) / (1.0 + check["r_b"])
    assert (check["as_ratio"] - expected).abs().max() == pytest.approx(0.0, abs=1e-12)


def test_forward_return_leaves_trailing_nulls_and_never_fills() -> None:
    frame = _pair_frame()
    feature = forward_return(5)
    out = frame.with_columns(**{feature.name: feature.expr})
    assert out["fwd5"].tail(5).null_count() == 5
    assert out["fwd5"].head(frame.height - 5).null_count() == 0
