"""Single-attempt eval study: ONE fee, no retries (user constraint 2026-07-13).

    .venv/Scripts/python scripts/single_attempt_study.py

HyroTrader 1-step 5k rules with swing upgrade: target +10%, daily loss
4% (static, day-start anchored), max loss 6% static, min 10 trading
days, UNLIMITED time. One attempt: P(pass) vs sizing, plus time
distribution. Policy analysis on validated streams (0 ledger trials).
EOD checks -> upper bounds.
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
TARGET = 1.10
DAILY_LOSS = 0.04
FLOOR_PCT = 0.06
MIN_DAYS = 10
HORIZON = 365
BLOCK = 7
N_PATHS = 20_000
SCALES = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]


def run_one(rets: list[float], scale: float, rng: random.Random) -> tuple[str, int]:
    max_start = len(rets) - BLOCK
    equity = ACCOUNT
    floor = ACCOUNT * (1.0 - FLOOR_PCT)
    target = ACCOUNT * TARGET
    day = 0
    hit = False
    while day < HORIZON:
        start = rng.randint(0, max_start)
        for r in rets[start : start + BLOCK]:
            day += 1
            eff = scale if not hit else 0.25  # coast after target until min days
            prev = equity
            equity *= 1.0 + r * eff
            if equity <= prev * (1.0 - DAILY_LOSS) or equity <= floor:
                return ("bust", day)
            if equity >= target:
                hit = True
            if hit and day >= MIN_DAYS:
                return ("pass", day)
            if day >= HORIZON:
                break
    return ("timeout", day)


def main() -> None:
    streams = build_streams()
    print(
        f"ONE attempt, HyroTrader swing rules (+10% target, 4% daily, 6% floor, "
        f"min {MIN_DAYS}d, unlimited time), {N_PATHS} paths, EOD upper bounds\n"
    )
    for name, rets in streams.items():
        print(f"=== engine: {name} ===")
        print(
            f"{'scale':>6} {'P(pass)':>8} {'P(bust)':>8} {'median':>7} "
            f"{'P(by Jul31)':>12} {'P(by Aug31)':>12} {'P(by Sep30)':>12}"
        )
        for scale in SCALES:
            rng = random.Random(int(scale * 100) + 77)
            outcomes = [run_one(rets, scale, rng) for _ in range(N_PATHS)]
            passes = [d for o, d in outcomes if o == "pass"]
            busts = sum(1 for o, _ in outcomes if o == "bust")
            passes.sort()
            median = passes[len(passes) // 2] if passes else 0
            p_pass = len(passes) / N_PATHS
            by17 = sum(1 for d in passes if d <= 17) / N_PATHS
            by49 = sum(1 for d in passes if d <= 49) / N_PATHS
            by79 = sum(1 for d in passes if d <= 79) / N_PATHS
            print(
                f"{scale:>5.2f}x {p_pass:>8.1%} {busts / N_PATHS:>8.1%} {median:>6}d "
                f"{by17:>12.1%} {by49:>12.1%} {by79:>12.1%}"
            )
        print()


if __name__ == "__main__":
    main()
