"""Round-trip cost model for Solana AMM meme-coin trades.

This module exists because the cost regime, not the signal, is what decides
which meme-coin strategies are mathematically available at a given account
size. On a $100 account a $0.40 priority fee is 0.4% of capital *per
transaction*; on a $500k account it is 0.00008%. The same signal is a business
for one and a shredder for the other, and no amount of model quality changes
that. Everything downstream sizes against these numbers.

Cost components, all real and all charged whether the trade wins or loses:

fixed, per transaction (USD)
    Solana base fee plus the priority fee / Jito tip needed to land in a
    competitive block. Paid on entry and on exit, and paid again on failed
    attempts that still consume the fee.

proportional, per side (fraction)
    The venue's swap fee. Pump.fun's bonding curve takes 1%; PumpSwap and
    Raydium CPMM take 0.25%. Jupiter itself adds no fee but routes into these.

price impact, per side (fraction)
    Constant-product AMMs move against you by roughly ``notional / quote
    reserve``. For a pool reported as ``reserve_in_usd`` total (both legs), the
    quote leg is about half that, so impact ≈ ``2 * notional / reserve_usd``.
    This is the term that explodes on thin pools and is invisible in any
    backtest that fills at the close.

failure rate
    A share of attempts land no position but still burn the fixed fee. During
    congestion this is not a rounding error.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Venue swap fees, per side, as fractions of notional.
PUMPFUN_BONDING_FEE = 0.01
PUMPSWAP_FEE = 0.0025
RAYDIUM_CPMM_FEE = 0.0025


@dataclass(frozen=True, slots=True)
class CostModel:
    """Parameters of one execution environment.

    Defaults describe a retail Solana trader paying a competitive-but-not-
    insane priority fee on a post-bonding-curve AMM. They are deliberately not
    optimistic: an entry that loses the race is worth nothing, so quoting the
    minimum landable fee would be modelling a fill we would not get.
    """

    fixed_fee_usd: float = 0.40
    venue_fee: float = PUMPSWAP_FEE
    failure_rate: float = 0.05
    extra_slippage: float = 0.01
    """Headroom above pure AMM impact: block-time price drift between quote and
    fill, plus adversarial reordering by faster bots. Applied per side."""

    def price_impact(self, notional_usd: float, reserve_usd: float) -> float:
        """Constant-product impact for one side, as a fraction of notional."""
        if reserve_usd <= 0:
            return 1.0
        return min(1.0, 2.0 * notional_usd / reserve_usd)

    def round_trip_cost_usd(self, notional_usd: float, reserve_usd: float) -> float:
        """Total USD lost to friction on a full in-and-out at this size.

        Assumes the exit happens at the same reserve depth as the entry. That
        is generous: a token you are exiting has usually thinned out, and a
        token you are exiting *fast* has thinned a lot.
        """
        impact = self.price_impact(notional_usd, reserve_usd)
        proportional = 2.0 * notional_usd * (self.venue_fee + impact + self.extra_slippage)
        # Failed attempts land no position but still pay the fee, so the
        # expected number of fee payments exceeds the two legs.
        expected_fee_payments = 2.0 / max(1e-9, 1.0 - self.failure_rate)
        return proportional + expected_fee_payments * self.fixed_fee_usd

    def round_trip_cost_frac(self, notional_usd: float, reserve_usd: float) -> float:
        """Round-trip friction as a fraction of the notional traded."""
        if notional_usd <= 0:
            return float("inf")
        return self.round_trip_cost_usd(notional_usd, reserve_usd) / notional_usd

    def breakeven_gross_return(self, notional_usd: float, reserve_usd: float) -> float:
        """Gross price move required just to get the stake back.

        This is the number to hold every meme-coin claim against. A strategy
        whose average winner is +30% and whose breakeven is +22% is not a 30%
        edge; it is an 8% edge before the losers are counted.
        """
        return self.round_trip_cost_frac(notional_usd, reserve_usd)


@dataclass(frozen=True, slots=True)
class SizingVerdict:
    """Whether a given account can trade a given pool at all, and how."""

    notional_usd: float
    reserve_usd: float
    round_trip_frac: float
    breakeven_return: float
    fee_share_of_cost: float
    """Portion of total friction that is the flat per-transaction fee. Above
    ~0.5 the account is too small for the trade and is mostly paying rent."""

    viable: bool
    reason: str


def evaluate_trade(
    notional_usd: float,
    reserve_usd: float,
    model: CostModel | None = None,
    *,
    max_round_trip_frac: float = 0.15,
) -> SizingVerdict:
    """Judge one prospective position against the cost floor.

    ``max_round_trip_frac`` is the friction ceiling above which we refuse to
    trade regardless of signal. 15% is already extreme — it means a coin must
    rise 15% before we are level — and is set there rather than lower because
    meme-coin winners are large enough to clear it. Anything above it, though,
    requires a hit rate that no realistic model delivers.
    """
    model = model or CostModel()
    if notional_usd <= 0:
        return SizingVerdict(
            notional_usd,
            reserve_usd,
            float("inf"),
            float("inf"),
            1.0,
            False,
            "non-positive notional",
        )
    impact = model.price_impact(notional_usd, reserve_usd)
    proportional = 2.0 * notional_usd * (model.venue_fee + impact + model.extra_slippage)
    fee_component = (2.0 / max(1e-9, 1.0 - model.failure_rate)) * model.fixed_fee_usd
    total = proportional + fee_component
    frac = total / notional_usd
    fee_share = fee_component / total if total > 0 else 1.0

    if frac > max_round_trip_frac:
        if fee_share > 0.5:
            reason = (
                f"position too small: flat fees are {fee_share:.0%} of friction "
                f"({frac:.1%} round trip)"
            )
        else:
            reason = f"pool too thin: {frac:.1%} round-trip friction at ${notional_usd:,.0f}"
        return SizingVerdict(notional_usd, reserve_usd, frac, frac, fee_share, False, reason)

    return SizingVerdict(
        notional_usd, reserve_usd, frac, frac, fee_share, True, "within cost floor"
    )


def max_viable_notional(
    reserve_usd: float,
    model: CostModel | None = None,
    *,
    max_round_trip_frac: float = 0.15,
) -> float:
    """Largest position this pool can absorb inside the friction ceiling.

    Solves ``2*(venue + 2N/R + slip)*N + F = c*N`` for N, i.e. the point where
    growing impact eats the whole budget. Returns 0.0 when even an infinitely
    small trade cannot clear the flat fee.
    """
    model = model or CostModel()
    if reserve_usd <= 0:
        return 0.0
    fee = (2.0 / max(1e-9, 1.0 - model.failure_rate)) * model.fixed_fee_usd
    # (4/R) N^2 + (2*(venue+slip) - c) N + fee = 0
    a = 4.0 / reserve_usd
    b = 2.0 * (model.venue_fee + model.extra_slippage) - max_round_trip_frac
    disc = b * b - 4.0 * a * fee
    if disc < 0:
        return 0.0
    root = (-b - math.sqrt(disc)) / (2.0 * a)
    upper = (-b + math.sqrt(disc)) / (2.0 * a)
    # Two roots bracket the viable band: below `root` flat fees dominate,
    # above `upper` impact does. Return the top of the band.
    return max(0.0, upper) if upper > 0 else max(0.0, root)


def min_viable_notional(
    reserve_usd: float,
    model: CostModel | None = None,
    *,
    max_round_trip_frac: float = 0.15,
) -> float:
    """Smallest position whose flat fees stay inside the friction ceiling."""
    model = model or CostModel()
    if reserve_usd <= 0:
        return float("inf")
    fee = (2.0 / max(1e-9, 1.0 - model.failure_rate)) * model.fixed_fee_usd
    a = 4.0 / reserve_usd
    b = 2.0 * (model.venue_fee + model.extra_slippage) - max_round_trip_frac
    disc = b * b - 4.0 * a * fee
    if disc < 0:
        return float("inf")
    lower = (-b - math.sqrt(disc)) / (2.0 * a)
    return max(0.0, lower)
