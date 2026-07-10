"""Phase 4 deliverable: prop-firm evaluation EV for the Phase 3 candidate.

    .venv/Scripts/python scripts/phase4_propsim.py

GENERIC rulesets modeled on publicly known futures-eval structures. Real
firms' current rules are UNVERIFIED (CLAUDE.md open question) and several
prohibit automation — verify both before any fee is paid. Pass rates are
upper bounds (EOD trailing check vs real intraday trailing).
"""

from __future__ import annotations

import statistics
from pathlib import Path

from trading_bot.backtesting.candidate import candidate_oos_daily_returns
from trading_bot.risk_management.prop_sim import PropFirmRules, simulate_evaluation

RULESETS = [
    PropFirmRules(
        name="GENERIC-A 50k",
        account_size=50_000.0,
        profit_target_pct=0.06,
        trailing_dd_pct=0.04,
        daily_loss_pct=0.02,
        max_days=None,
        evaluation_fee=170.0,
    ),
    PropFirmRules(
        name="GENERIC-B 50k (strict)",
        account_size=50_000.0,
        profit_target_pct=0.08,
        trailing_dd_pct=0.03,
        daily_loss_pct=0.02,
        max_days=90,
        evaluation_fee=100.0,
    ),
]
SCALES = [0.1, 0.25, 0.5, 1.0, 2.0]
FUNDED_VALUES = [2_000.0, 5_000.0, 10_000.0]


def main() -> None:
    returns = candidate_oos_daily_returns(Path("data/lake"))
    ann_vol = statistics.stdev(returns) * (365**0.5)
    print(
        f"candidate OOS daily returns: {len(returns)} days, "
        f"mean {statistics.mean(returns) * 100:+.3f}%/d, ann.vol {ann_vol * 100:.1f}%\n"
    )
    for rules in RULESETS:
        print(
            f"=== {rules.name}: target +{rules.profit_target_pct:.0%}, "
            f"trailing {rules.trailing_dd_pct:.0%} (EOD), "
            f"daily {rules.daily_loss_pct:.0%}, "
            f"max days {rules.max_days}, fee ${rules.evaluation_fee:.0f} ==="
        )
        best = None
        for scale in SCALES:
            result = simulate_evaluation(
                returns, rules, risk_scale=scale, n_paths=20_000, horizon_days=365
            )
            print("  " + result.to_text())
            if best is None or result.pass_rate > best.pass_rate:
                best = result
        assert best is not None
        evs = ", ".join(f"${v:,.0f}->EV ${best.expected_value(v):+,.0f}" for v in FUNDED_VALUES)
        print(
            f"  best scale {best.risk_scale:.2f}: pass {best.pass_rate:.1%} "
            f"(CI {best.pass_ci_low:.1%}-{best.pass_ci_high:.1%})\n"
            f"  EV per attempt at assumed funded value {evs}\n"
        )


if __name__ == "__main__":
    main()
