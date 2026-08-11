"""Load the committed ledger documents into records, and index them.

Direction of authority, in one line: **documents -> records -> index**, never
back. ``rebuild_index`` can be deleted and regenerated at any time; the TOML
under docs/research/ledger/ cannot.

Trial ids are assigned deterministically from document order, so rebuilding
produces byte-identical ids without storing them — the document stays the
identity, and the index stays disposable.
"""

from __future__ import annotations

import sqlite3
import tomllib
from dataclasses import replace
from pathlib import Path
from typing import Any

from trading_bot.research.ledger.records import Family, Ledger, Trial
from trading_bot.research.ledger.vocabulary import Grade, Maturity, Protocol, Verdict

LEDGER_DIR = Path("docs") / "research" / "ledger"
TRIALS_FILE = "trials.toml"

_MATURITY_BY_CODE = {m.value: m for m in Maturity}


def load_ledger(root: Path) -> Ledger:
    """Parse the committed ledger documents into an in-memory Ledger.

    Each document entry may cover several trials (a batch declares "+9"), so
    entries expand into individual Trial records sharing the batch's labels.
    Expansion is what gives every trial an identity while keeping the
    document reviewable at the granularity its evidence actually supports.
    """
    payload = _read_toml(root / LEDGER_DIR / TRIALS_FILE)
    entries: list[dict[str, Any]] = payload["entries"]

    trials: list[Trial] = []
    families: dict[str, int] = {}
    next_id = 1

    for entry in entries:
        count = int(entry["trial_count"])
        ran = int(entry.get("run_count", count))
        family = str(entry["family"])
        families[family] = families.get(family, 0) + count
        for seq in range(count):
            trials.append(
                Trial(
                    trial_id=next_id,
                    hypothesis=entry["hypothesis"]
                    if count == 1
                    else f"{entry['hypothesis']}#{seq + 1}",
                    family=family,
                    grade=Grade(entry["grade"]),
                    protocol=Protocol(entry["protocol"]),
                    verdict=Verdict(entry["verdict"]),
                    maturity=_MATURITY_BY_CODE[entry["maturity"]],
                    source=entry["source"],
                    evidence=entry["evidence"],
                    ran=seq < ran,
                    # The published DSR belongs to the batch's headline spec,
                    # carried on its first trial only so the corpus total is
                    # not multiplied by the batch size.
                    dsr=float(entry["dsr"]) if seq == 0 and "dsr" in entry else None,
                    dsr_n_trials=int(entry["dsr_n_trials"])
                    if seq == 0 and "dsr" in entry
                    else None,
                    selection_set=entry.get("selection_set"),
                    notes=entry.get("notes", ""),
                )
            )
            next_id += 1

    documented = sum(int(e["trial_count"]) for e in entries)
    claimed = int(payload["ledger_total_claimed"])
    gap = claimed - documented
    if gap > 0:
        # The unallocated remainder is materialised as real trials so it can
        # never be forgotten by a count that quietly ignores it.
        reason = payload["unallocated"]["reason"]
        for seq in range(gap):
            trials.append(
                Trial(
                    trial_id=next_id,
                    hypothesis=f"UNALLOCATED#{seq + 1}",
                    family="unallocated",
                    grade=Grade.AMBIGUOUS,
                    protocol=Protocol.CONFIRMATORY,
                    verdict=Verdict.INCONCLUSIVE,
                    maturity=Maturity.L3_INITIAL_EVIDENCE,
                    source=str(LEDGER_DIR / TRIALS_FILE),
                    evidence=reason,
                    notes="Documented deltas do not reconcile to the claimed total.",
                )
            )
            next_id += 1
        families["unallocated"] = gap

    period = str(payload["period"])
    family_records = [
        Family(
            family_id=fid,
            description=f"migrated historical family ({cells} trials)",
            declared_cells=cells,
            period=period,
            source=str(LEDGER_DIR / TRIALS_FILE),
        )
        for fid, cells in sorted(families.items())
    ]
    return Ledger(trials=trials, families=family_records)


def ledger_claims(root: Path) -> dict[str, int]:
    """The totals the ledger document itself claims, for reconciliation."""
    payload = _read_toml(root / LEDGER_DIR / TRIALS_FILE)
    return {
        "registered": int(payload["ledger_total_claimed"]),
        "run": int(payload["ledger_run_claimed"]),
        "data_blocked": int(payload["ledger_data_blocked_claimed"]),
        "documented": sum(int(e["trial_count"]) for e in payload["entries"]),
    }


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        payload: dict[str, Any] = tomllib.load(handle)
    return payload


# --- derived index -------------------------------------------------------


_SCHEMA = """
CREATE TABLE trial (
    trial_id      INTEGER PRIMARY KEY,
    hypothesis    TEXT NOT NULL,
    family        TEXT NOT NULL,
    grade         TEXT NOT NULL,
    protocol      TEXT NOT NULL,
    verdict       TEXT NOT NULL,
    maturity      TEXT NOT NULL,
    ran           INTEGER NOT NULL,
    dsr           REAL,
    dsr_n_trials  INTEGER,
    selection_set TEXT,
    source        TEXT NOT NULL,
    evidence      TEXT NOT NULL,
    notes         TEXT NOT NULL
);
CREATE TABLE family (
    family_id      TEXT PRIMARY KEY,
    description    TEXT NOT NULL,
    declared_cells INTEGER NOT NULL,
    period         TEXT NOT NULL,
    source         TEXT NOT NULL
);
CREATE INDEX trial_family ON trial(family);
CREATE INDEX trial_verdict ON trial(verdict);
"""


def rebuild_index(ledger: Ledger, destination: Path | None = None) -> sqlite3.Connection:
    """Build the derived SQLite index. Deletable and deterministic.

    ``destination=None`` builds in memory — the common case for tests and
    ad-hoc queries, and a reminder that the index is not a durable artifact.
    """
    if destination is not None and destination.exists():
        destination.unlink()
    connection = sqlite3.connect(":memory:" if destination is None else str(destination))
    connection.executescript(_SCHEMA)
    connection.executemany(
        "INSERT INTO trial VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                t.trial_id,
                t.hypothesis,
                t.family,
                t.grade.value,
                t.protocol.value,
                t.verdict.value,
                t.maturity.value,
                int(t.ran),
                t.dsr,
                t.dsr_n_trials,
                t.selection_set,
                t.source,
                t.evidence,
                t.notes,
            )
            for t in ledger.trials
        ],
    )
    connection.executemany(
        "INSERT INTO family VALUES (?,?,?,?,?)",
        [
            (f.family_id, f.description, f.declared_cells, f.period, f.source)
            for f in ledger.families
        ],
    )
    connection.commit()
    return connection


def index_fingerprint(connection: sqlite3.Connection) -> str:
    """Stable digest of index contents, for the rebuild-determinism test."""
    import hashlib

    digest = hashlib.sha256()
    for table, order in (("trial", "trial_id"), ("family", "family_id")):
        for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}"):  # noqa: S608
            digest.update(repr(row).encode("utf-8"))
    return digest.hexdigest()


def with_trial(ledger: Ledger, trial: Trial) -> Ledger:
    """Append-only helper: returns a NEW ledger, never mutates in place."""
    if any(t.trial_id == trial.trial_id for t in ledger.trials):
        raise ValueError(f"trial_id {trial.trial_id} already exists; ids are never reused")
    return replace(ledger, trials=[*ledger.trials, trial])
