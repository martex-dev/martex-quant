# MI Lab Layer 1, Step 2 — Panel Builder Audit & Semantic-Difference Matrix

Date: 2026-08-11. Status: **AUDIT — precedes any code change.**
Governing rule: **parameterize, never normalize.**
Metric: semantic equivalence. Line count is not a success measure
(docs/research/mi-layer1-consolidation-plan.md §1.5).

---

## 1. Every panel-like construction found

The plan named six. A full sweep of the 30-script corpus found **seventeen**,
in three structurally different families. Only the first family is a
candidate for Step 2.

### Family A — long/stacked daily panels (one row per symbol-day)

| # | Location | Universe | Terminal `drop_nulls` |
|---|---|---|---|
| A1 | `h08_funding_killtest.daily_panel` | LEGACY8 | `["pct","fwd7"]` |
| A2 | `h10_basis_killtest.build_panel` | LEGACY8 | `["pct","fwd7"]` |
| A3 | `h13_h14_killtests.build_panel` | LEGACY8 | `["ret","vol30","fwd7"]` |
| A4 | `h15_21_killtests.daily_panel` | universe (40) | none |
| A5 | `h24_32_killtests.daily_panel` | universe (40) | none |
| A6 | `h33_40_killtests.daily_panel` | universe (40) | none |
| A7 | `h22_h23_studies.h23` (inline) | universe (40) | `["r90","vol30","fwd7"]` |

### Family B — wide/pivot frames (one COLUMN per symbol)

| # | Location | Join |
|---|---|---|
| B1 | `h11_rotation_killtest.main` | `how="full", coalesce=True` on timestamp |
| B2 | `h12_combined_study` | `how="inner"` |
| B3 | `h41_h42_fub1_studies` | `how="inner"` |

### Family C — intraday bar loaders (15m)

| # | Location | Shape |
|---|---|---|
| C1 | `h44_50_killtests.load` | 15m + `day`/`hh`/`mm` |
| C2 | `h52_55_57_studies.load` | 15m + `day`/`hh`/`mm` |
| C3 | `h51_fade_study.load` | 15m, `ts` renamed to `timestamp` |
| C4 | `h53_killtest` (inline) | taker-buy 15m + `day` |

### Family D — single-purpose inline panels

| # | Location | Content |
|---|---|---|
| D1 | `h09_calendar_killtest.main` | daily + hourly, `ret` only |
| D2 | `h15_21_killtests` H20 | hourly `ret` + session bucket |
| D3 | `h33_40_killtests` H34 | spot × perp join for basis |

**Step 2 scope: Family A only.** Families B, C and D are structurally
different objects (wide vs long, intraday vs daily, single-use joins);
merging them would be an architectural change, not a consolidation. They
are listed so the decision is explicit rather than an oversight.

---

## 2. Semantic-difference matrix (Family A)

| Dimension | A1 h08 | A2 h10 | A3 h13_h14 | A4 h15_21 | A5 h24_32 | A6 h33_40 | A7 h22_h23 |
|---|---|---|---|---|---|---|---|
| **Input datasets** | lake 1d + `data/funding` | lake 1d + `data/perp` | lake 1d | lake 1d | lake 1d (+BTC twice) | lake 1d | lake 1d |
| **Universe** | LEGACY8 const | LEGACY8 const | LEGACY8 const | param | param | param | param |
| **Missing symbol** | propagates | propagates | propagates | `continue` | `continue` | `continue` | `continue` |
| **Extra join** | funding, inner on day | perp, inner on day | — | — | BTC, **left** on day | — | — |
| **`day` dtype** | **µs** UTC | **µs** UTC | ms UTC | ms UTC | ms UTC | ms UTC | ms UTC |
| **Sort** | after join, by `day` | after join, by `day` | `.sort("timestamp")` pre-select | same | same | same | same |
| **OHLC columns kept** | close | close, perp_close | close | close, volume | close, volume | close, high, low | close |
| **`ret`** | — | — | ✔ | ✔ | ✔ | ✔ | ✔ |
| **Volatility** | — | — | `vol30`,`vol10` **excl current** | `vol10` **excl current** | `vol90` **INCL current** | — | `vol30` **excl current** |
| **Trailing percentile** | funding, w=90, no null-skip | basis, w=90, no null-skip | vol10, w=365, **null-skip** | (H18, w=365, no skip) | — | — | (H23b, w=90, no skip) |
| **Momentum lookbacks** | — | — | — | 7, 14, 30 | 30, 90, 90skip7 | 30, 90, 180 | 90 |
| **Forward horizons** | 1, 7, 30 | 1, 7, 30 | 1, 3, 7 | 7, 30, 1 | 7 | 7, 30 | 7 |
| **Other features** | — | `basis` | — | `ma90`,`peak365`,`v7`,`v30` | `max365`,`maxret30`,`illiq30`,`vshock`,`upshare90`,`beta`,`resmom90`,`hi52`,`riskadj` | `hi30`,`tr`,`atr14` | — |
| **Per-symbol windows** | ✔ (loop) | ✔ (loop) | ✔ (loop) | ✔ (loop) | ✔ (loop) | ✔ (loop) | ✔ (loop) |
| **`drop_nulls`** | in builder | in builder | in builder | at call sites | at call sites | at call sites | in builder |
| **Output rows** | 17,910 | 17,899 | 23,209 | 64,484 | 64,484 | 64,484 | (post-drop) |
| **Output column order** | day,funding,close,pct,fwd*,symbol | day,perp_close,close,basis,pct,fwd*,symbol | day,ret,close,vol30,vol10,vol10_pct,fwd*,symbol | day,close,volume,ret,… ,symbol | day,close,volume,ret,…,symbol | day,close,high,low,ret,…,symbol | day,close,ret,…,symbol |

