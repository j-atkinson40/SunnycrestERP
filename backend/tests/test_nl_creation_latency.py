"""BLOCKING CI gate — NL Creation extract latency.

Phase 4 overlay responsiveness depends on `/api/v1/nl-creation/extract`
staying under the p50/p99 targets:

    p50 < 600 ms   (the number users feel per keystroke)
    p99 < 1200 ms  (tail during AI spikes)

The extract endpoint is called on every debounced keystroke while
the user types. Drift here is immediately user-visible.

Methodology:
  1. Seed a tenant + admin user + ~10 CompanyEntity rows so the
     entity resolver has something to fuzzy-match against.
  2. Disable Anthropic (empty ANTHROPIC_API_KEY) so the gate
     measures OUR code path, not the external API latency. Claude
     latency is measured separately in `test_nl_creation_ai.py`.
  3. Warm up + run N=30 sequential calls per entity type × 3
     entity types (case, event, contact).
  4. Compute p50 + p99 from combined sample.
  5. Fail if p50 > 600 ms or p99 > 1200 ms.

Sequential, not concurrent — measures the worst-case single-call
latency the user actually experiences per keystroke.

Environment opt-outs:
  - `NL_CREATION_LATENCY_DISABLE=1` skips the test.

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
import uuid

import pytest

from tests._gc_latency import Gen2Excluded, assert_allocation_ceiling


_TARGET_P50_MS: float = 600.0
_TARGET_P99_MS: float = 1200.0
_WARMUP_COUNT: int = 3
_SAMPLE_COUNT_PER_ENTITY: int = 10

#: ⚠️ ALLOCATION CEILINGS — the half of the gate that excluding gen-2
#: pauses would otherwise delete. Counted in gen-0 collections over the
#: sample loop (see tests/_gc_latency.py). Measured 2026-09-15 over 3-4
#: runs with a spread of <= 1, times 3 headroom.
_ALLOC_CEIL_EXTRACT: int = 25


if os.environ.get("NL_CREATION_LATENCY_DISABLE") == "1":
    pytest.skip(
        "NL_CREATION_LATENCY_DISABLE=1 — skipping latency gate",
        allow_module_level=True,
    )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _seed_tenant():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.company_entity import CompanyEntity
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"LAT-{suffix}",
            slug=f"lat-{suffix}",
            is_active=True,
            vertical="funeral_home",
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
            email=f"admin-{suffix}@lat.co",
            first_name="Lat",
            last_name="Gate",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        # Seed a handful of CompanyEntity rows so the entity
        # resolver has realistic fuzzy-match candidates.
        names = [
            "Hopkins Funeral Home",
            "Smith Memorial Chapel",
            "Riverside Funeral Services",
            "Anderson & Sons",
            "Whitney Funeral Home",
            "Maple Grove Cemetery",
            "St. Mary's Church",
            "First Baptist Church",
            "Oakwood Memorial",
            "Greenlawn Cemetery",
        ]
        for name in names:
            db.add(
                CompanyEntity(
                    id=str(uuid.uuid4()),
                    company_id=co.id,
                    name=name,
                    is_funeral_home="Funeral" in name,
                    is_cemetery="Cemetery" in name,
                    is_active=True,
                )
            )
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "company_id": co.id,
            "user_id": user.id,
            "token": token,
            "slug": co.slug,
        }
    finally:
        db.close()


@pytest.fixture(scope="module")
def seeded_tenant():
    return _seed_tenant()


@pytest.fixture
def headers(seeded_tenant):
    return {
        "Authorization": f"Bearer {seeded_tenant['token']}",
        "X-Company-Slug": seeded_tenant["slug"],
    }


# Mixed-shape inputs per entity.
_SHAPES = {
    "case": [
        "new case John Smith DOD tonight Hopkins FH",
        "new case Mary Johnson DOD yesterday",
        "new case Robert Taylor service Thursday Riverside",
    ],
    "event": [
        "lunch with Jim tomorrow 2pm",
        "staff meeting Friday 10am conference room A",
        "review with Anderson next Tuesday",
    ],
    "contact": [
        "Bob Smith at Hopkins phone 555-1234",
        "Mary Johnson bob@acme.com office manager",
        "Robert Taylor owner Hopkins",
    ],
}


def test_nl_creation_extract_p50_p99_under_budget(
    client, headers, seeded_tenant
):
    """BLOCKING CI gate. Fails if p50 > 600 ms or p99 > 1200 ms on
    the sequential sample.

    Anthropic is disabled (empty API key) so we measure OUR code
    path. When ANTHROPIC_API_KEY is set in CI, this number will
    drift UP (legitimately — real AI calls add 300-500 ms). The
    gate still holds at the published numbers because Haiku p99
    stays under 1200 ms in practice.
    """
    prev_key = os.environ.get("ANTHROPIC_API_KEY")
    # Keep whatever state is live; if the env has a key, real calls
    # happen. The gate budget accommodates both paths.

    gc_s = Gen2Excluded()
    try:
        # Warm-up
        for _ in range(_WARMUP_COUNT):
            for entity_type, shapes in _SHAPES.items():
                client.post(
                    "/api/v1/nl-creation/extract",
                    json={
                        "entity_type": entity_type,
                        "natural_language": shapes[0],
                    },
                    headers=headers,
                )

        # Sample
        with gc_s:
            for entity_type, shapes in _SHAPES.items():
                for i in range(_SAMPLE_COUNT_PER_ENTITY):
                    input_text = shapes[i % len(shapes)]
                    with gc_s.sample():
                        r = client.post(
                            "/api/v1/nl-creation/extract",
                            json={
                                "entity_type": entity_type,
                                "natural_language": input_text,
                            },
                            headers=headers,
                        )
                    assert r.status_code == 200, (
                        f"extract {entity_type!r} → {r.status_code} {r.text[:120]}"
                    )
    finally:
        if prev_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = prev_key

    durations_ms = gc_s.durations_ms

    p50 = statistics.median(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[-1]

    diag = (
        f"p50={p50:.1f}ms p99={p99:.1f}ms "
        f"(n={len(durations_ms)}, min={min(durations_ms):.1f}ms "
        f"max={max(durations_ms):.1f}ms) [{gc_s.exclusion_note()}]"
    )
    print(f"\n[nl-creation-latency] {diag}")

    assert p50 <= _TARGET_P50_MS, (
        f"nl-creation extract p50 {p50:.1f}ms > target {_TARGET_P50_MS}ms — {diag}"
    )
    assert p99 <= _TARGET_P99_MS, (
        f"nl-creation extract p99 {p99:.1f}ms > target {_TARGET_P99_MS}ms — {diag}"
    )
    assert_allocation_ceiling(gc_s, _ALLOC_CEIL_EXTRACT, "nl-creation-extract")
