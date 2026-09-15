"""BLOCKING CI gate — Workflow Arc Phase 8a endpoint latency.

Targets per Phase 8a scope decision:
  GET /workflows?scope=core|vertical|tenant     p50 < 100 ms, p99 < 300 ms
  POST /workflows/{id}/fork                     p50 < 200 ms, p99 < 500 ms
  GET /spaces (with system spaces resolved)     identical to UI/UX Arc budget
                                                  (p50 < 100 ms, p99 < 300 ms)

Phase 8a adds scope-filter SQL + used_by_count aggregate. The existing
`workflows` table is tiny (~40 rows on a seeded tenant) so measuring
the tab filter in isolation mostly measures ORM + FastAPI overhead.
Fork is bounded by step-count of the source + step-param copy. System
space resolution is one extra permission check per user; Phase 3
baseline was p50=15ms / p99=20ms against the same fixture set.

20 samples sequential per endpoint, mixed shapes where relevant.

Opt-out: WORKFLOW_ARC_LATENCY_DISABLE=1 skips.

⚠️ WHAT THIS GATE EXCLUDES — generation-2 GC pauses, and nothing else.
A full collection on this application's heap costs ~450 ms whatever the
garbage volume, because the cost is walking ~2.08M permanent objects. It
lands on whichever request is in flight. Every sample here is measured with
`tests/_gc_latency.Gen2Excluded`, which subtracts the collector's own
interval from the sample it landed in and SAYS SO in the printed diagnostic,
every run, including when nothing was excluded. Nothing is disabled, frozen
or tuned: the endpoint runs under exactly the runtime that ships. gen-0 and
gen-1 stay in the number, and an allocation ceiling on gen-0 keeps the
regression signal the exclusion would otherwise remove. Ruled 2026-09-15;
see docs/investigations/2026-09-15-latency-gates-exclude-gc.md.
"""

from __future__ import annotations

import os
import statistics
import time
import uuid

import pytest

from tests._gc_latency import Gen2Excluded, assert_allocation_ceiling


_TARGET_P50_MS: float = 100.0
_TARGET_P99_MS: float = 300.0
_TARGET_FORK_P50_MS: float = 200.0
_TARGET_FORK_P99_MS: float = 500.0
_WARMUP_COUNT: int = 3
_SAMPLE_COUNT: int = 20

#: ⚠️ ALLOCATION CEILINGS — the half of the gate that excluding gen-2 pauses
#: would otherwise delete. Counted in gen-0 collections over the sample loop
#: (see tests/_gc_latency.py). Measured 2026-09-15 over 3-4 runs with a spread
#: of <= 1, times 3 headroom.
_ALLOC_CEIL_CORE: int = 120
_ALLOC_CEIL_CORE_USED_BY: int = 120
_ALLOC_CEIL_VERTICAL: int = 5
_ALLOC_CEIL_SPACES: int = 5
_ALLOC_CEIL_FORK: int = 10


if os.environ.get("WORKFLOW_ARC_LATENCY_DISABLE") == "1":
    pytest.skip(
        "WORKFLOW_ARC_LATENCY_DISABLE=1 — skipping Phase 8a latency gate",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def seeded_tenant():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"WFLAT-{suffix}",
            slug=f"wflat-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"lat-{suffix}@wflat.co",
            first_name="Lat",
            last_name="Gate",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "token": token,
            "slug": co.slug,
            "company_id": co.id,
            "user_id": user.id,
        }
    finally:
        db.close()


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


def _fork_id(response) -> str:
    """The id of the fork just created, asserted rather than fished for.

    ⚠️ If the serializer ever stops returning `id`, teardown would silently
    register nothing and the leak would come back with the fixture still in
    place and still looking correct. That is this file's own failure mode
    repeating one level up, so it fails here instead.
    """
    body = response.json()
    assert isinstance(body, dict) and body.get("id"), (
        f"fork response carries no id to tear down: {str(body)[:200]}"
    )
    return body["id"]


