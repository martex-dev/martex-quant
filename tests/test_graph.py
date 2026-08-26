"""The research graph is tested on the errors it exists to prevent.

Its traversals are ordinary breadth-first search and are worth a few checks.
Its reason for existing is ``independent_support``, so most of this file is
that: the corpus has twice mistaken correlated observations for independent
confirmation, and a graph that repeated the mistake would be worse than no
graph, because it would launder the error through a tool.
"""

from __future__ import annotations

import pytest

from martex_quant.research.graph import (
    Edge,
    EdgeKind,
    Node,
    NodeKind,
    ResearchGraph,
)

SRC = "docs/hypotheses/test.md"


def node(name: str, kind: NodeKind = NodeKind.FINDING) -> Node:
    return Node(name=name, kind=kind, summary=f"{name} summary", source=SRC)


def graph(*names: str) -> ResearchGraph:
    g = ResearchGraph()
    for name in names:
        g.add_node(node(name))
    return g


class TestConstructionRefusesUncitedClaims:
    def test_a_node_must_cite_a_source(self) -> None:
        with pytest.raises(ValueError, match="committed source"):
            Node(name="n", kind=NodeKind.FINDING, summary="s", source="")

    def test_an_edge_must_cite_a_source(self) -> None:
        with pytest.raises(ValueError, match="cite a source"):
            Edge("a", "b", EdgeKind.SUPPORTS, source="")

    def test_a_correlation_edge_without_a_measurement_is_refused(self) -> None:
        """An asserted correlation is the H12 error in embryo — its 0.35 was
        an artefact of tail-count alignment, not a measurement."""
        with pytest.raises(ValueError, match="assertion, not evidence"):
            Edge("a", "b", EdgeKind.CORRELATED_WITH, source=SRC)

    def test_edges_to_unknown_nodes_are_refused(self) -> None:
        g = graph("a")
        with pytest.raises(KeyError):
            g.add_edge(Edge("a", "ghost", EdgeKind.SUPPORTS, source=SRC))

    def test_duplicate_nodes_are_refused(self) -> None:
        g = graph("a")
        with pytest.raises(ValueError, match="duplicate"):
            g.add_node(node("a"))


class TestTraversal:
    def test_depends_on_is_transitive(self) -> None:
        g = graph("spec", "finding", "hypothesis")
        g.add_edge(Edge("spec", "finding", EdgeKind.DEPENDS_ON, source=SRC))
        g.add_edge(Edge("finding", "hypothesis", EdgeKind.DEPENDS_ON, source=SRC))
        assert g.depends_on("spec") == ["finding", "hypothesis"]

    def test_impact_walks_dependencies_backwards(self) -> None:
        """The question asked of rotation-stop the moment H59 flagged it."""
        g = graph("spec", "downstream", "further")
        g.add_edge(Edge("downstream", "spec", EdgeKind.DEPENDS_ON, source=SRC))
        g.add_edge(Edge("further", "downstream", EdgeKind.DEPENDS_ON, source=SRC))
        assert set(g.impact_of("spec")) == {"downstream", "further"}

    def test_a_node_is_not_its_own_dependency(self) -> None:
        g = graph("a", "b")
        g.add_edge(Edge("a", "b", EdgeKind.DEPENDS_ON, source=SRC))
        assert "a" not in g.depends_on("a")

    def test_dependency_cycles_are_detected(self) -> None:
        g = graph("a", "b")
        g.add_edge(Edge("a", "b", EdgeKind.DEPENDS_ON, source=SRC))
        assert not g.cycles_in_dependencies()
        g.add_edge(Edge("b", "a", EdgeKind.DEPENDS_ON, source=SRC))
        assert g.cycles_in_dependencies()

    def test_unknown_node_raises_rather_than_returning_empty(self) -> None:
        with pytest.raises(KeyError):
            graph("a").depends_on("ghost")


