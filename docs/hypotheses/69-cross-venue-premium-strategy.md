# Hypothesis 69 — Cross-Venue Premium, Strategy Grade (family F2)

Status: **PRE-REGISTERED 2026-08-27. NO RESULT EXISTS.** Trials declared:
**+3 → 167.** Verdict will be written into §8 and nowhere else.

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

## 8. VERDICT

*(Not yet run. This section is written only when the study executes.)*