def _sample(client, headers, path: str) -> Gen2Excluded:
    """Returns the SAMPLER, not a bare list.

    ⚠️ The sampler, not `sampler.durations_ms`. The exclusion note and the
    allocation count travel with the numbers to the place the numbers are
    read; handing back a list would leave a gate reporting a figure whose
    qualification had been dropped two frames up.
    """
    # Warm up.
    for _ in range(_WARMUP_COUNT):
        r = client.get(path, headers=headers)
        assert r.status_code == 200, r.text
    with Gen2Excluded() as gc_s:
        for _ in range(_SAMPLE_COUNT):
            with gc_s.sample():
                r = client.get(path, headers=headers)
            assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:120]}"
    return gc_s


def _assert_budget(
    gc_s: Gen2Excluded, *, p50_budget: float, p99_budget: float, label: str,
    allocation_ceiling: int,
):
    durations = gc_s.durations_ms
    p50 = statistics.median(durations)
    p99 = statistics.quantiles(durations, n=100)[-1]
    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={_SAMPLE_COUNT}, min={min(durations):.1f}ms "
        f"max={max(durations):.1f}ms) [{gc_s.exclusion_note()}]"
    )
    print(f"\n[{label}-latency] {diag}")
    assert p50 <= p50_budget, (
        f"{label} p50 {p50:.1f}ms > {p50_budget}ms — {diag}"
    )
    assert p99 <= p99_budget, (
        f"{label} p99 {p99:.1f}ms > {p99_budget}ms — {diag}"
    )
    assert_allocation_ceiling(gc_s, allocation_ceiling, label)


def test_workflow_scope_core_latency(client, headers):
    gc_s = _sample(client, headers, "/api/v1/workflows?scope=core")
    _assert_budget(
        gc_s,
        p50_budget=_TARGET_P50_MS,
        p99_budget=_TARGET_P99_MS,
        label="workflow-scope-core",
        allocation_ceiling=_ALLOC_CEIL_CORE,
    )


def test_workflow_scope_core_with_used_by_latency(client, headers):
    """With include_used_by=true, each row fires an aggregate —
    should still stay within budget for Phase 8a data sizes."""
    gc_s = _sample(
        client,
        headers,
        "/api/v1/workflows?scope=core&include_used_by=true",
    )
    _assert_budget(
        gc_s,
        p50_budget=_TARGET_P50_MS,
        p99_budget=_TARGET_P99_MS,
        label="workflow-scope-core-used-by",
        allocation_ceiling=_ALLOC_CEIL_CORE_USED_BY,
    )


def test_workflow_scope_vertical_latency(client, headers):
    gc_s = _sample(
        client, headers, "/api/v1/workflows?scope=vertical"
    )
    _assert_budget(
        gc_s,
        p50_budget=_TARGET_P50_MS,
        p99_budget=_TARGET_P99_MS,
        label="workflow-scope-vertical",
        allocation_ceiling=_ALLOC_CEIL_VERTICAL,
    )


def test_spaces_list_with_system_space_latency(
    client, headers, seeded_tenant
):
    """Settings system space adds one extra space + one permission
    check to the resolve path. Budget unchanged from UI/UX arc."""
    # Seed so system space is in preferences.
    from app.database import SessionLocal
    from app.models.user import User
    from app.services.spaces import seed_for_user

    db = SessionLocal()
    try:
        user = (
            db.query(User).filter(User.id == seeded_tenant["user_id"]).one()
        )
        seed_for_user(db, user=user)
    finally:
        db.close()

    gc_s = _sample(client, headers, "/api/v1/spaces")
    _assert_budget(
        gc_s,
        p50_budget=_TARGET_P50_MS,
        p99_budget=_TARGET_P99_MS,
        label="spaces-with-system",
        allocation_ceiling=_ALLOC_CEIL_SPACES,
    )