### Implicit defaults shared by all seven

- `ParquetStore.read` already returns rows sorted by timestamp and
  de-duplicated on timestamp (the store upserts with `keep="last"`), so no
  builder does its own duplicate handling.
- All timestamps are UTC; the lake's canonical dtype is `Datetime("ms","UTC")`.
  A1/A2 cast to µs **only** to match the funding/perp cache dtype for the join.
- polars `rolling_*` defaults: `min_periods == window_size` (leading nulls),
  `rolling_std` uses **ddof=1**. Identical in every builder.
- `pl.lit(symbol).alias("symbol")` is added last, so `symbol` is always the
  final column.

---

## 3. Equivalence evidence (measured, not assumed)

Every shared feature was compared element-wise across builders on the full
lake. **All shared columns are bit-identical**, `max_abs_diff = 0.0`:

| Comparison | Columns | Rows joined | Result |
|---|---|---|---|
| A4 vs A5 | close, ret, r30, fwd7 | 64,484 | exact |
| A4 vs A6 | close, ret, r30, fwd7 | 64,484 | exact |
| A5 vs A6 | close, ret, r30, r90, fwd7 | 64,484 | exact |
| A3 vs A4 | vol10, ret, close | 23,209 | exact |

So the per-symbol expression core **is** genuinely shared and may be
consolidated. What differs is assembly policy, not feature arithmetic.

### The one measured non-equivalence

`vol90` computed **including** the current bar (A5) versus **excluding** it
(the `shift(1)` convention used by A3/A4/A7):

```
max |vol90_incl − vol90_excl| = 0.021364185967575975   (BTCUSDT)
```

On a series whose typical 90-day daily-return σ is ~0.03–0.06 that is a
difference of the same order as the quantity itself — one extreme day
entering or leaving the window. It is **not** a rounding artifact. H24's
`riskadj = r90 / vol90` and H27's low-volatility ranking both depend on
which convention is used.

Neither convention is look-ahead: day *t*'s return is known at *t*'s close.
They are two legitimate features that were given confusingly similar names.
**They must never collapse into one `volatility()`.**

---

## 4. Newly discovered duplication cluster: trailing percentile rank

Not in the original plan. The same hand-rolled Python loop appears **six**
times, with three different windows and two null policies:

| Copy | Series | Window | Null policy | Min index |
|---|---|---|---|---|
| h08 | funding | 90 | none | `i < 90` |
| h10 | basis | 90 | none | `i < 90` |
| h13_h14 | vol10 | 365 | **skips nulls in window; returns None if v is None** | `i < 365` |
| h15_21 (H18) | stretch | 365 | none | `i < 365` |
| h22_h23 (H23b) | funding | 90 | none | `i < 90` |
| h44_50 (H47) | funding rate | 270 | none | `i < 270` |

All six compute `rank = #{w in window : w <= v} / len(window)` over a
**trailing inclusive** window `values[i-window : i+1]` — i.e. window+1
observations, including the current one. The h13_h14 copy additionally
filters `None` out of the window, which changes the denominator.

Three of these (h08, h10, h13_h14) live *inside* Family A builders, so
consolidating those builders requires consolidating this helper too. It is
therefore in scope for Step 2, with `window` and `skip_nulls` as explicit
parameters.

---

## 5. Correction candidates (recorded, NOT fixed)

1. **`vol90` includes the current bar while every other volatility feature
   excludes it.** This is recorded as an *inconsistency*, not an error. It
   is not look-ahead — day *t*'s return is known at *t*'s close — and there
   is no evidence in the record that either convention was chosen by
   mistake; the two are simply different features. Changing it would move
   H24 (risk-adjusted momentum) and H27 (low-vol anomaly). **Methodological
   correction candidate requiring its own pre-registration**, which would
   have to state which convention is intended and why, before any result is
   recomputed.
2. **`illiq30` divides by `close * volume`** where the Amihud measure is
   conventionally `|ret| / dollar_volume` with dollar volume in quote units.
   Whether the lake's `volume` is base or quote units determines if this is
   right. Not investigated further — H29 was killed either way. Recorded.
3. **The trailing percentile window is `window + 1` observations**
   (`values[i-w : i+1]`), so a "90-day percentile" actually ranks against 91
   values. Harmless and consistent across all six copies, but the naming is
   misleading. Recorded.
