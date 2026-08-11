# MI Lab Layer 3 — Series store & provenance: audit and design

Date: 2026-08-11. Scope rule: make research inputs reproducible and
auditable **without changing any historical research result**.

---

## 1. Audit: every non-lake series loader

The Parquet lake covers exchange OHLCV with a canonical schema, a catalog
and validation that blocks a bad write. Everything else the corpus depends
on had **none of that**: 18 direct `pl.read_parquet` call sites, no schema
check, no provenance, no catalog entry.

| Kind | Files | Read sites | Time column | Precision |
|---|---|---|---|---|
| funding | 8 | 3 (h08 fetch+cache, h22_h23, h44_50) | `timestamp` | µs UTC |
| perp | 8 | 2 (h10 fetch+cache, h33_40) | `day` | µs UTC |
| intraday 15m | 12 | 3 (h44_50, h52_55_57 — consolidated in Layer 1 — and h51) | `ts` | µs UTC |
| intraday taker | 11 | 1 (h53) | `ts` | µs UTC |
| intraday OI | 12 | 0 (H54 data-blocked) | `ts` | µs UTC |
| derived streams | 5 | 7 (h41_h42 producer; h43 ×3, h51, h52, july_sprint, owncap) | `timestamp` | µs UTC |

**Timestamp semantics are preserved, not normalised.** Every cache is
microsecond UTC while the lake is millisecond, and each kind keys on a
different column name. That divergence is real and load-bearing — it is why
`features.panel.align_day_to_cache_precision` exists — so the store records
it per kind rather than unifying it.

---

## 2. Findings

### Finding 3.1 — the derived cache holds TWO schemas under one convention

`data/tmp/h4x_streams/` contains five files whose names are
indistinguishable in shape but whose schemas are not:

| File | Schema | Rows |
|---|---|---|
| `rot_stop_stream` | timestamp, **equity**, exposure | 2,880 |
| `rot_champion_stream` | timestamp, **equity**, exposure | 2,880 |
| `v1_stream` | timestamp, **ret** | 1,710 |
| `v1_stop_stream` | timestamp, **ret** | 1,710 |
| `blend_stream` | timestamp, **ret** | 1,978 |

A consumer reading a `_stream` file without checking gets either a
`ColumnNotFound` or — worse — silently compares an equity **level** against
a **return**. h43_combo_study reads all three kinds in one function and is
correct only because it happens to use each appropriately.

Modelled as two kinds, `EQUITY_STREAM` and `RETURN_STREAM`, with a
`STREAM_KINDS` map recording which file is which. Tests assert that reading
a return stream as an equity stream is caught.

**Not a correction candidate**: no published result is wrong. It is a latent
hazard, now closed.

### Finding 3.2 — 52 of 55 real series pass integrity; the 3 failures were my model, not the data

Running the new checks over every real file flagged only the three `ret`
streams, and only because the initial spec assumed one stream shape. After
modelling both, **all 55 real series pass**.

### Finding 3.3 — derived-cache provenance remains structurally weak

Recording the producer and upstream inputs (Layer 3) makes the coupling
visible, but does not fix it: the streams are recomputed only when absent,
and **nothing verifies a recomputed stream matches the one its consumers
were validated against**. This is the same fragility recorded as Layer 1
correction candidate 4, now with a concrete mechanism attached. Closing it
would require storing an expected fingerprint and refusing a mismatch —
which would change what those studies do when the cache is stale, so it
needs its own decision.

### Evidence relevant to existing correction candidates — documented, not fixed

* **Candidate 4 (cache timestamp precision/provenance):** the store now
  detects a µs→ms drift explicitly, and a test demonstrates that such a
  drift would otherwise silently empty every join against the lake. The
  underlying provenance weakness is unchanged.
* **Candidate 5 (H05 carry time-dependence):** unaffected; the carry study
  fetches live rather than reading a cache, which is precisely why it cannot
  hold a golden.

---

## 3. Design

`data/series/store.py` — one read path per kind.

* `SeriesSpec` per kind: directory, filename template, time column, exact
  schema, and for derived kinds the producer and upstream inputs.
* `SeriesStore.read` returns the frame **byte-identical** to a direct
  `pl.read_parquet`. No sorting, renaming or aggregation — those differ per
  study and are part of each published result.
* `read_with_provenance` / `describe` add: sha256, size, rows, observed
  schema, first/last timestamp, read time, and derived-kind lineage.
* `manifest` produces a JSON-safe audit record whose digest excludes
  `read_at`, so two runs over unchanged files yield the same hash. Since
  `/data/` is gitignored, this is the only thing that can identify which
  bytes produced a result.
* `check_integrity` detects: empty data, missing/extra columns, dtype drift
  (including timestamp precision), unsorted timestamps, duplicate
  timestamps. **Gaps are deliberately NOT errors** — exchange downtime and
  young listings are legitimate, and the lake's own validator treats gaps as
  warnings.
* `staleness_days` reports age rather than enforcing a threshold: what
  counts as stale is a per-study decision.

`strict=True` by default — a silently-wrong input is how a corpus rots.

---

## 4. Migration

Six duplicated stream reads migrated (h43 ×3, h51, h52_55_57,
july_sprint, owncap_sizing). All five affected goldens reproduce exactly.

Deliberately **not** migrated: h08's `fetch_funding` and h10's
`fetch_perp_daily` are fetch-or-read-cache functions with network fallbacks,
not plain reads; h22_h23 and h44_50 apply study-specific aggregation inline;
h53's taker read and h51's renaming read each have a different contract.
Wrapping those would change control flow around network calls for no
provenance gain at the read itself.