class TestIndependentSupport:
    """The reason this module exists."""

    def test_uncorrelated_supporters_all_count(self) -> None:
        g = graph("claim", "s1", "s2", "s3")
        for s in ("s1", "s2", "s3"):
            g.add_edge(Edge(s, "claim", EdgeKind.SUPPORTS, source=SRC))
        report = g.independent_support("claim")
        assert len(report.independent) == 3
        assert not report.overstated

    def test_the_h59_case_two_cells_correlating_0_821_count_once(self) -> None:
        """rotation and rotation-stop both returned INCONSISTENT. That looks
        like confirmation and is not: one event, seen twice."""
        g = graph("drawdown-anomalous", "rotation", "rotation-stop")
        g.add_edge(Edge("rotation", "drawdown-anomalous", EdgeKind.SUPPORTS, source=SRC))
        g.add_edge(Edge("rotation-stop", "drawdown-anomalous", EdgeKind.SUPPORTS, source=SRC))
        g.add_edge(
            Edge("rotation", "rotation-stop", EdgeKind.CORRELATED_WITH, source=SRC, weight=0.821)
        )
        report = g.independent_support("drawdown-anomalous")
        assert len(report.claimed) == 2
        assert len(report.independent) == 1
        assert report.overstated
        assert report.discounted[0][2] == pytest.approx(0.821)

    def test_the_discount_is_reported_not_silent(self) -> None:
        """Silently shrinking a count would hide that a judgement was made."""
        g = graph("claim", "a", "b")
        for s in ("a", "b"):
            g.add_edge(Edge(s, "claim", EdgeKind.SUPPORTS, source=SRC))
        g.add_edge(Edge("a", "b", EdgeKind.CORRELATED_WITH, source=SRC, weight=0.9))
        text = g.independent_support("claim").describe()
        assert "2 claimed" in text and "1 independent" in text
        assert "OVERSTATES" in text and "0.900" in text

    def test_correlation_below_threshold_does_not_discount(self) -> None:
        """H41's 0.188 sleeve was genuinely the first low-correlation stream
        in the corpus; the graph must not erase that distinction."""
        g = graph("claim", "a", "b")
        for s in ("a", "b"):
            g.add_edge(Edge(s, "claim", EdgeKind.SUPPORTS, source=SRC))
        g.add_edge(Edge("a", "b", EdgeKind.CORRELATED_WITH, source=SRC, weight=0.188))
        assert len(g.independent_support("claim").independent) == 2

    def test_negative_correlation_also_discounts(self) -> None:
        """Two streams at -0.95 are one measurement with a sign flip, not two."""
        g = graph("claim", "a", "b")
        for s in ("a", "b"):
            g.add_edge(Edge(s, "claim", EdgeKind.SUPPORTS, source=SRC))
        g.add_edge(Edge("a", "b", EdgeKind.CORRELATED_WITH, source=SRC, weight=-0.95))
        assert len(g.independent_support("claim").independent) == 1

    def test_a_third_uncorrelated_supporter_survives_the_discount(self) -> None:
        g = graph("claim", "a", "b", "c")
        for s in ("a", "b", "c"):
            g.add_edge(Edge(s, "claim", EdgeKind.SUPPORTS, source=SRC))
        g.add_edge(Edge("a", "b", EdgeKind.CORRELATED_WITH, source=SRC, weight=0.9))
        report = g.independent_support("claim")
        assert report.independent == ["a", "c"]

    def test_threshold_is_a_parameter_not_a_hidden_constant(self) -> None:
        g = graph("claim", "a", "b")
        for s in ("a", "b"):
            g.add_edge(Edge(s, "claim", EdgeKind.SUPPORTS, source=SRC))
        g.add_edge(Edge("a", "b", EdgeKind.CORRELATED_WITH, source=SRC, weight=0.5))
        assert len(g.independent_support("claim", threshold=0.4).independent) == 1
        assert len(g.independent_support("claim", threshold=0.9).independent) == 2


class TestIntegrity:
    def test_a_node_both_supporting_and_contradicting_is_surfaced(self) -> None:
        g = graph("a", "b")
        g.add_edge(Edge("a", "b", EdgeKind.SUPPORTS, source=SRC))
        g.add_edge(Edge("a", "b", EdgeKind.CONTRADICTS, source="docs/other.md"))
        assert g.contradictions() == [("a", "b", "docs/other.md")]

    def test_conflicting_evidence_is_reported_not_deleted(self) -> None:
        """A corpus may legitimately hold conflicting evidence; the graph
        makes it visible rather than resolving it."""
        g = graph("a", "b")
        g.add_edge(Edge("a", "b", EdgeKind.SUPPORTS, source=SRC))
        g.add_edge(Edge("a", "b", EdgeKind.CONTRADICTS, source=SRC))
        assert len(g.edges) == 2

    def test_orphans_are_listed(self) -> None:
        g = graph("connected", "other", "lonely")
        g.add_edge(Edge("connected", "other", EdgeKind.SUPPORTS, source=SRC))
        assert g.orphans() == ["lonely"]
