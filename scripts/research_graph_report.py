"""Stage 12: build the research graph from this corpus and report on it.

    .venv/Scripts/python scripts/research_graph_report.py

Every node and edge below cites the committed document it was read from.
Nothing here is inferred, scored, or promoted — the graph records what the
corpus already says and then asks three questions of it:

* what would be affected if the deployed spec is wrong (H59 made that live);
* is any claimed confirmation actually correlated evidence counted twice;
* is anything recorded but never connected to anything else.

The orphan check earned its keep on first run: it flagged H59's control cell
as unconnected, which was a real omission — the control is what licenses
reading cells 1 and 2 at all. MF1-continuation is still listed as an orphan
and is left that way honestly: its support is not encoded here, and inventing
edges to silence a warning would defeat the check.

Deliberately NOT exhaustive over 125 trials. It encodes the load-bearing
spine — the deployed spec, the findings it rests on, and the meta-findings
whose support is worth auditing. A graph that claimed to cover everything
while quietly omitting rows would be worse than one with a stated scope.
"""

from __future__ import annotations

from trading_bot.research.graph import (
    Edge,
    EdgeKind,
    Node,
    NodeKind,
    ResearchGraph,
)

MEM = "PROJECT_MEMORY.md"
H59 = "docs/hypotheses/59-live-drawdown-consistency.md"
H58 = "docs/hypotheses/58-learned-indicator-ensemble.md"

NODES = [
    # --- specs ---
    Node("rotation-stop", NodeKind.SPEC, "deployed spec: rotation + chandelier stop", MEM),
    Node("rotation", NodeKind.SPEC, "unstopped 90d cross-sectional momentum", MEM),
    Node("vol-target", NodeKind.SPEC, "V1 vol-target trend, per-symbol lookback", MEM),
    # --- findings the deployed spec rests on ---
    Node("H11-breadth", NodeKind.FINDING, "rotation strengthens on 40 coins vs 8", MEM),
    Node("H40-stops-help", NodeKind.FINDING, "post-stop-fire fwd30 -8.77%, CI clear", MEM),
    Node("H42b-beats-champion", NodeKind.FINDING, "rot-stop beats rotation on all metrics", MEM),
    Node("H36-no-short-leg", NodeKind.FINDING, "bottom-2 does not keep falling", MEM),
    # --- today's results ---
    Node("H59-rotstop-inconsistent", NodeKind.FINDING, "live month p=0.008 vs own backtest", H59),
    Node("H59-rotation-inconsistent", NodeKind.FINDING, "live month p=0.006 vs own backtest", H59),
    Node("H59-control-clean", NodeKind.FINDING, "vol-target consistent p=0.49", H59),
    Node("H58-equal-beats-learned", NodeKind.FINDING, "equal weights beat learned weights", H58),
    Node("H33-blend-killed", NodeKind.FINDING, "info-significant blend failed at strategy", MEM),
    # --- meta-findings ---
    Node("MF4-info-not-strategy", NodeKind.META_FINDING, "info-signal != strategy gain", MEM),
    Node("MF5-correlation-joins", NodeKind.META_FINDING, "diversification needs joined corr", MEM),
    Node("MF1-continuation", NodeKind.META_FINDING, "crypto continues at daily+", MEM),
    # --- an open lead, never a finding ---
    Node("LEAD-wrong-objective", NodeKind.LEAD, "direction target != return payoff", H58),
]

EDGES = [
    # what the deployed spec rests on
    Edge("rotation-stop", "H42b-beats-champion", EdgeKind.DEPENDS_ON, MEM),
    Edge("rotation-stop", "H40-stops-help", EdgeKind.DEPENDS_ON, MEM),
    Edge("rotation-stop", "H36-no-short-leg", EdgeKind.DEPENDS_ON, MEM),
    Edge("H42b-beats-champion", "H11-breadth", EdgeKind.DEPENDS_ON, MEM),
    Edge("rotation", "H11-breadth", EdgeKind.DEPENDS_ON, MEM),
    # today's findings, and what they are about
    Edge("H59-rotstop-inconsistent", "rotation-stop", EdgeKind.DEPENDS_ON, H59),
    Edge("H59-rotation-inconsistent", "rotation", EdgeKind.DEPENDS_ON, H59),
    # the claim both cells appear to support
    Edge("H59-rotstop-inconsistent", "MF5-correlation-joins", EdgeKind.SUPPORTS, H59),
    Edge("H59-rotation-inconsistent", "MF5-correlation-joins", EdgeKind.SUPPORTS, H59),
    # ...and the measured correlation that makes them ONE observation
    Edge(
        "H59-rotstop-inconsistent",
        "H59-rotation-inconsistent",
        EdgeKind.CORRELATED_WITH,
        MEM,
        0.821,
    ),
    # the control cell, which is what licenses reading cells 1 and 2 at all
    Edge("H59-control-clean", "vol-target", EdgeKind.DEPENDS_ON, H59),
    # meta-finding 4's support
    Edge("H58-equal-beats-learned", "MF4-info-not-strategy", EdgeKind.SUPPORTS, H58),
    Edge("H33-blend-killed", "MF4-info-not-strategy", EdgeKind.SUPPORTS, MEM),
    Edge("LEAD-wrong-objective", "H58-equal-beats-learned", EdgeKind.DEPENDS_ON, H58),
]


def build() -> ResearchGraph:
    graph = ResearchGraph()
    for node in NODES:
        graph.add_node(node)
    for edge in EDGES:
        graph.add_edge(edge)
    return graph


def main() -> None:
    graph = build()
    print(f"research graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    print("scope: the load-bearing spine, NOT all 125 trials\n")

    print("=== if rotation-stop is wrong, what is affected? ===")
    impact = graph.impact_of("rotation-stop")
    print(f"  {len(impact)} node(s): {', '.join(impact) or 'none recorded'}")
    print("  (H59 made this a live question, not a hypothetical)\n")

    print("=== what does the deployed spec rest on? ===")
    for name in graph.depends_on("rotation-stop"):
        print(f"  {name:<26} {graph.nodes[name].summary}")

    print("\n=== is any claimed support actually independent? ===")
    for claim in ("MF5-correlation-joins", "MF4-info-not-strategy"):
        print(graph.independent_support(claim).describe())

    print("\n=== integrity ===")
    cycles = "YES — modelling bug" if graph.cycles_in_dependencies() else "none"
    print(f"  dependency cycles : {cycles}")
    conflicts = graph.contradictions()
    print(f"  support+contradict: {conflicts or 'none'}")
    orphans = graph.orphans()
    print(f"  orphaned nodes    : {', '.join(orphans) if orphans else 'none'}")


if __name__ == "__main__":
    main()
