"""Stage 14: the lab's state, gathered for the dashboard.

The existing dashboard answers "what is my money doing". This answers "what
does the research say, and how much of it should I trust" — deliberately a
separate module so the trading view cannot break when a research document is
malformed, and vice versa.

Same discipline as ``data.py``: pure reads, defensive everywhere, a missing
file is a "not recorded yet" state rather than an error. A dashboard that
500s because a hypothesis document was mid-edit is a dashboard nobody leaves
open.

One framing rule carried over from the lab itself: this surfaces the ledger's
own numbers and the graph's own audit. It computes no new verdicts. A
dashboard that derived its own conclusions would become a second, unversioned
source of truth competing with PROJECT_MEMORY.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

LEDGER = "docs/research/ledger/trials.toml"
HYPOTHESES = "docs/hypotheses"
MAX_RECENT = 6


def _ledger(base: Path) -> dict[str, Any]:
    path = base / LEDGER
    if not path.exists():
        return {}
    try:
        payload: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return {}
    return payload


def ledger_summary(base: Path) -> dict[str, Any]:
    """Headline counts, plus the documentation gap carried explicitly.

    The gap is surfaced rather than hidden because it is a real property of
    this corpus: documented per-hypothesis deltas do not sum to the claimed
    total, and the difference is carried as unallocated rather than
    distributed by guess. A dashboard that showed only the total would quietly
    present a reconstructed number as a verified one.
    """
    payload = _ledger(base)
    if not payload:
        return {"available": False}
    entries = payload.get("entries", [])
    documented = sum(int(e.get("trial_count", 0)) for e in entries)
    total = int(payload.get("ledger_total_claimed", 0))
    verdicts: dict[str, int] = {}
    for entry in entries:
        verdict = str(entry.get("verdict", "unrecorded"))
        verdicts[verdict] = verdicts.get(verdict, 0) + int(entry.get("trial_count", 0))
    return {
        "available": True,
        "total": total,
        "run": int(payload.get("ledger_run_claimed", 0)),
        "data_blocked": int(payload.get("ledger_data_blocked_claimed", 0)),
        "documented": documented,
        "unallocated": total - documented,
        "by_verdict": verdicts,
        "families": len({str(e.get("family", "")) for e in entries}),
    }


_VERDICT_LINE = re.compile(r"^\s*\*\*(?:H\d+\s+)?(KILLED|CANDIDATE|SIGNAL)", re.MULTILINE)


def recent_hypotheses(base: Path, limit: int = MAX_RECENT) -> list[dict[str, Any]]:
    """The most recent registrations, newest first, with run state.

    'Has a VERDICT section' is the honest signal for whether something ran —
    it is what the corpus actually uses, rather than a status field that can
    drift from reality.
    """
    directory = base / HYPOTHESES
    if not directory.is_dir():
        return []
    docs: list[tuple[int, Path]] = []
    for path in directory.glob("*.md"):
        match = re.match(r"^(\d+)", path.name)
        if match:
            docs.append((int(match.group(1)), path))
    docs.sort(key=lambda pair: pair[0], reverse=True)

    out: list[dict[str, Any]] = []
    for number, path in docs[:limit]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        has_verdict = "## VERDICT" in text
        killed = "KILLED" in text
        out.append(
            {
                "number": number,
                "title": _title(text) or path.stem,
                "path": f"{HYPOTHESES}/{path.name}",
                "state": ("killed" if killed else "run") if has_verdict else "registered",
            }
        )
    return out


def _title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def independence_audit(base: Path) -> dict[str, Any]:
    """The research graph's independence audit, if the graph is populated.

    Imported lazily and guarded: the dashboard must not fail to render
    because a research module raised. If the graph is unavailable the panel
    says so rather than showing an empty audit that looks like a clean one —
    those two states must never be confused.
    """
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "research_graph_report", base / "scripts/research_graph_report.py"
        )
        if spec is None or spec.loader is None:
            return {"available": False, "reason": "graph script not found"}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        graph = module.build()
    except Exception as exc:  # noqa: BLE001 — a dashboard never propagates
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}

    claims: list[dict[str, Any]] = []
    for name, node in graph.nodes.items():
        if node.kind != "meta_finding":
            continue
        report = graph.independent_support(name)
        if not report.claimed:
            continue
        claims.append(
            {
                "claim": name,
                "claimed": len(report.claimed),
                "independent": len(report.independent),
                "overstated": report.overstated,
                "discounted": [
                    {"a": a, "b": b, "correlation": round(r, 3)} for a, b, r in report.discounted
                ],
            }
        )
    return {
        "available": True,
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "claims": claims,
        "orphans": graph.orphans(),
    }


def gather_lab(base: Path) -> dict[str, Any]:
    return {
        "ledger": ledger_summary(base),
        "recent": recent_hypotheses(base),
        "independence": independence_audit(base),
    }
