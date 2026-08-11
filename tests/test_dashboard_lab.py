"""The lab panel is tested on the two ways a dashboard lies.

First: showing a total without the gap behind it, which presents a
reconstructed number as a verified one. Second: rendering "unavailable" as
though it were "clean" — an empty audit and a broken audit must never look
alike, because the second is the one that matters.
"""

from __future__ import annotations

from pathlib import Path

from trading_bot.dashboard.lab import (
    gather_lab,
    independence_audit,
    ledger_summary,
    recent_hypotheses,
)

ROOT = Path(__file__).resolve().parents[1]


class TestLedgerSummary:
    def test_reads_the_real_ledger(self) -> None:
        summary = ledger_summary(ROOT)
        assert summary["available"]
        assert summary["total"] == summary["run"] + summary["data_blocked"]

    def test_the_documentation_gap_is_surfaced_not_folded_in(self) -> None:
        """Showing only the total would present a reconstructed number as a
        verified one. The gap is a real property of this corpus."""
        summary = ledger_summary(ROOT)
        assert summary["unallocated"] == summary["total"] - summary["documented"]
        assert summary["unallocated"] > 0

    def test_a_missing_ledger_is_a_state_not_an_error(self) -> None:
        assert ledger_summary(Path("/nonexistent")) == {"available": False}

    def test_a_malformed_ledger_does_not_raise(self, tmp_path: Path) -> None:
        """A dashboard that 500s on a mid-edit document is one nobody leaves open."""
        (tmp_path / "docs/research/ledger").mkdir(parents=True)
        (tmp_path / "docs/research/ledger/trials.toml").write_text("this is not [ valid toml")
        assert ledger_summary(tmp_path) == {"available": False}


class TestRecentHypotheses:
    def test_newest_first_and_run_state_detected(self) -> None:
        recent = recent_hypotheses(ROOT, limit=3)
        assert recent
        numbers = [h["number"] for h in recent]
        assert numbers == sorted(numbers, reverse=True)
        assert all(h["state"] in {"killed", "run", "registered"} for h in recent)

    def test_h58_is_recorded_as_killed(self) -> None:
        found = [h for h in recent_hypotheses(ROOT, limit=10) if h["number"] == 58]
        assert found and found[0]["state"] == "killed"

    def test_a_missing_directory_yields_nothing_rather_than_raising(self) -> None:
        assert recent_hypotheses(Path("/nonexistent")) == []


class TestIndependenceAudit:
    def test_it_reproduces_the_h59_discount(self) -> None:
        audit = independence_audit(ROOT)
        assert audit["available"]
        overstated = [c for c in audit["claims"] if c["overstated"]]
        assert overstated, "the H59 pair should be discounted to one observation"
        assert any(d["correlation"] == 0.821 for c in overstated for d in c["discounted"])

    def test_unavailable_is_distinguishable_from_clean(self) -> None:
        """The failure that would matter: a broken audit rendering as an empty
        one, which reads as 'nothing wrong'."""
        audit = independence_audit(Path("/nonexistent"))
        assert audit["available"] is False
        assert audit["reason"]
        assert "claims" not in audit


class TestGatherLab:
    def test_the_payload_is_json_shaped_and_complete(self) -> None:
        import json

        payload = gather_lab(ROOT)
        assert set(payload) == {"ledger", "recent", "independence"}
        json.dumps(payload)  # must serialise for the endpoint
