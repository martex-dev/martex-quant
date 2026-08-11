"""Stage 12: the research graph — what depends on what, and what would break.

A 125-trial corpus has a problem no individual document can solve: nobody can
hold in their head which findings lean on which other findings. When a
deployed spec is questioned — as rotation-stop was by H59 — the load-bearing
question is *what else did we conclude that assumed it was sound?* Answering
that by re-reading twenty documents is how corpora quietly rot.

The graph exists to answer three questions and deliberately refuses to answer
more:

1. **What does this finding depend on?** (ancestors)
2. **What would be affected if this turned out to be wrong?** (descendants)
3. **Is this meta-finding's support actually independent?**

The third is the one with teeth, and it is here because this project has made
that exact error twice. H12 nearly justified a combined book on a correlation
of 0.35 that was really 0.77. H59 produced two INCONSISTENT cells that look
like confirmation but correlate at 0.821 — one event seen twice. So
``independent_support`` does not count supporting nodes; it counts them and
then DISCOUNTS any pair joined by a ``CORRELATED_WITH`` edge above a
threshold, and it reports what it discounted rather than silently shrinking a
number.

What this module does NOT do, on purpose: it assigns no confidence scores,
computes no aggregate "strength of evidence", and promotes nothing. A graph
that scores its own nodes invites the reader to trust the score instead of
the sources. Edges are recorded facts with citations; weighing them is a
human act.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum


class NodeKind(StrEnum):
    HYPOTHESIS = "hypothesis"
    FINDING = "finding"
    META_FINDING = "meta_finding"
    SPEC = "spec"  # a deployed or archived strategy
    LEAD = "lead"  # an anomaly; never a finding


class EdgeKind(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    SUPERSEDES = "supersedes"
    #: Two nodes measuring substantially the same underlying event. The
    #: weight is the measured correlation, and it is what stops repeated
    #: observations of one event from being counted as replication.
    CORRELATED_WITH = "correlated_with"


#: Above this, two supporting nodes are treated as one observation. 0.7 is a
#: judgement call, stated here rather than buried: H12's true 0.77 was
#: described in the ledger as "blend averages, doesn't insure", and H59's
#: 0.821 pair is plainly one event. Both sit above it; the threshold is a
#: declared convention, not a derived constant.
INDEPENDENCE_THRESHOLD = 0.7


@dataclass(frozen=True)
class Node:
    name: str
    kind: NodeKind
    summary: str
    source: str  # the committed document this came from

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError(f"{self.name}: every node must cite a committed source")


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: EdgeKind
    source: str
    weight: float | None = None  # correlation, for CORRELATED_WITH

    def __post_init__(self) -> None:
        if self.kind is EdgeKind.CORRELATED_WITH and self.weight is None:
            raise ValueError(
                f"{self.src}->{self.dst}: a CORRELATED_WITH edge without a measured "
                "correlation is an assertion, not evidence"
            )
        if not self.source:
            raise ValueError(f"{self.src}->{self.dst}: every edge must cite a source")


@dataclass(frozen=True)
class SupportReport:
    """Support for a claim, with non-independent evidence discounted.

    ``claimed`` and ``independent`` are reported together, always. Reporting
    only the discounted count would hide that the discount happened; reporting
    only the raw count is the error this class exists to prevent.
    """

    claim: str
    claimed: list[str]
    independent: list[str]
    discounted: list[tuple[str, str, float]]

    @property
    def overstated(self) -> bool:
        return len(self.independent) < len(self.claimed)

    def describe(self) -> str:
        lines = [
            f"{self.claim}: {len(self.claimed)} claimed confirmation(s), "
            f"{len(self.independent)} independent"
        ]
        for a, b, r in self.discounted:
            lines.append(f"  DISCOUNTED: {a} and {b} correlate {r:.3f} — one event, seen twice")
        if self.overstated:
            lines.append("  ** the raw count OVERSTATES the evidence **")
        return "\n".join(lines)


@dataclass
class ResearchGraph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        if node.name in self.nodes:
            raise ValueError(f"duplicate node {node.name}")
        self.nodes[node.name] = node

    def add_edge(self, edge: Edge) -> None:
        for end in (edge.src, edge.dst):
            if end not in self.nodes:
                raise KeyError(f"edge references unknown node {end}")
        self.edges.append(edge)

    # --- traversal ------------------------------------------------------

    def _walk(self, start: str, *, forward: bool, kinds: set[EdgeKind]) -> list[str]:
        """Breadth-first over the chosen edge kinds, excluding the start."""
        if start not in self.nodes:
            raise KeyError(start)
        seen: set[str] = {start}
        order: list[str] = []
        queue: deque[str] = deque([start])
        while queue:
            current = queue.popleft()
            for edge in self.edges:
                if edge.kind not in kinds:
                    continue
                a, b = (edge.src, edge.dst) if forward else (edge.dst, edge.src)
                if a == current and b not in seen:
                    seen.add(b)
                    order.append(b)
                    queue.append(b)
        return order

    def depends_on(self, name: str) -> list[str]:
        """Everything this node rests on, transitively."""
        return self._walk(name, forward=True, kinds={EdgeKind.DEPENDS_ON})

    def impact_of(self, name: str) -> list[str]:
        """Everything that would be affected if this node turned out wrong.

        The question asked of rotation-stop the moment H59 flagged it. Walks
        DEPENDS_ON backwards and SUPPORTS forwards, because a finding is
        implicated both by resting on a node and by being cited as support
        for one.
        """
        upstream = self._walk(name, forward=False, kinds={EdgeKind.DEPENDS_ON})
        supported = self._walk(name, forward=True, kinds={EdgeKind.SUPPORTS})
        out = list(dict.fromkeys([*upstream, *supported]))
        return out

    # --- the query with teeth -------------------------------------------

    def correlation_between(self, a: str, b: str) -> float | None:
        for edge in self.edges:
            if edge.kind is not EdgeKind.CORRELATED_WITH:
                continue
            if {edge.src, edge.dst} == {a, b}:
                return edge.weight
        return None

    def independent_support(
        self, claim: str, *, threshold: float = INDEPENDENCE_THRESHOLD
    ) -> SupportReport:
        """Supporters of ``claim``, with correlated pairs collapsed to one.

        Greedy and order-stable: supporters are taken in insertion order and
        a candidate is dropped if it correlates above the threshold with any
        already-kept supporter. Greedy rather than optimal on purpose — the
        result must be reproducible and explainable, and 'which maximal
        independent set' is not a question this corpus should be answering
        with a solver.
        """
        if claim not in self.nodes:
            raise KeyError(claim)
        claimed = [e.src for e in self.edges if e.kind is EdgeKind.SUPPORTS and e.dst == claim]

        kept: list[str] = []
        discounted: list[tuple[str, str, float]] = []
        for candidate in claimed:
            collides = False
            for chosen in kept:
                r = self.correlation_between(candidate, chosen)
                if r is not None and abs(r) >= threshold:
                    discounted.append((chosen, candidate, r))
                    collides = True
                    break
            if not collides:
                kept.append(candidate)
        return SupportReport(claim, claimed, kept, discounted)

    # --- integrity ------------------------------------------------------

    def contradictions(self) -> list[tuple[str, str, str]]:
        """Pairs where one node both supports and contradicts another.

        Not an error to fix automatically — a corpus CAN legitimately hold
        conflicting evidence — but it must be visible rather than latent.
        """
        supports = {(e.src, e.dst) for e in self.edges if e.kind is EdgeKind.SUPPORTS}
        out: list[tuple[str, str, str]] = []
        for edge in self.edges:
            if edge.kind is EdgeKind.CONTRADICTS and (edge.src, edge.dst) in supports:
                out.append((edge.src, edge.dst, edge.source))
        return out

    def orphans(self) -> list[str]:
        """Nodes with no edges at all — recorded but never connected."""
        touched = {end for e in self.edges for end in (e.src, e.dst)}
        return [n for n in self.nodes if n not in touched]

    def cycles_in_dependencies(self) -> bool:
        """DEPENDS_ON must be acyclic; a dependency cycle is a modelling bug.

        Three-colour DFS rather than reachability via ``_walk``. ``_walk``
        marks its start as already seen so a node is never reported as its
        own dependency — correct for traversal, but it makes the start
        unreachable and so blind to exactly the cycle being looked for.
        """
        adjacency: dict[str, list[str]] = {name: [] for name in self.nodes}
        for edge in self.edges:
            if edge.kind is EdgeKind.DEPENDS_ON:
                adjacency[edge.src].append(edge.dst)

        white, grey, black = 0, 1, 2
        colour = dict.fromkeys(self.nodes, white)

        def visit(name: str) -> bool:
            colour[name] = grey
            for nxt in adjacency[name]:
                if colour[nxt] == grey:  # back edge into the current path
                    return True
                if colour[nxt] == white and visit(nxt):
                    return True
            colour[name] = black
            return False

        return any(colour[name] == white and visit(name) for name in self.nodes)
