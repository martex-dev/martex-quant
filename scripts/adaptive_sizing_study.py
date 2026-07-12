"""Adaptive (equity-aware) sizing for the single-attempt eval.

    .venv/Scripts/python scripts/adaptive_sizing_study.py

Policy analysis on the validated rotation-stop stream (0 ledger trials).
The swing account's floor is STATIC, so the optimal single-attempt
policy sizes by remaining buffer: bold above start, defensive near the
floor. Policies (small principled grid, no mining):
  static X       : scale = X
  adaptive(U)    : equity >= start -> U; below start -> U scaled by
                   remaining buffer fraction, floored at 0.35
Rules: +10% target, 4% daily, 6% static floor, min 10 days, unlimited.
"""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "july_sprint_study", Path(__file__).parent / "july_sprint_study.py"
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build_streams = _mod.build_streams

ACCOUNT = 5_000.0
TARGET = ACCOUNT * 1.10
FLOOR = ACCOUNT * 0.94
DAILY_LOSS = 0.04
MIN_DAYS = 10
HORIZON = 365
BLOCK = 7
N_PATHS = 20_000


def scale_static(x: float):  # noqa: ANN201
    return lambda equity: x


def scale_adaptive(up: float):  # noqa: ANN201
    def f(equity: float) -> float:
        if equity >= ACCOUNT:
            return up
        buffer_frac = (equity - FLOOR) / (ACCOUNT - FLOOR)
        return max(0.35, up * buffer_frac)

    return f


POLICIES = [
    ("static 0.75x", scale_static(0.75)),
    ("static 0.85x", scale_static(0.85)),
    ("static 1.00x", scale_static(1.0)),
    ("adaptive up=1.00", scale_adaptive(1.0)),
    ("adaptive up=1.25", scale_adaptive(1.25)),
    ("adaptive up=1.50", scale_adaptive(1.5)),
]


def run_one(rets: list[float], policy, rng: random.Random) -> tuple[str, int]:  # noqa: ANN001
    max_start = len(rets) - BLOCK
    equity = ACCOUNT
    day = 0
    hit = False
    while day < HORIZON:
        start = rng.randint(0, max_start)
        for r in rets[start : start + BLOCK]:
            day += 1
            eff = policy(equity) if not hit else 0.25
            prev = equity
            equity *= 1.0 + r * eff
            if equity <= prev * (1.0 - DAILY_LOSS) or equity <= FLOOR:
                return ("bust", day)
            if equity >= TARGET:
                hit = True
            if hit and day >= MIN_DAYS:
                return ("pass", day)
            if day >= HORIZON:
                break
    return ("timeout", day)


def main() -> None:
    rets = build_streams()["rotation-stop"]
    print(f"rotation-stop stream, ONE attempt, {N_PATHS} paths, EOD upper bounds\n")
    header = f"{'policy':<18} {'P(pass)':>8} {'P(bust)':>8} {'median':>7}"
    print(header + f" {'by Aug31':>9} {'by Sep30':>9}")
    for name, policy in POLICIES:
        rng = random.Random(hash(name) % 100_000)
        outcomes = [run_one(rets, policy, rng) for _ in range(N_PATHS)]
        passes = sorted(d for o, d in outcomes if o == "pass")
        busts = sum(1 for o, _ in outcomes if o == "bust")
        median = passes[len(passes) // 2] if passes else 0
        by49 = sum(1 for d in passes if d <= 49) / N_PATHS
        by79 = sum(1 for d in passes if d <= 79) / N_PATHS
        print(
            f"{name:<18} {len(passes) / N_PATHS:>8.1%} {busts / N_PATHS:>8.1%} "
            f"{median:>6}d {by49:>9.1%} {by79:>9.1%}"
        )


if __name__ == "__main__":
    main()
