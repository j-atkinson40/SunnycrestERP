"""The ponder walks every arm of a fork, not one of them.

THE PRIOR WALK DROPPED PATHS SILENTLY. `_ordered_nodes` built its successor map
as `{e["source"]: e["target"] for e in edges}` — a dict comprehension, so a node
with two outgoing edges kept only the LAST-declared one and the other arm fell
out of the walk. Its own docstring named this as its stop condition, which is
why this is a deliberate flip rather than a bug fix.

WHY IT MATTERS: the accounting mirrors are not linear once reconciliation is
taught. That process is nothing BUT forks — matched vs unmatched, keyword vs
coded, viable vs blocked, void vs return. A linear walk picks one arm
arbitrarily and presents it as *the* path, teaching a process that does not
exist. A ponder that teaches the wrong path is worse than one that teaches
nothing, because it is believed.

THE LOAD-BEARING GUARANTEE IS THE LINEAR CASE. Every mirror rendering today is
linear; if any of those moved, this change would be a regression wearing a
feature. `TestLinearCanvasesAreByteIdentical` is the characterization, and it is
written against the OLD algorithm reimplemented in the test rather than against
recorded output — so it proves equivalence, not merely stability.

Pure functions over dict literals: no DB, no tenants, no cleanup needed.
"""
from __future__ import annotations

from app.services.maps_of_content.ponder import _ordered_nodes, motif_for_step


def _canvas(node_ids, edges):
    return {
        "nodes": [{"id": n, "type": "action", "label": n} for n in node_ids],
        "edges": [{"source": s, "target": t} for s, t in edges],
    }


def _ids(result):
    return [n["id"] for n in result]


def _old_walk(canvas):
    """The PRIOR implementation, verbatim in behaviour — the equivalence oracle
    for the linear case. Kept here rather than trusting recorded output, so the
    characterization proves the two algorithms AGREE rather than proving this
    one has not changed."""
    nodes = {n["id"]: n for n in canvas.get("nodes", [])}
    edges = canvas.get("edges", [])
    targets = {e["target"] for e in edges}
    nexts = {e["source"]: e["target"] for e in edges}
    roots = [nid for nid in nodes if nid not in targets]
    if not roots:
        return list(nodes.values())
    ordered, seen, cur = [], set(), roots[0]
    while cur and cur in nodes and cur not in seen:
        ordered.append(nodes[cur]); seen.add(cur); cur = nexts.get(cur)
    ordered += [n for nid, n in nodes.items() if nid not in seen]
    return ordered


class TestLinearCanvasesAreByteIdentical:
    """THE CHARACTERIZATION. Nothing that renders today may move."""

    def test_a_straight_chain_matches_the_old_walk_exactly(self):
        c = _canvas(["start", "a", "b", "end"],
                    [("start", "a"), ("a", "b"), ("b", "end")])
        assert _ids(_ordered_nodes(c)) == _ids(_old_walk(c)) == [
            "start", "a", "b", "end"]

    def test_a_chain_with_a_disconnected_leftover_matches(self):
        """Leftovers still append in declaration order — the old behaviour, and
        deliberately kept: an orphan node is visible rather than dropped."""
        c = _canvas(["start", "a", "orphan"], [("start", "a")])
        assert _ids(_ordered_nodes(c)) == _ids(_old_walk(c)) == [
            "start", "a", "orphan"]

    def test_a_canvas_with_no_root_matches(self):
        """Every node has an incoming edge (a pure cycle). Both fall back to
        declaration order."""
        c = _canvas(["a", "b"], [("a", "b"), ("b", "a")])
        assert _ids(_ordered_nodes(c)) == _ids(_old_walk(c)) == ["a", "b"]

    def test_an_empty_canvas_matches(self):
        c = _canvas([], [])
        assert _ordered_nodes(c) == _old_walk(c) == []