4. **A1/A2 use a µs `day` dtype** solely because the funding/perp caches were
   written with µs precision. Cosmetic today; would become a real join
   hazard if those caches were ever regenerated at ms. Recorded — this is
   the same cache-provenance fragility noted for `h4x_streams`.

---

## 5b. Forward-return audit (Step 4, 2026-08-11)

Twelve `shift(-n)` sites across seven distinct implementations. All share one
endpoint convention — `P[t+h] / P[t] - 1`, exclusive of *t*, inclusive of
*t+h*, trailing rows left null and dropped by the caller — and all run on a
single series (a per-symbol loop or an already-joined wide frame). **No site
uses `.over()`, and none is applied to a concatenated multi-symbol frame.**

What genuinely differs:

| Dimension | Divergence |
|---|---|
| **Shape** | simple (10 sites) · ratio-of-forwards (2) · difference-of-forwards (1) |
| **Price column** | `close` · `close`/`close_b` (H35) · `eth`/`btc` (H56) · `btc`/`alt` (v2_m1) |
| **Output name** | derivable as `fwd{h}` on daily frames; **not derivable** on intraday — 4 bars is `fwd1h`, 8 bars is `fwd2h` in h52 but `fwd8` in h44_50 |
| **Horizon unit** | days (daily panels) · 15-minute bars (intraday) |
| **Null handling** | trailing nulls always left; the caller's `drop_nulls` list differs per site |

### The shapes are not interchangeable

```
ratio      = (1 + r_a) / (1 + r_b) - 1  =  (r_a - r_b) / (1 + r_b)
difference =  r_a - r_b
```

They agree only when `r_b == 0`. At the 30-day crypto horizon v2_m1 uses,
`r_b` is routinely tens of percent, so substituting one for the other would
change H35, H56 or the V2 dominance verdict. Both are preserved as separate
constructors, and a test asserts they disagree *and* verifies the exact
algebraic relationship above.

**No new correction candidates.** Unlike the volatility conventions, the
forward-return sites were mutually consistent wherever they computed the same
quantity — the only divergences are the three shapes and the naming, both of
which are deliberate properties of their studies.

---

## 5c. Remaining-duplication audit (Step 5, 2026-08-11)

A final sweep of the corpus for analytical duplication outside the panel,
bootstrap and forward-return layers. Two genuine clusters, both consolidated;
everything else deliberately left alone with a stated reason.

### Consolidated

| Cluster | Sites | Semantic differences parameterized |
|---|---|---|
| **Cross-sectional ranking spread** | h15_21 H16, h24_32 `ranking_spread` (10 call sites) | `drop_nulls_on` (h24_32 drops inside, h15_21 at its call site), `gate` (H31 only), `min_symbols` (10, or 6 for H31), `k`, `outcome_column` |
| **15m intraday loader** | h44_50, h52_55_57 | none — the two bodies are semantically identical (differing only in formatting) |

The loop body of the spread cluster was byte-identical between the two
callers. Null placement is the load-bearing difference: dropping inside can
take a thin day below the `min_symbols` gate and remove the whole day, which
changes the day-block bootstrap consuming the series — not merely its length.
A test asserts the two placements produce different series.

### Deliberately left separate

| Implementation | Why |
|---|---|
| `h11_rotation_killtest` spread | Built from Python lists of closes, not a polars panel, with its own `MIN_LISTED` gate. A different data structure, not a different parameterisation. |
| `h33_40` H37/H38 spread | Fused into a per-day loop that also derives breadth, dispersion and pick-correlation. Extracting it would change that loop's iteration. |
| `h53` `_tb15m` loader | Different dataset and schema; derives only `day`. |
| `h51_fade_study` loader | Renames `ts` → `timestamp` because it feeds the event-driven engine, which requires the canonical column name. Same file, different contract. |
| Family B wide/pivot builders (h11, h12, h41_h42) | Structurally different objects (one column per symbol). |
| `universe.json` loading (9 sites) | A one-line `json.loads`; consolidating buys no semantic clarity. |
| `show`/`report` print helpers | Output formatting, not analysis. Consolidating would risk stdout for no research benefit. |
| Monte Carlo path simulators (5 sites) | Out of scope by instruction; remains a recorded cluster. |

**No new correction candidates.** Nothing in this sweep revealed a divergence
between implementations of the same quantity.

---

## 6. Consolidation decision

**Consolidate (proven identical):** the per-symbol expression core — `ret`,
momentum `r{n}`, forward returns `fwd{n}`, rolling close/volume statistics,
true range / ATR — plus the frame assembly loop and the trailing-percentile
helper.

**Parameterize (measured or documented differences):** volatility
convention (`vol_excl_current` vs `vol_incl_current` — never `vol`),
missing-symbol policy, `drop_nulls` placement, `day` dtype, which OHLCV
columns survive the initial `select`, and percentile window/null policy.

**Leave separate (structurally different, not equivalent):** Families B, C
and D; A5's BTC-beta second stage, which is a cross-symbol join rather than
a per-symbol expression and is used by exactly one script.

**Uncertain — deliberately NOT merged:** none. Every proposed merge above is
backed by an element-wise exact-equality check on the full lake (§3).
