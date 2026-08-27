# Hypothesis 69 — Cross-Venue Premium, Strategy Grade (family F2)

Status: **KILLED (2026-08-27).** Trials: **+3 → 167.** Verdict in §8.
All three gates fail. H68's info signal does **not** survive contact with
execution: the book earns +30.30%/yr at **Sharpe 0.89** and loses to
simply owning the basket (0.94). §2's warning about a bull sample was the
right warning, and Gate B — written for exactly this — is what caught it.
The pre-registered correlation prediction (0.3–0.7) was **correct** at
+0.3929. H68's verdict is untouched; a real info signal has been shown
not to be a tradable edge in this shape.

The strategy hypothesis `docs/hypotheses/68-cross-venue-dislocation.md`
§8.7 said was owed. H68 found the peg-adjusted USD-vs-USDT venue premium
predicts forward returns at info grade (+3.17% at 7d, CI [+0.51%,
+6.08%], breadth 17/20). This asks the different and harder question:
**is any of it tradable after costs, and is it a new edge or the one we
already run?**

**Committed before any strategy code exists.** No result exists at the
time of writing.

---

## 0. What this hypothesis is NOT, stated first because it is the biggest risk

`OBSERVATION` — **H69 is not out-of-sample evidence for H68.** It uses the
same venues, the same 20 symbols, the same window, the same 90-day
percentile window, the same 90th-percentile threshold and the same three
horizons. Nothing is re-estimated on fresh data.

`INTERPRETATION` — H69 can only answer **"is it tradable?"** It cannot
add confirmation that the effect is real. A pass here means the info
signal survives execution; it does **not** mean the finding has been
replicated. Genuine out-of-sample confirmation needs either new venues,
new symbols, or forward time, and none of those is in this document.
The `DSR_global` burden at N = 167 partially prices the reuse; it does
not erase it.

## 1. Claim

A long-only book that holds symbols whose peg-adjusted venue premium sits
in the top decile of its own trailing 90 days earns a positive net return
after realistic costs, beats simply owning the same basket, and is
uncorrelated enough with the deployed momentum book to count as a
separate edge.

## 2. Why it should work — and what the data already says

`OBSERVATION` — decomposing H68's already-counted primary cell into its
two arms (the same statistic H10 printed for its own cell; **no new
trial**):

| Signal, h=7 | E[fwd\|HIGH] | E[fwd\|LOW] | unconditional | HIGH − uncond | uncond − LOW |
|---|---|---|---|---|---|
| S1 raw | +2.93% | −0.32% | +0.92% | +2.01% | +1.24% |
| **S2 peg-adjusted** | **+3.33%** | +0.16% | +0.92% | **+2.41%** | +0.75% |

`INTERPRETATION` — **the edge is predominantly in the HIGH arm.** For S2,
+2.41% of the +3.17% spread is HIGH rising above the unconditional mean
and only +0.75% is LOW falling below it. A long-only book therefore
captures roughly three quarters of the measured spread, which is why the
spec below is long/flat rather than long/short. This is the one place
where a measurement informed the spec's shape, and it is disclosed here
rather than presented as a design intuition.

`OBSERVATION` — **and the warning in the same table.** The unconditional
forward 7-day return over this window is **+0.92%**, roughly 60%/yr. The
sample is predominantly a crypto bull market.

`INTERPRETATION` — a long-only crypto book will pass a "is it profitable"
bar in this window almost regardless of whether the signal works. §5
Gate B exists entirely because of this line, and it is the bar most
likely to matter.

## 3. When it should fail

- **If it is just beta.** See above. Gate B.
- **If execution eats it.** H68 measured close-to-close from the signal
  close. The engine decides at the close and **fills at the next bar's
  open**, charging 10bp fee + 1bp half-spread + volume-participation
  impact per side. §5.2 predicts erosion in advance.
- **If it is the book we already run.** Meta-finding 5: every long-crypto
  book measured in this project correlates **0.52–0.82** with every other
  one. Gate C.
- **If it is too rarely on.** Only **32.6%** of days have at least one
  qualifying symbol (24.9% in 2019–2021, 42.7% in 2022–2023, 33.1% in
  2024–2026), so the book sits substantially in cash and a real per-day
  edge can still annualize to little.
