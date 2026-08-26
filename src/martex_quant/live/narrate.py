"""Plain-English narration of each day's decisions.

Generated from the ACTUAL decision variables (trends measured, ranks
computed, vol scaling applied) — a diary written by the bot about what it
really did and why, not an AI's guess after the fact. No jargon:
'exposure' becomes 'position size', 'params' become 'the settings it
picked', symbols lose their USDT suffix.
"""

from __future__ import annotations

from typing import Any

import polars as pl


def _name(symbol: str) -> str:
    return symbol.removesuffix("USDT")


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def _trailing_return(df: pl.DataFrame, lookback: int) -> float | None:
    closes = df["close"]
    if closes.len() <= lookback:
        return None
    past = closes[-1 - lookback]
    now = closes[-1]
    assert isinstance(past, float) and isinstance(now, float)
    return now / past - 1.0


def _trades_sentence(fills: list[dict[str, Any]]) -> str:
    if not fills:
        return "No trades were needed today."
    parts = []
    for f in fills:
        action = "bought" if f["side"] == "buy" else "sold"
        parts.append(f"{action} {_name(f['symbol'])} (~${f['quantity'] * f['price']:,.0f})")
    return "Trades today: " + ", ".join(parts) + "."


def narrate_vol_target(
    frames: dict[str, pl.DataFrame],
    params: dict[str, Any],
    exposures: dict[str, float],
    fills: list[dict[str, Any]],
) -> str:
    """One day of the trend-following strategy, in plain language."""
    rising, holding, flat = [], [], []
    for symbol, df in frames.items():
        lookback = int(params.get(symbol, 0)) or 0
        ret = _trailing_return(df, lookback) if lookback else None
        label = (
            f"{_name(symbol)} ({_pct(ret)} over {lookback}d)" if ret is not None else _name(symbol)
        )
        if exposures.get(symbol, 0.0) > 0:
            size = exposures[symbol]
            holding.append(f"{label} at {size * 100:.0f}% of its slot")
            rising.append(_name(symbol))
        elif ret is not None and ret > 0:
            # positive trend but sized to zero (extreme vol) — rare
            flat.append(f"{label} — trend is up but it is too choppy to hold safely")
        else:
            flat.append(label)

    lines = []
    if holding:
        lines.append(
            "It checked each coin's trend at its own chosen lookback. Rising and held: "
            + "; ".join(holding)
            + ". Position sizes shrink automatically when a coin gets choppier."
        )
    if flat:
        lines.append(
            ("Everything else is" if holding else "Every coin it watches is")
            + " below where it was at its lookback — no upward trend, so"
            + " those slots stay safely in cash: "
            + ", ".join(flat)
            + "."
        )
    lines.append(_trades_sentence(fills))
    return " ".join(lines)


def narrate_rotation(
    frames: dict[str, pl.DataFrame],
    lookback: int,
    weights: dict[str, float],
    fills: list[dict[str, Any]],
) -> str:
    """One day of the rotation strategy, in plain language."""
    scored = []
    for symbol, df in frames.items():
        ret = _trailing_return(df, lookback)
        if ret is not None:
            scored.append((symbol, ret))
    scored.sort(key=lambda x: x[1], reverse=True)
    ranking = ", ".join(f"{_name(s)} {_pct(r)}" for s, r in scored[:4]) + ", …"

    lines = [
        f"It ranked all {len(scored)} coins by how far they moved in the last "
        f"{lookback} days: {ranking}"
    ]
    held = [(s, w) for s, w in weights.items() if w > 0]
    if held:
        total = sum(w for _, w in held)
        names = " and ".join(_name(s) for s, _ in held)
        sizing = (
            "at full size"
            if total > 0.95
            else f"scaled down to {total * 100:.0f}% of the account because"
            " the market is choppier than its risk budget"
        )
        lines.append(
            f"It holds the strongest: {names}, {sizing}. "
            "It keeps them until other coins overtake them or their own trend turns down."
        )
    else:
        top_positive = [s for s, r in scored if r > 0]
        if not top_positive:
            lines.append(
                "Even the strongest coins are DOWN over that window — the rules say "
                "never hold a falling coin just because it falls slower, so it sits fully in cash."
            )
        else:
            lines.append("Its top picks did not qualify today, so it sits in cash.")
    lines.append(_trades_sentence(fills))
    return " ".join(lines)