class TestAForkNoLongerLosesAnArm:
    def test_BOTH_arms_are_walked(self):
        """THE FIX. Old walk: `nexts` keeps only the last-declared edge from
        `check`, so `matched` never appears in the walk — it lands in the
        leftover sweep, AFTER everything, divorced from the fork it belongs to.
        """
        c = _canvas(
            ["start", "check", "matched", "unmatched", "done"],
            [("start", "check"), ("check", "matched"), ("check", "unmatched"),
             ("matched", "done")],
        )

        got = _ids(_ordered_nodes(c))

        assert got.index("check") < got.index("matched")
        assert got.index("check") < got.index("unmatched")
        assert set(got) == {"start", "check", "matched", "unmatched", "done"}

    def test_the_old_walk_DID_lose_it_relative_to_the_fork(self):
        """The inversion, pinned. Under the old walk `matched` sorted after the
        whole chain rather than under its fork — the arm was not traversed, it
        merely survived as a leftover."""
        c = _canvas(
            ["start", "check", "matched", "unmatched"],
            [("start", "check"), ("check", "matched"), ("check", "unmatched")],
        )

        old = _ids(_old_walk(c))
        assert old == ["start", "check", "unmatched", "matched"]  # arm stranded
        assert _ids(_ordered_nodes(c)) == ["start", "check", "matched", "unmatched"]

    def test_each_arm_is_told_TO_ITS_END_before_the_next_begins(self):
        """Depth-first is the pedagogical choice, not an implementation
        convenience: "if it matches, X then Y; if it doesn't, Z" is how a person
        explains a fork. Breadth-first would interleave the arms and read as one
        confused path."""
        c = _canvas(
            ["check", "m1", "m2", "u1", "u2"],
            [("check", "m1"), ("m1", "m2"), ("check", "u1"), ("u1", "u2")],
        )

        assert _ids(_ordered_nodes(c)) == ["check", "m1", "m2", "u1", "u2"]

    def test_declaration_order_decides_which_arm_is_told_first(self):
        """The authoring order is the teaching order. Swapping the edges swaps
        the narration, so an author controls the story by drawing it."""
        c = _canvas(
            ["check", "a", "b"],
            [("check", "b"), ("check", "a")],
        )
        assert _ids(_ordered_nodes(c)) == ["check", "b", "a"]

    def test_a_JOIN_is_visited_once(self):
        """Two ways lead to the same step; you do not teach that step twice."""
        c = _canvas(
            ["check", "a", "b", "join"],
            [("check", "a"), ("check", "b"), ("a", "join"), ("b", "join")],
        )

        got = _ids(_ordered_nodes(c))

        assert got.count("join") == 1
        assert len(got) == 4

    def test_a_CYCLE_terminates(self):
        """An authored canvas can loop (iteration edges exist in the schema).
        The walk must stop rather than recurse forever — `seen` is the guard and
        the DFS is iterative precisely so a deep cycle cannot blow the stack."""
        c = _canvas(
            ["start", "a", "b"],
            [("start", "a"), ("a", "b"), ("b", "a")],
        )

        got = _ids(_ordered_nodes(c))

        assert got == ["start", "a", "b"]


class TestTheCountContractHolds:
    """`check_mirror_drift` compares node COUNT against the runtime's steps. If
    the walk started returning a different number of nodes, the drift check
    would fire on every branching mirror for the wrong reason."""

    def test_every_node_appears_exactly_once_however_tangled(self):
        c = _canvas(
            ["r", "a", "b", "c", "d", "orphan"],
            [("r", "a"), ("r", "b"), ("a", "c"), ("b", "c"), ("c", "d")],
        )

        got = _ids(_ordered_nodes(c))

        assert sorted(got) == sorted(["r", "a", "b", "c", "d", "orphan"])
        assert len(got) == len(set(got)) == 6


class TestTheBranchBeatIsUnchanged:
    def test_a_fork_node_still_reads_as_a_branch_beat(self):
        """Scope line: this pass changed walk COVERAGE, not beat CONTENT. The
        branch beat still says only "a fork happens here" — naming which way
        leads where needs the edge labels carried into the beat, and that is its
        own pass."""
        for ntype in ("condition", "decision", "branch"):
            assert motif_for_step({"id": "x", "type": ntype}) == {"kind": "branch"}
