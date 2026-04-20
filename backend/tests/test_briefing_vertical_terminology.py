"""Phase 7 follow-up — briefing prompt vertical-terminology block.

Asserts that the `briefing.morning` + `briefing.evening` prompts, when
rendered with a specific `vertical` variable, produce output that:

  1. Includes an explicit instruction block telling Claude which
     terminology to use for that vertical
  2. Includes terminology appropriate to the vertical
  3. DOES NOT include cross-vertical terminology in its instructions
     (a manufacturing prompt shouldn't instruct "use: cases")

These tests run against the active prompt version loaded from the
database — so they implicitly verify that `seed_intelligence_phase6.py`
seeded the vertical block into the prompt bodies. If a future prompt
edit drops the vertical block, these tests fail.

No AI call. No Intelligence service call. Pure
`prompt_renderer.render(version, variables)` + string assertions —
deterministic + fast.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _load_active_version(db: Session, prompt_key: str):
    """Load the active version of a platform-global prompt."""
    from app.models.intelligence import (
        IntelligencePrompt,
        IntelligencePromptVersion,
    )

    prompt = (
        db.query(IntelligencePrompt)
        .filter(
            IntelligencePrompt.company_id.is_(None),
            IntelligencePrompt.prompt_key == prompt_key,
        )
        .first()
    )
    assert prompt is not None, f"Prompt {prompt_key!r} not seeded"
    version = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == prompt.id,
            IntelligencePromptVersion.status == "active",
        )
        .first()
    )
    assert version is not None, f"No active version for {prompt_key!r}"
    return version


def _render_for_vertical(
    db: Session, prompt_key: str, vertical: str
) -> str:
    """Render the prompt system message with the given vertical."""
    from app.services.intelligence import prompt_renderer

    version = _load_active_version(db, prompt_key)
    variables = {
        "user_first_name": "Test",
        "user_last_name": "",
        "company_name": "TestCo",
        "role_slug": "admin",
        "vertical": vertical,
        "today_iso": "2026-04-20",
        "day_of_week": "Monday",
        "now_iso": "2026-04-20T09:00:00Z",
        "active_space_id": "",
        "active_space_name": "",
        "narrative_tone": "concise",
        "requested_sections": [],
        "legacy_context": {},
        "queue_summaries": [],
        "overnight_calls": {},
        "today_events": [],
        "tomorrow_events": [],
        "pending_approvals": [],
        "flagged_items": [],
        "day_completed_items": [],
    }
    rendered_system, _rendered_user = prompt_renderer.render(
        version, variables
    )
    return rendered_system


# ── Vertical block presence + correctness ──────────────────────────


PROMPT_KEYS = ("briefing.morning", "briefing.evening")


@pytest.mark.parametrize("prompt_key", PROMPT_KEYS)
def test_prompt_contains_vertical_instruction_header(db_session, prompt_key):
    """The rendered prompt must include an explicit
    VERTICAL-APPROPRIATE TERMINOLOGY header instructing Claude on
    per-vertical language."""
    rendered = _render_for_vertical(db_session, prompt_key, "manufacturing")
    assert "VERTICAL-APPROPRIATE TERMINOLOGY" in rendered, (
        f"{prompt_key} missing vertical instruction header"
    )


@pytest.mark.parametrize("prompt_key", PROMPT_KEYS)
def test_manufacturing_prompt_lists_mfg_terms(db_session, prompt_key):
    """A manufacturing rendering must instruct on MFG terminology."""
    rendered = _render_for_vertical(db_session, prompt_key, "manufacturing")
    # Required MFG terms in the instruction list.
    for term in ("orders", "work orders", "production", "deliveries", "invoices"):
        assert term in rendered, (
            f"{prompt_key} (manufacturing) missing term '{term}'"
        )


@pytest.mark.parametrize("prompt_key", PROMPT_KEYS)
def test_manufacturing_prompt_excludes_fh_instructions(db_session, prompt_key):
    """A manufacturing rendering must NOT list FH-instruction terms
    as allowed terminology. They should appear ONLY in the 'Do NOT
    use' line — we verify this by checking the 'Do NOT use' appears
    alongside FH terms."""
    rendered = _render_for_vertical(db_session, prompt_key, "manufacturing")
    # The prompt should contain the FH exclusion directive.
    assert "Do NOT use:" in rendered
    # Find the Do-NOT-use line for the manufacturing block — it must
    # mention FH-specific terms that manufacturing should NOT emit.
    lines = rendered.split("\n")
    do_not_line = next(
        (line for line in lines if line.startswith("- Do NOT use:")), None
    )
    assert do_not_line is not None, "Could not find 'Do NOT use:' line"
    # MFG's forbidden terms include cases + arrangements.
    for forbidden in ("cases", "arrangements"):
        assert forbidden in do_not_line.lower(), (
            f"manufacturing prompt should forbid '{forbidden}' in its "
            f"Do-NOT-use list, got: {do_not_line!r}"
        )


@pytest.mark.parametrize("prompt_key", PROMPT_KEYS)
def test_funeral_home_prompt_lists_fh_terms(db_session, prompt_key):
    rendered = _render_for_vertical(db_session, prompt_key, "funeral_home")
    for term in ("cases", "arrangements", "services", "families"):
        assert term in rendered, (
            f"{prompt_key} (funeral_home) missing term '{term}'"
        )


@pytest.mark.parametrize("prompt_key", PROMPT_KEYS)
def test_funeral_home_prompt_excludes_mfg_instructions(db_session, prompt_key):
    rendered = _render_for_vertical(db_session, prompt_key, "funeral_home")
    lines = rendered.split("\n")
    do_not_line = next(
        (line for line in lines if line.startswith("- Do NOT use:")), None
    )
    assert do_not_line is not None
    for forbidden in ("orders", "work orders", "production"):
        assert forbidden in do_not_line.lower(), (
            f"funeral_home prompt should forbid '{forbidden}': {do_not_line!r}"
        )


@pytest.mark.parametrize("prompt_key", PROMPT_KEYS)
def test_cemetery_prompt_uses_cemetery_terms(db_session, prompt_key):
    rendered = _render_for_vertical(db_session, prompt_key, "cemetery")
    for term in ("burials", "plots", "interments"):
        assert term in rendered, (
            f"{prompt_key} (cemetery) missing term '{term}'"
        )


@pytest.mark.parametrize("prompt_key", PROMPT_KEYS)
def test_crematory_prompt_uses_crematory_terms(db_session, prompt_key):
    rendered = _render_for_vertical(db_session, prompt_key, "crematory")
    for term in ("cremations", "services", "certificates"):
        assert term in rendered, (
            f"{prompt_key} (crematory) missing term '{term}'"
        )


@pytest.mark.parametrize("prompt_key", PROMPT_KEYS)
def test_unknown_vertical_uses_generic_fallback(db_session, prompt_key):
    """Tenant with null / unexpected vertical falls into the generic
    instruction branch — doesn't leak any one vertical's language."""
    rendered = _render_for_vertical(db_session, prompt_key, "")
    # Generic branch present?
    assert (
        "generic business language" in rendered
        or "unset" in rendered
    ), (
        f"{prompt_key} with empty vertical should fall into the generic "
        "instruction branch"
    )


# ── End-to-end: generator path threads vertical correctly ──────────


def test_generator_passes_vertical_to_intelligence(
    db_session, monkeypatch
):
    """Integration — the generator path (data_sources → generator →
    intelligence_service.execute) passes the tenant's vertical as a
    prompt variable. We intercept intelligence_service.execute to
    capture the variables dict."""
    import uuid

    from app.core.security import create_access_token  # noqa: F401 — unused but validates imports
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from app.services.briefings import (
        collect_data_for_morning_briefing,
        generate_morning_briefing,
    )

    # Seed a manufacturing tenant + user.
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"VT-{suffix}",
        slug=f"vt-{suffix}",
        is_active=True,
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    role = Role(
        id=str(uuid.uuid4()),
        company_id=co.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=str(uuid.uuid4()),
        company_id=co.id,
        email=f"vt-{suffix}@t.co",
        first_name="VT",
        last_name="Test",
        hashed_password="x",
        is_active=True,
        is_super_admin=True,
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()

    captured: dict = {}

    class _Stub:
        status = "success"
        response_parsed = {
            "narrative_text": "ok",
            "structured_sections": {"greeting": "ok"},
        }
        response_text = None
        input_tokens = 0
        output_tokens = 0
        cost_usd = None
        latency_ms = 0

    def _fake_execute(db, prompt_key, variables=None, **kw):
        captured["prompt_key"] = prompt_key
        captured["variables"] = variables or {}
        return _Stub()

    monkeypatch.setattr(
        "app.services.intelligence.intelligence_service.execute",
        _fake_execute,
    )

    data_ctx = collect_data_for_morning_briefing(db_session, user)
    generate_morning_briefing(db_session, user, data_ctx)

    # The variables dict must contain vertical="manufacturing".
    assert captured["prompt_key"] == "briefing.morning"
    assert captured["variables"].get("vertical") == "manufacturing", (
        "generator must thread the tenant's vertical into the prompt "
        f"variables. Got: {captured['variables'].get('vertical')!r}"
    )