- **If it is a 2022+ book wearing a 2019 start.** Mean symbols available
  is 5.3 in 2019–2021 against 16.6 in 2024–2026.

## 4. Specification

### 4.1 Zero new parameter search — the discipline that makes this worth running

Every parameter is **inherited verbatim from H68**: the 20-symbol
universe, the S2 definition, the 90-day trailing percentile window, the
90th-percentile threshold, and the horizons {1, 7, 30}. **No threshold,
window, universe or weighting alternative is tested.** The only things
this document adds are the ones a return stream cannot avoid having:
how capital is allocated, and how orders are filled.

### 4.2 Signal

For symbol *s* on day *t*, from `data/venues/` daily closes stamped
00:00 UTC:

```
S2(s,t) = log(coinbase_close) - log(binance_close) - log(peg_close)
```

`peg` is Bitfinex USDT/USD. Rank is
`trailing_percentile_rank(window=90, skip_nulls=False)` within symbol —
the same function and the same documented off-by-one H68 used — computed
**within contiguous segments** so XRP's 904-day SEC-delisting halt is
never ranked across. A symbol **qualifies** on day *t* when its rank
≥ **0.90**.

### 4.3 The book

- **Tranche ladder.** Capital is split into `H` equal tranches, where `H`
  is the holding period. On day *t*, tranche `t mod H` rebalances to
  equal-weight that day's qualifying symbols and holds them for `H` days.
  A tranche whose entry day had **no** qualifier goes to **cash**.
- Target weight for symbol *s* = the sum, over tranches currently holding
  *s*, of `(1/H) / (number of qualifiers on that tranche's entry day)`.
- **Long/flat, 1×, no leverage, no shorting**, weights sum ≤ 1.
  The LOW arm's +0.75% is deliberately left on the table: H36 killed the
  short leg in this project and retail short costs are not modelled here.

### 4.4 Execution — the engine is the source of truth

`run_multi_backtest` (`backtesting/multi.py`), which decides at the close
and **fills at the NEXT bar's open** through `ExecutionConfig` defaults:
**10bp fee, 1bp half-spread, 25bp impact per 100% of bar volume.**

**The traded leg is the frozen research lake's Binance OHLCV**, not the
venue cache — the same store every other strategy trial in this ledger
executes against. The venue cache supplies only the exogenous signal.
The two are consistent: a fresh Binance pull was verified byte-identical
to the lake on all 2,747 overlapping closes (H68 §4.1).

**Window: 2019-01-01 → 2026-07-09**, bounded by the lake.

### 4.5 Benchmark

Equal-weight **buy-and-hold** on the same 20 symbols, union mode (a
symbol joins when it has bars), run through the **same engine with the
same costs**, recomputed **in the same run over the identical window**.
Importing a published number and comparing it to a different window is
the FU-B1 defect in `docs/research/graveyard-audit.md` §2.1 and will not
be repeated.

### 4.6 The declared cells — 3 trials, no more

| # | Cell | Purpose |
|---|---|---|
| 1 | `H` = 1 day | H68's h=1 cell as a stream (cheapest to trade) |
| **2** | **`H` = 7 days — PRIMARY** | H68's primary horizon |
| 3 | `H` = 30 days | H68's h=30 cell as a stream |

All three reported regardless of outcome. Block bootstrap: **30-day
blocks, 2,000 resamples, seed 20260827.**

## 5. Pre-registered bars

### 5.1 The six bars

**Gate A — is it an edge at all?** (judged on cell 2)

1. Mean daily net return > 0, 95% block-bootstrap CI excluding zero.
2. Net CAGR ≥ **2%/yr** after all costs.
3. Sharpe ≥ **1.0**.
4. `DSR_global` ≥ **0.95** at **N = 167**.

**Gate B — is it more than beta?**

5. **Sharpe > equal-weight buy-and-hold's Sharpe**, same window, same
   engine, same costs, recomputed in the same run.
   *Sharpe and not CAGR: a book that is in cash ~two-thirds of the time
   will lose a CAGR race to buy-and-hold almost by construction, and that
   would say nothing about whether the timing adds value.*

