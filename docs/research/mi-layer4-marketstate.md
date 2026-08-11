# MI Lab Layer 4 — MarketState & poison tests

Date: 2026-08-11. Scope: point-in-time market state with the look-ahead
guarantee enforced by construction. No historical result changed.

---

## 1. The guarantee

`History` already makes look-ahead structurally inexpressible for a single
instrument: it exposes bars only up to a cursor, and indexing past it raises.
`MarketState` is the cross-sectional equivalent — it filters on an explicit
**availability time** and keeps nothing beyond it, so a state built as of `t`
physically cannot hand back a value knowable only later.

## 2. Availability is not the observation's timestamp

A daily bar stamped `2024-01-01T00:00Z` describes the 24 hours that follow.
Its close is unknown until `2024-01-02T00:00Z`. So:

```
availability_time = bar_timestamp + interval (+ optional lag)
```

This is the same convention the event-driven engine encodes as "decide on the
close, fill at the next open". Being off by one bar here is the single most
common way a backtest lies, so the rule is a declared object
(`BarCloseAvailability`) recorded on every state — a result can say which
assumption produced it — rather than an inline comparison.

`lag` models a late-publishing feed or a deliberately pessimistic execution
assumption. It changes `rule_name`, so two states built under different
assumptions are never mistaken for each other.

## 3. Deliberate scope restriction: OHLCV only

**This is the decision I flagged, resolved conservatively.** Every other
series in the corpus has a genuinely ambiguous availability rule, and none is
implemented:

| Series | Why the OHLCV rule does not apply |
|---|---|
| funding rates | Stamped at **settlement** — the stamp IS the availability time, not the event time. Applying `+interval` would be wrong by a full cycle. |
| open interest | A point-in-time snapshot with no interval at all; there is nothing to add. |
| perp closes | Same shape as OHLCV, but the cache carries no interval metadata to derive from. |
| derived equity streams | Computed from full history. "The value at *t*" has no meaning independent of how the curve was produced. |

Requesting an unsupported kind raises rather than guessing. A rule chosen for
convenience would be worse than no rule: it would make a leaking MarketState
look rigorous, which is precisely the failure this layer exists to prevent.

Adding any of these is a pre-registered methodological decision, not an
implementation detail, because it determines whether strategy × market-state
analysis is sound or quietly circular.

## 4. Poison tests

Four deliberate look-ahead injections, each asserting the guard — not the
fixture — is what catches the leak:

1. **A future bar.** State mid-series excludes the not-yet-closed bar; the
   test also shows a naive `timestamp <= as_of` filter admits exactly one
   extra row, so the exclusion demonstrably comes from the availability rule.
2. **A future-derived column.** A forward return is future knowledge wearing
   a present-day timestamp; the newest row's value is null because its future
   is not in the state.
3. **A state carrying unavailable rows**, as a mislabelled loader would
   produce — `assert_no_lookahead` rejects it.
4. **A frame with no availability column** — unverifiable is treated as
   unsafe rather than assumed fine.

Plus structural invariants: states are monotone in time (information is only
added), a symbol with no closed bars is kept as an **empty frame** rather than
dropped (conflating "not yet observable" with "not in the universe" is how
survivorship creeps in), a symbol absent from the lake is omitted, and a
naive-timezone `as_of` is refused since the corpus is UTC throughout.

## 5. Findings

None new. No evidence bearing on correction candidates 1–8 surfaced, and
nothing here touches them.
