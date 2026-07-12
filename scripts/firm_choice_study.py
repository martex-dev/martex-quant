"""Firm-choice sprint study: Breakout vs HyroTrader rules on validated streams.

    .venv/Scripts/python scripts/firm_choice_study.py

Extends scripts/july_sprint_study.py (0 ledger trials — policy analysis).
Firm rule sets from public docs 2026-07-12 (verify on day 0):
- Breakout 1-step 5k: fee $45, target +10%, daily 4%, static max loss 6%,
  NO min trading days, on-demand payout (assume 1d activation + 0d payout),
  80% split -> $400 net needs +10% gross funded profit.
- HyroTrader 1-step 5k: fee $119 (refunded at first payout), target +10%,
  daily 4%, static max loss 6%, MIN 10 trading days (after hitting target
  the path coasts at 0.25x until day 10), 70% split + fee refund ->
  $400 net needs ~+8% gross funded profit. Assume 1d activation, 1d payout.
Universe caveat: Breakout lists ~50 major pairs; the rotation-stop/43a
streams below assume our FULL 40-coin universe — Breakout results are
therefore OPTIMISTIC until re-validated on its actual symbol list.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "july_sprint_study", Path(__file__).parent / "july_sprint_study.py"
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build_streams = _mod.build_streams

ACCOUNT = 5_000.0
BLOCK = 7
N_PATHS = 20_000
DEADLINE = 17  # buy ~Jul 14, deadline Jul 31
SCALES = [1.0, 2.0, 3.0, 4.0]
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Firm:
    name: str
    fee: float
    daily_loss: float
    static_floor: float
    min_days: int
    funded_target_pct: float  # gross funded profit needed for ~$400 net
    frictions_days: int  # activation + payout processing


FIRMS = [
    Firm("Breakout ($45, no min days)", 45.0, 0.04, 0.06, 0, 0.10, 1),
    Firm("HyroTrader ($119, 10d min, fee refund)", 119.0, 0.04, 0.06, 10, 0.08, 2),
]


def run_chain(
    rets: list[float], firm: Firm, scale: float, rng: random.Random
) -> tuple[bool, bool, int]:
    max_start = len(rets) - BLOCK
    day = 0
    fees = 0
    attempt = 0
    deadline = DEADLINE - firm.frictions_days
    while attempt < MAX_ATTEMPTS and day < deadline:
        attempt += 1
        fees += 1
        equity = ACCOUNT
        floor = ACCOUNT * (1.0 - firm.static_floor)
        target = ACCOUNT * 1.10
        eval_start = day
        hit = False
        busted = False
        while day < deadline and not busted and (not hit or day - eval_start < firm.min_days):
            start = rng.randint(0, max_start)
            for r in rets[start : start + BLOCK]:
                day += 1
                eff = scale if not hit else 0.25  # coast after target until min days
                prev = equity
                equity *= 1.0 + r * eff
                if equity <= prev * (1.0 - firm.daily_loss) or equity <= floor:
                    busted = True
                    break
                if equity >= target:
                    hit = True
                if day >= deadline or (hit and day - eval_start >= firm.min_days):
                    break
        if busted:
            continue
        if not (hit and day - eval_start >= firm.min_days):
            return (False, False, fees)
        # funded stage
        equity = ACCOUNT
        floor = ACCOUNT * (1.0 - firm.static_floor)
        target = ACCOUNT * (1.0 + firm.funded_target_pct)
        while day < deadline:
            start = rng.randint(0, max_start)
            for r in rets[start : start + BLOCK]:
                day += 1
                prev = equity
                equity *= 1.0 + r * scale
                if equity <= prev * (1.0 - firm.daily_loss) or equity <= floor:
                    return (False, True, fees)
                if equity >= target:
                    return (True, True, fees)
                if day >= deadline:
                    break
        return (False, True, fees)
    return (False, False, fees)


def main() -> None:
    streams = build_streams()
    print(
        f"deadline {DEADLINE}d (buy ~Jul 14), {N_PATHS} paths, retries up to "
        f"{MAX_ATTEMPTS}, EOD checks (upper bounds)\n"
    )
    for firm in FIRMS:
        print(f"=== {firm.name} ===")
        for stream_name, rets in streams.items():
            print(f"  engine: {stream_name}")
            for scale in SCALES:
                rng = random.Random(int(scale * 10) + firm.min_days)
                chain = passed = fees_total = 0
                for _ in range(N_PATHS):
                    ok, p, fees = run_chain(rets, firm, scale, rng)
                    chain += ok
                    passed += p
                    fees_total += fees
                print(
                    f"    {scale:>4.1f}x  P(chain) {chain / N_PATHS:>6.1%}  "
                    f"P(funded by Aug) {passed / N_PATHS:>6.1%}  "
                    f"avg fee cost {fees_total / N_PATHS * firm.fee:>4.0f}$"
                )
        print()


if __name__ == "__main__":
    main()