**Gate C — is it a separate edge?**

6. **|correlation| with rotation-stop < 0.30**, timestamp-joined on daily
   returns, per meta-finding 5 (join on timestamp, never position).

### 5.2 Predictions recorded in advance

- **Gate C will probably fail.** Meta-finding 5 puts every long-crypto
  book in this ledger at 0.52–0.82 against every other. This one is long
  crypto majors roughly a third of the time. **Predicted correlation
  0.3–0.7.** Recording this now means a pass would be genuinely
  surprising, and a failure is not a post-hoc excuse.
- **The net edge will be smaller than H68's +3.17%**, because next-open
  fills and per-side costs are charged here and were not there. Magnitude
  unknown; direction is not.
- **Average deployment ≈ 33%** of capital, from the 32.6% qualifying-day
  rate. Reported, not gated.

### 5.3 Reported, explicitly NOT gated

Time in market, average position count, turnover, MDD, per-year returns,
symbol count by year, the tail-conditional statistic proposed in H67 §8.4
(mean return on rotation-stop's worst-decile days) — recorded to
accumulate evidence for that proposed amendment, **not** as a bar, since
the amendment has not been adopted.

## 6. Disposition, declared in advance

- **A + B + C** → a **new independent edge**. Counts toward the
  eight-edge target of `family-expansion-program.md` §2. Candidate grade;
  paper eligibility remains a separate decision under
  `docs/research/eval-runbook.md`.
- **A + B, C fails** → **not a new edge, a different momentum book.** The
  incremental question then applies and is decided here in advance: it
  must beat rotation-stop on **both** Sharpe and CAGR, recomputed on the
  identical window in the same run, to be a deployment candidate. If it
  does not, it is **STANDALONE-VIABLE** per
  `docs/research/standalone-viable-amendment.md` — real, on the bench,
  not deployed.
- **A passes, B fails** → **crypto beta with extra steps.** Closed, not
  deployed, whatever its correlation. A long-only book in a bull sample
  passing Gate A is not evidence of anything.
- **A fails** → **KILLED.** The honest reading would be that H68's info
  signal does not survive contact with execution.

## 7. Known limitations, stated before results

- **§0 first and loudest: this is not out-of-sample.** Same data, same
  parameters, same window as H68.
- **The window is a bull sample.** Unconditional forward 7-day return
  +0.92%. Gate B is the only thing standing between that and a false pass.
- **The panel is ragged and back-loaded.** 5.3 symbols available on
  average in 2019–2021 against 16.6 in 2024–2026, and only 24.9% of early
  days carry a qualifier. In practice this is mostly a 2022+ book, and
  the per-year table is required reading, not decoration.
- **H68's 2025 weakness carries over** — S1 was −1.32% that year — and a
  per-year result here that is negative in 2025 is expected, not a
  surprise to be explained away.
- **Operational cost of deployment is real and unmodelled.** The live
  system pulls Binance only. This spec needs Coinbase and Bitfinex feeds
  every day before the decision, which is new infrastructure and a new
  failure mode; none of it is charged in the backtest.
- **Survivorship** as recorded in H68 §7, unchanged and still pointing
  the wrong way: a venue delisting a collapsing asset removes it from the
  panel exactly when its premium would be most extreme.
- **The 25bp impact model is a linear guess** at participation-scaled
  slippage, applied to concentrated positions in names as small as WLD
  and ENA. It is the project standard and is not re-tuned here, but it is
  not a measurement.
- **No leverage and no short leg.** Both are deliberate; neither is
  claimed to be optimal.

---

## 8. VERDICT (2026-08-27, scripts/h69_cross_venue_strategy.py, +3 → 167)

**KILLED.** Gate A fails (A3, A4), Gate B fails, Gate C fails. Per §6,
*"A fails → KILLED"* — and it would have closed on the §6 beta branch
even had Sharpe cleared 1.0, because Gate B failed independently.

Window **2019-01-01 → 2026-07-10** as §4.4 declared, 20 symbols, engine
fills at the next bar's open with 10bp fee + 1bp half-spread + 25bp
participation impact per side. 889 entry days carried at least one
qualifier.

### 8.1 The three declared cells, plus the Gate B benchmark

All run in the same process, over the identical window.

| Book | CAGR | Sharpe | MDD | mean bp/day | 95% CI (bp) | DSR@167 | in market |
|---|---|---|---|---|---|---|---|
| hold = 1d | +39.06% | 0.90 | −73.24% | +12.643 | [+1.627, +23.124] | 0.0901 | 33.0% |
| **hold = 7d — PRIMARY** | **+30.30%** | **0.89** | **−50.01%** | **+9.176** | **[+1.683, +17.588]** | **0.3598** | 69.3% |
| hold = 30d | +25.23% | 0.85 | −54.76% | +7.621 | [+0.170, +16.084] | 0.4623 | 91.7% |
| **equal-weight buy-and-hold** | **+52.97%** | **0.94** | −80.23% | +20.712 | [+3.022, +38.236] | 0.0005 | 100.0% |

### 8.2 The six bars

| Gate | Bar | Measured | Result |
|---|---|---|---|
| A1 | mean > 0, CI excludes zero | +9.176bp, low +1.683bp | **PASS** |
| A2 | CAGR ≥ 2%/yr | +30.30% | **PASS** |
| A3 | Sharpe ≥ 1.0 | **0.89** | **FAIL** |
| A4 | DSR ≥ 0.95 @167 | **0.3598** | **FAIL** |
| B5 | Sharpe > buy-and-hold | **0.89 vs 0.94** | **FAIL** |
| C6 | \|corr\| rotation-stop < 0.30 | **+0.3929** (n=2,652) | **FAIL** |

### 8.3 The finding: a significant spread is not a Sharpe

`OBSERVATION` — H68 measured the S2 spread at **+3.17% per 7 days**, CI
[+0.51%, +6.08%], breadth 17/20, on 31,752 symbol-days. That is not a
marginal result. The book built from it — same symbols, same threshold,
same window, **zero new parameter search** — earns Sharpe **0.89** and is
beaten by owning the basket equally weighted.

`INTERPRETATION` — **the info-grade bar has no variance term, and that is
the gap this hypothesis exposes.** `E[fwd | HIGH] − E[fwd | LOW]` with a
CI excluding zero says the conditional means differ. It says nothing
about the volatility a book must carry to collect that difference. Here
the qualifying set averages ~1.4 names, so harvesting a panel-wide mean
requires holding a concentrated book whose realized volatility is far
above the panel average. The mean survived; the ratio did not.

**Proposed as a general lesson, and it is cheap to act on:** an
info-grade SIGNAL should be reported alongside the *volatility of the
bucket*, not only the difference of its means. Two signals with identical
spreads are not equally valuable if one is carried by 15 names and the
other by 1.4. Stated as a proposal for the standard info template, not
adopted by this verdict.

### 8.4 It is beta, and §2 said so before the run

`OBSERVATION` — §2 recorded, before any strategy code existed: *"the
unconditional forward 7-day return over this window is +0.92%, roughly
60%/yr… a long-only crypto book will pass a 'is it profitable' bar in
this window almost regardless of whether the signal works. §5 Gate B
exists entirely because of this line."*

`OBSERVATION` — A1 and A2 **passed**: mean +9.176bp/day with a CI
excluding zero, CAGR +30.30%. On those two bars alone this looks like a
success.

`INTERPRETATION` — and it is not one. Gate B is what separates the two
readings, and it fired: the timing **subtracts** risk-adjusted return
relative to owning everything. Without Gate B this verdict would have
recorded a +30%/yr strategy as a win. **The bar earned its place**, and
that is worth more than the result it killed.

### 8.5 The correlation prediction was right

`OBSERVATION` — §5.2 predicted, before the run: *"Gate C will probably
fail… predicted correlation 0.3–0.7."* Measured: **+0.3929**.

`INTERPRETATION` — meta-finding 5 holds again. Every long-crypto book in
this ledger sits 0.52–0.82 against every other; this one is 0.39 against
rotation-stop, at the low end but well outside the 0.30 bar. **Not an
independent edge**, and it does not count toward the eight-edge target.

`OBSERVATION` — the tail-conditional statistic proposed in H67 §8.4,
reported here only (the amendment is **not** adopted): on rotation-stop's
worst decile H69 returns **−1.575%**, worst 5% **−1.968%**, worst 1%
**−2.648%**, against +0.092% unconditional.

`INTERPRETATION` — useful scope information for that proposal. Here the
**linear bar already saw the dependence** (+0.39, failing), so the
tail check adds nothing. H67's blindness was specific to a
**short-convexity** payoff driven by squared returns. **The proposed
amendment should therefore be scoped to asymmetric payoffs, not applied
to every hypothesis** — for a directional book the existing bar works.

### 8.6 What the signal did do, recorded without being acted on

`OBSERVATION` — at hold = 1 the book earns **+39.06%/yr while deployed
only 33.0% of the time**, against buy-and-hold's +52.97%/yr at 100%.
Per unit of time in market that is roughly **118%/yr vs 53%/yr**.

`INTERPRETATION` — the signal **does** concentrate return into the days
it is on, by more than 2×. What it does not do is concentrate
*risk-adjusted* return, and this project cannot lever an edge that failed
its own validation. This is recorded because it points at a differently
shaped question — the premium as an **overlay or filter on the deployed
book** rather than a standalone long book — and **that would be a new
pre-registration with a stated reason, not a rescue of this one.**
Time in market is also not the same as leverage-adjusted exposure, so the
118% figure is an illustration, not a Sharpe claim.

### 8.7 Per-year, including the part that is tempting and must be refused

| Year | n | H69 | Sharpe | buy-and-hold |
|---|---|---|---|---|
| 2019 | 274 | +28.38%/yr | 1.18 | −0.22%/yr |
| 2020 | 366 | +70.43%/yr | 1.81 | +182.58%/yr |
| 2021 | 365 | +23.64%/yr | 0.53 | +289.27%/yr |
| 2022 | 365 | −12.93%/yr | −0.29 | −93.70%/yr |
| **2023** | 365 | **+91.48%/yr** | **2.46** | +84.53%/yr |
| **2024** | 366 | **+94.14%/yr** | **2.60** | +124.69%/yr |
| **2025** | 365 | **−19.53%/yr** | −0.70 | −13.54%/yr |
| **2026** | 191 | **−47.79%/yr** | −1.14 | −45.54%/yr |

`OBSERVATION` — 2023 and 2024 are excellent on their own (Sharpe 2.46 and
2.60, beating buy-and-hold in 2023). 2025 and 2026 are bad.

`INTERPRETATION` — **this is exactly the slice that must not be acted
on.** Selecting 2023–2024 after seeing the full result is the failure
pre-registration exists to prevent, and the ledger has a standing rule
that near-misses stay closed. Recorded because §7 required the per-year
table, and because H68 §8.6 **pre-flagged 2025 as its weak year** — that
flag was written before this study existed and it was right, which makes
the 2025–2026 weakness a confirmed property rather than bad luck.

### 8.8 Caveats that survive the kill

- **§0 stands: this was never out-of-sample.** It shared H68's data,
  parameters and window, so it could only ever have answered "is it
  tradable". It answered no.
- **An implementation deviation was found and corrected before this
  verdict was written.** The first run fed the engine the lake's full
  extent from 2017-08-17 rather than §4.4's declared 2019-01-01 start,
  which let the benchmark trade the 2017 bubble (+838%/yr) and the 2018
  crash while the strategy sat in signal-less cash. Corrected to the
  registered window; the fix **helped** the benchmark (Sharpe 0.86 →
  0.94) and helped the strategy less (0.82 → 0.89), so it widened the
  Gate B gap rather than narrowing it. The pre-fix figures are recorded
  here so the correction is auditable.
- **MDD −50% on the primary and −73% at hold = 1.** Whatever else this
  book is, it is not a low-drawdown vehicle.
- **The 25bp participation-impact model is the project standard, not a
  measurement**, and it is applied to concentrated positions in names as
  small as WLD and ENA. It is more likely optimistic than pessimistic.
- **H68's verdict is untouched.** The info signal remains a SIGNAL; what
  is now also on the record is that it does not survive execution in a
  long-only ladder. Those are different claims and the ledger holds both.
