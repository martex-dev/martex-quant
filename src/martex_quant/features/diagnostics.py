"""Structural diagnostics for panel frames — test and debug infrastructure.

A stdout golden proves a published number is unchanged but says nothing
useful about WHY a panel moved. These helpers answer that: they reduce a
frame to the structural properties a refactor must not alter, and diff two
frames property by property.

Deliberately not wired into any research script. Panels are compared here,
in tests and while debugging; nothing emits these permanently.

The invariant this exists to protect: a panel refactor must not change row
count, row ordering, schema, dtypes, column order, null positions, numeric
values, timestamp values, or symbol membership — unless the historical
implementations genuinely differ and the difference is an explicit
parameter.
"""

from __future__ import annotations

from typing import Any

import polars as pl


def panel_signature(frame: pl.DataFrame, *, symbol_column: str = "symbol") -> dict[str, Any]:
    """Reduce a panel to the structural properties a refactor must preserve.

    Cheap enough to call in a test, complete enough that two equal
    signatures plus equal numeric content means the frames are the same
    panel.
    """
    signature: dict[str, Any] = {
        "rows": frame.height,
        "columns": list(frame.columns),  # ORDER matters: it is part of the schema
        "dtypes": {name: str(dtype) for name, dtype in frame.schema.items()},
        "null_counts": {
            name: int(count)
            for name, count in zip(frame.columns, frame.null_count().row(0), strict=True)
        },
    }
    if symbol_column in frame.columns:
        symbols = frame[symbol_column].unique().sort().to_list()
        signature["n_symbols"] = len(symbols)
        signature["symbols"] = symbols
    for name, dtype in frame.schema.items():
        if dtype.base_type() == pl.Datetime and frame.height:
            signature[f"first_{name}"] = str(frame[name][0])
            signature[f"last_{name}"] = str(frame[name][-1])
    return signature


def compare_panels(
    expected: pl.DataFrame,
    actual: pl.DataFrame,
    *,
    symbol_column: str = "symbol",
) -> list[str]:
    """Structural differences between two panels, most diagnostic first.

    Returns an empty list when the panels are structurally identical AND
    every shared numeric column matches exactly. Numeric comparison is only
    attempted when the shapes already agree — otherwise the row-count
    difference is the finding and a value diff would be noise.
    """
    left = panel_signature(expected, symbol_column=symbol_column)
    right = panel_signature(actual, symbol_column=symbol_column)

    differences: list[str] = []
    for key in sorted(set(left) | set(right)):
        if left.get(key) != right.get(key):
            differences.append(f"{key}: {left.get(key)!r} -> {right.get(key)!r}")
    if differences:
        return differences

    for name, dtype in expected.schema.items():
        if not dtype.is_numeric():
            continue
        delta = (expected[name] - actual[name]).abs().max()
        if isinstance(delta, int | float) and delta > 0.0:
            differences.append(f"{name}: max abs diff {delta!r}")
    return differences


def format_comparison(differences: list[str], *, label: str = "panel") -> str:
    """Render ``compare_panels`` output for a test failure message."""
    if not differences:
        return f"{label}: structurally identical"
    lines = [f"{label}: {len(differences)} structural difference(s)"]
    lines.extend(f"  {d}" for d in differences)
    return "\n".join(lines)
