"""THE ROUTE-ORDER PIN (perf pass, 2026-07) — static-before-parameterized.

The twice-caught class: FastAPI matches routes in registration order, so a
parameterized route declared BEFORE a static sibling SWALLOWS it —
`GET /ponder/{task_id}` before `GET /ponder/users` turned the user search
into "Task not found" (P1 rider), exactly as `DELETE /{space_id}` would
have eaten `DELETE /affinity` in 8e.1. Both were caught live; this pin
kills the class in CI.

The checker walks the REAL app's routes in registration order and flags
any earlier route that would match a later route's literal path (same
segment count, overlapping methods, every static segment equal, params
matching anything) — the later route is unreachable for those methods.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute


def _segments(path: str) -> list[str]:
    return [s for s in path.strip("/").split("/") if s != ""]


def _is_param(seg: str) -> bool:
    return seg.startswith("{") and seg.endswith("}")


def _shadows(earlier: list[str], later: list[str]) -> bool:
    """Would the earlier pattern match the later LITERAL path?"""
    if len(earlier) != len(later):
        return False
    matched_a_param = False
    for e, l in zip(earlier, later):
        if _is_param(e):
            if _is_param(l):
                return False  # both parameterized at this slot — not a literal shadow
            matched_a_param = True
            continue
        if e != l:
            return False
    return matched_a_param  # identical static paths are a different problem


def swallowed_routes(app: FastAPI) -> list[str]:
    """Every (earlier-param-route swallows later-static-route) pair, named."""
    routes = [
        (r.path, frozenset(r.methods or ()), idx)
        for idx, r in enumerate(app.routes)
        if isinstance(r, APIRoute)
    ]
    offenders = []
    for i, (path_i, methods_i, _) in enumerate(routes):
        segs_i = _segments(path_i)
        if not any(_is_param(s) for s in segs_i):
            continue
        for path_j, methods_j, _ in routes[i + 1:]:
            if not (methods_i & methods_j):
                continue
            if _shadows(segs_i, _segments(path_j)):
                offenders.append(
                    f"{sorted(methods_i & methods_j)} {path_i} (earlier) swallows "
                    f"{path_j} (later — unreachable)"
                )
    return offenders


# THE PRE-EXISTING LEDGER (observe-then-enforce, the C-10 gate canon): the
# pin's first run surfaced these ALREADY-swallowed routes — each is a live
# latent bug (the static endpoint has been unreachable; the param handler
# answers with a garbage lookup). They come from cross-router mount
# interleavings in v1.py, so each fix needs its owning module's eyes (an
# endpoint dead since birth coming alive is a behavior change, not a
# reorder). Tracked here; fix = remove the entry + move the static route/
# mount above. NEW offenders fail CI immediately.
KNOWN_SWALLOWED = {
    "/api/v1/companies/health-summary",
    "/api/v1/companies/funeral-homes",
    "/api/v1/companies/crm-hidden-count",
    "/api/v1/companies/crm-hidden-companies",
    "/api/v1/companies/crm-settings",
    "/api/v1/companies/opportunities",
    "/api/v1/documents-v2/inbox",
    "/api/v1/documents-v2/deliveries",
    "/api/v1/spring-burials/bulk-schedule",
    "/api/v1/products/urns",
    "/api/v1/sales/invoices/review",
    "/api/platform/admin/visual-editor/workflows/forks/",
    # the deprecated /api mount mirrors the /api/v1 offenders:
    "/api/companies/health-summary",
    "/api/companies/funeral-homes",
    "/api/companies/crm-hidden-count",
    "/api/companies/crm-hidden-companies",
    "/api/companies/crm-settings",
    "/api/companies/opportunities",
    "/api/documents-v2/inbox",
    "/api/documents-v2/deliveries",
    "/api/spring-burials/bulk-schedule",
    "/api/products/urns",
    "/api/sales/invoices/review",
}


def test_no_new_swallowed_routes():
    """THE PIN: no route ordering may swallow a static sibling beyond the
    pre-existing ledger above. The twice-caught class (8e.1 affinity, P1
    /ponder/users) dies here for every FUTURE route."""
    from app.main import app

    new = [
        o for o in swallowed_routes(app)
        if not any(f"swallows {known} " in o for known in KNOWN_SWALLOWED)
    ]
    assert new == [], (
        "NEW route-order violations (static-before-parameterized — move the "
        "static route ABOVE the parameterized one):\n  " + "\n  ".join(new)
    )


def test_the_ledger_does_not_overstate():
    """Every ledger entry is still genuinely swallowed — a fixed route must
    leave the ledger (the ledger can only shrink, never pad)."""
    from app.main import app

    actual = swallowed_routes(app)
    stale = [
        known for known in KNOWN_SWALLOWED
        if not any(f"swallows {known} " in o for o in actual)
    ]
    assert stale == [], (
        "These ledger entries are no longer swallowed — remove them:\n  "
        + "\n  ".join(stale)
    )


def test_the_checker_catches_a_deliberately_misordered_fixture():
    """The checker itself is live: a param route declared before its static
    sibling is flagged; the corrected order passes."""
    bad = FastAPI()
    r = APIRouter()

    @r.get("/ponder/{task_id}")
    def by_id(task_id: str): ...

    @r.get("/ponder/users")
    def users(): ...

    bad.include_router(r, prefix="/api")
    offenders = swallowed_routes(bad)
    assert len(offenders) == 1
    assert "/api/ponder/{task_id}" in offenders[0]
    assert "/api/ponder/users" in offenders[0]

    good = FastAPI()
    r2 = APIRouter()

    @r2.get("/ponder/users")
    def users2(): ...

    @r2.get("/ponder/{task_id}")
    def by_id2(task_id: str): ...

    good.include_router(r2, prefix="/api")
    assert swallowed_routes(good) == []


def test_different_methods_do_not_false_positive():
    """GET /{page_id} never swallows PATCH /tasks/reorder — methods gate."""
    app = FastAPI()
    r = APIRouter()

    @r.get("/{page_id}")
    def page(page_id: str): ...

    @r.patch("/tasks")
    def patch_tasks(): ...

    app.include_router(r)
    assert swallowed_routes(app) == []
