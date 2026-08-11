# Archived research output — NOT a golden fixture

Files here are preserved historical observations. Nothing in this directory
is used as a regression target, and nothing here is ever regenerated.

## `phase3_studies.2026-08-10.out`

The complete stdout of `scripts/phase3_studies.py --study all`, captured
2026-08-10 when the MI Lab Layer 1 baseline was frozen.

**Why it is not a permanent byte-exact golden.**
`scripts/phase3_studies.py:184` anchors the H05 carry sub-study's funding
history to `datetime.now(tz=UTC) - timedelta(days=4 * 365)` and fetches it
live from Binance via ccxt. The observation window therefore slides forward
by one day every day, and the script requires network access to run at all.

Measured on 2026-08-11, one day after freezing:

- 5 of 100 lines changed, all in the H05 carry section (lines 92–96).
- The window `2022-08-11..2026-08-10` became `2022-08-12..2026-08-11`.
- One derived figure moved: DOGE annualized carry 7.87% → 7.86%.
- **Lines 1–91 — Studies 2–7 (daily TSMOM, vol-filtered TSMOM, mean
  reversion, vol-target, Donchian) — were byte-identical.**

So the deterministic majority of the script does reproduce exactly; the
script as a whole cannot, because one section is a function of the calendar.

**What this file is for.** It records what the study printed on a specific
date, with a specific data window, so the figures cited in
`docs/research/phase3-verdict.md` remain traceable to an observation. It is
evidence, not a test fixture.

**What was NOT done.** The carry window was not pinned to fixed dates and
the fetch was not switched to a cache. Either change would alter the
methodology and could move published carry figures, so it requires its own
pre-registration (see correction candidates in
`docs/research/mi-layer1-consolidation-plan.md`). The registry entry for
`phase3_studies` is classified `time_dependent` instead, which states the
limitation honestly rather than hiding it behind a fixture that would need
regenerating every day.
