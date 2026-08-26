"""The assistant is tested on the mistakes it exists to catch.

Each blocking rule here corresponds to a real event in this corpus, so the
tests are written against those events rather than against invented cases.
"""

from __future__ import annotations

from pathlib import Path

from martex_quant.research.assistant import (
    Objection,
    Proposal,
    Severity,
    killed_hypotheses,
    review,
)

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/research/ledger/trials.toml"


def sound(**overrides: object) -> Proposal:
    """A proposal that violates nothing, so each test can break ONE thing."""
    base = {
        "name": "H60",
        "claim": "something testable",
        "trial_count": 2,
        "beats": "the deployed rotation-stop book",
        "preregistration": "docs/hypotheses/60-x.md",
    }
    base.update(overrides)
    return Proposal(**base)  # type: ignore[arg-type]


def rules(objections: list[Objection]) -> set[str]:
    return {o.rule for o in objections}


class TestKilledHypothesisExpansion:
    def test_ranges_expand_so_duplicates_cannot_hide(self) -> None:
        """The ledger writes 'H44-H50'. A literal match would miss H45-H49 —
        exactly how a duplicate slips through."""
        killed = killed_hypotheses(LEDGER)
        assert {"H44", "H45", "H46", "H47", "H48", "H49", "H50"} <= killed

    def test_single_names_survive(self) -> None:
        assert "H58" in killed_hypotheses(LEDGER)

    def test_non_hypothesis_names_are_not_mangled(self) -> None:
        killed = killed_hypotheses(LEDGER)
        assert not any(k.startswith("H") and k[1:].isdigit() and int(k[1:]) > 200 for k in killed)


class TestBlockingRules:
    def test_missing_preregistration_blocks(self) -> None:
        result = review(sound(preregistration=""), ledger_total=125, killed=set())
        assert "no pre-registration" in rules(result.blocking)

    def test_beating_zero_blocks(self) -> None:
        """The single most common way a dead idea survives review."""
        result = review(sound(beats="zero"), ledger_total=125, killed=set())
        assert "incremental bar is zero" in rules(result.blocking)

    def test_no_bar_at_all_blocks(self) -> None:
        result = review(sound(beats=""), ledger_total=125, killed=set())
        assert "no incremental bar declared" in rules(result.blocking)

    def test_learning_weights_without_an_equal_weight_baseline_blocks(self) -> None:
        """H58's standing consequence: the baseline has now actually won."""
        result = review(
            sound(learns_parameters=True, declares_equal_weight_baseline=False),
            ledger_total=125,
            killed=set(),
        )
        objection = next(o for o in result.blocking if "equal-weight" in o.rule)
        assert "H58" in objection.detail

    def test_declaring_the_baseline_clears_it(self) -> None:
        result = review(
            sound(learns_parameters=True, declares_equal_weight_baseline=True),
            ledger_total=125,
            killed=set(),
        )
        assert not any("equal-weight" in r for r in rules(result.blocking))

    def test_zero_trials_blocks(self) -> None:
        result = review(sound(trial_count=0), ledger_total=125, killed=set())
        assert "trial count not declared" in rules(result.blocking)


class TestRevisitingKills:
    def test_retesting_a_kill_without_a_reason_blocks(self) -> None:
        result = review(sound(revisits=("H33",)), ledger_total=125, killed={"H33"})
        assert any("re-tests killed" in r for r in rules(result.blocking))

    def test_a_substantive_reason_downgrades_it_to_caution(self) -> None:
        result = review(
            sound(
                revisits=("H33",),
                reason_for_revisiting="new maker-fill data unavailable at the original run",
            ),
            ledger_total=125,
            killed={"H33"},
        )
        assert not result.blocking
        assert any("re-tests killed" in o.rule for o in result.objections)

    def test_a_token_reason_does_not_satisfy_the_rule(self) -> None:
        result = review(
            sound(revisits=("H33",), reason_for_revisiting="worth another look"),
            ledger_total=125,
            killed={"H33"},
        )
        assert result.blocking

    def test_revisiting_a_surviving_hypothesis_is_not_flagged(self) -> None:
        result = review(sound(revisits=("H42",)), ledger_total=125, killed={"H33"})
        assert not any("re-tests killed" in r for r in rules(result.objections))


class TestLedgerCostAndFraming:
    def test_the_cost_is_computed_not_asserted(self) -> None:
        result = review(sound(trial_count=5), ledger_total=125, killed=set())
        assert result.ledger_after == 130

    def test_strategy_grade_raises_a_caution_naming_the_new_total(self) -> None:
        result = review(sound(grade="strategy", trial_count=3), ledger_total=125, killed=set())
        caution = next(o for o in result.objections if o.rule == "strategy grade claimed")
        assert "128" in caution.detail
        assert caution.severity is Severity.CAUTION

    def test_a_clean_review_refuses_to_call_itself_approval(self) -> None:
        """A checker that says APPROVED gets read as authorization."""
        text = review(sound(), ledger_total=125, killed=set()).describe()
        assert "NOT approval" in text
        assert "approved" not in text.lower().replace("not approval", "")

    def test_every_objection_cites_where_the_rule_is_written(self) -> None:
        result = review(
            sound(beats="zero", preregistration="", learns_parameters=True),
            ledger_total=125,
            killed=set(),
        )
        assert result.objections
        assert all(o.source for o in result.objections)