@pytest.fixture
def created_workflow_ids():
    """⚠️ THE TEARDOWN THIS FILE CLAIMED TO HAVE AND DID NOT.

    Until 2026-09-15 `test_workflow_fork_latency` created 23 global
    `scope="core"` workflows per run and deleted none, while its docstring said
    *"we delete the fork after measurement."* That sentence had been false since
    it was written. It survived because it is a SAFETY claim, and a safety claim
    is the category a reader is least likely to test — testing it means
    constructing the failure it says cannot happen.

    ⚠️ DELETION IS BY RECORDED ID, NOT BY NAME. A `name LIKE 'ForkSrc-%'` sweep
    would be a constructed scope: it would miss anything renamed, it would match
    rows this run did not create, and it would silently stop matching the day
    the name changes. The test appends every id it creates — sources as it makes
    them, forks as the endpoint returns them — and teardown deletes exactly
    those.

    ⚠️ IT RUNS ON FAILURE. Fixture finalisation happens whether the test passed,
    failed or raised. A `try/finally` in the test body would too, but only from
    the point the `try` is entered; the first failure before that would have
    reinstated the leak permanently.

    `workflow_steps` and `workflow_step_params` are ON DELETE CASCADE from
    `workflows` (read from the FK catalogue, not assumed), so they go with the
    parent. `workflows.forked_from_workflow_id` is SET NULL, so a fork does NOT
    disappear with its source and has to be recorded in its own right.
    """
    created: list[str] = []
    yield created
    if not created:
        return

    from app.database import SessionLocal
    from app.models.workflow import Workflow

    db = SessionLocal()
    try:
        removed = (
            db.query(Workflow)
            .filter(Workflow.id.in_(created))
            .delete(synchronize_session=False)
        )
        db.commit()
    finally:
        db.close()

    # ⚠️ The control on the teardown, not on the test. A delete that removes
    # fewer rows than were recorded has left some behind, and the whole reason
    # this fixture exists is that nobody was checking.
    assert removed == len(created), (
        f"teardown recorded {len(created)} workflow rows and deleted {removed} "
        f"— {len(created) - removed} row(s) are still in the database"
    )


def test_workflow_fork_latency(
    client, headers, seeded_tenant, created_workflow_ids
):
    """Fork copies a workflow + its steps + its platform-default
    params. Budget wider (200ms/500ms) because it's a multi-table
    write path. The test uses a freshly-created source workflow for
    each sample so the AlreadyForked check doesn't kick in.

    Every row created here — the sources AND the forks — is registered with
    `created_workflow_ids` and deleted in that fixture's teardown. See its
    docstring for why this is by id rather than by name, and for what the
    previous version of this sentence claimed.
    """
    from app.database import SessionLocal
    from app.models.workflow import Workflow, WorkflowStep

    db = SessionLocal()
    try:
        # One source workflow per sample; create them upfront so the
        # measurement excludes source setup time.
        source_ids = []
        for i in range(_SAMPLE_COUNT + _WARMUP_COUNT):
            src_id = str(uuid.uuid4())
            src = Workflow(
                id=src_id,
                company_id=None,
                name=f"ForkSrc-{i}",
                description="fork latency source",
                tier=1,
                scope="core",
                vertical=None,
                trigger_type="manual",
                is_active=True,
                is_system=True,
            )
            db.add(src)
            db.flush()
            for step_n in range(3):
                db.add(
                    WorkflowStep(
                        id=str(uuid.uuid4()),
                        workflow_id=src_id,
                        step_order=step_n + 1,
                        step_key=f"step_{step_n}",
                        step_type="action",
                        config={"n": step_n},
                    )
                )
            source_ids.append(src_id)
        db.commit()
    finally:
        db.close()

    # Registered AFTER the commit, so nothing unwritten is queued for deletion.
    created_workflow_ids.extend(source_ids)

    # Warm up with the first _WARMUP_COUNT sources.
    for i in range(_WARMUP_COUNT):
        r = client.post(
            f"/api/v1/workflows/{source_ids[i]}/fork",
            json={},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        created_workflow_ids.append(_fork_id(r))

    # Measured samples use the remaining sources.
    with Gen2Excluded() as gc_s:
        for i in range(_WARMUP_COUNT, _WARMUP_COUNT + _SAMPLE_COUNT):
            with gc_s.sample():
                r = client.post(
                    f"/api/v1/workflows/{source_ids[i]}/fork",
                    json={},
                    headers=headers,
                )
            assert r.status_code == 200, r.text
            created_workflow_ids.append(_fork_id(r))

    _assert_budget(
        gc_s,
        p50_budget=_TARGET_FORK_P50_MS,
        p99_budget=_TARGET_FORK_P99_MS,
        label="workflow-fork",
        allocation_ceiling=_ALLOC_CEIL_FORK,
    )
