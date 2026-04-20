"""Triage ask_question — rendered-prompt terminology tests
(follow-up 2).

Deterministic assertions on the rendered prompt body per vertical.
We do NOT call Anthropic here — we intercept the `variables` passed
to `intelligence_service.execute`, render the active v2 prompt
locally via `prompt_renderer.render`, and assert the rendered text
contains the right terminology block (or lack thereof) for each
vertical.

The point: catch vertical leakage BEFORE it reaches Claude. If
somebody bumps a prompt and removes the VERTICAL-APPROPRIATE
TERMINOLOGY block by accident, this test fails.

Pattern mirrors `backend/tests/test_briefing_vertical_terminology.py`
(Phase 6 precedent).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest


# ── Fixture ─────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_user(*, vertical: str, role_slug: str = "admin"):
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"T-{suffix}",
            slug=f"t-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@t.co",
            first_name="T",
            last_name="U",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    from app.services.triage.ai_question import _reset_rate_limiter

    _reset_rate_limiter()
    yield
    _reset_rate_limiter()


def _seed_task_and_session(db, user):
    from app.services.task_service import create_task
    from app.services.triage.engine import start_session

    task = create_task(
        db,
        company_id=user.company_id,
        title="Priority task",
        created_by_user_id=user.id,
        assignee_user_id=user.id,
        priority="urgent",
        due_date=date.today() + timedelta(days=1),
    )
    session = start_session(db, user=user, queue_id="task_triage")
    return task.id, session.id


class _FakeIntelResult:
    def __init__(self):
        self.status = "success"
        self.response_parsed = {
            "answer": "ok",
            "confidence": 0.9,
            "sources": [],
        }
        self.response_text = None
        self.latency_ms = 100
        self.execution_id = "exec_" + uuid.uuid4().hex[:8]
        self.prompt_id = None
        self.prompt_version_id = None
        self.model_used = "claude-haiku-4-5"
        self.error_message = None
        self.rendered_system_prompt = ""
        self.rendered_user_prompt = ""
        self.input_tokens = 1
        self.output_tokens = 1
        self.cost_usd = None


# ── Helpers ────────────────────────────────────────────────────────


def _render_active_prompt(db, prompt_key: str, variables: dict) -> str:
    """Render the currently-active version of a prompt with the given
    variables, returning the combined system+user rendered text."""
    from app.models.intelligence import (
        IntelligencePrompt,
        IntelligencePromptVersion,
    )
    from app.services.intelligence import prompt_renderer

    prompt = (
        db.query(IntelligencePrompt)
        .filter(
            IntelligencePrompt.company_id.is_(None),
            IntelligencePrompt.prompt_key == prompt_key,
        )
        .one()
    )
    version = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == prompt.id,
            IntelligencePromptVersion.status == "active",
        )
        .one()
    )
    system, user = prompt_renderer.render(version, variables)
    return (system or "") + "\n\n" + (user or "")


def _call_ask_question_and_capture_variables(db, user_id):
    """Drive the service path, intercept the Intelligence call, and
    return the `variables` dict that was passed to
    `intelligence_service.execute`."""
    from app.models.user import User
    from app.services.triage.ai_question import ask_question

    user = db.query(User).filter(User.id == user_id).one()
    task_id, session_id = _seed_task_and_session(db, user)
    fake = _FakeIntelResult()
    captured = {}

    def _spy(db, **kwargs):
        captured.update(kwargs.get("variables", {}))
        return fake

    with patch(
        "app.services.triage.ai_question.intelligence_service.execute",
        side_effect=_spy,
    ):
        ask_question(
            db,
            user=user,
            session_id=session_id,
            item_id=task_id,
            question="Why is this urgent?",
        )
    return captured


# ── Terminology matrix ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "vertical,use_terms,forbidden_in_donot",
    [
        (
            "manufacturing",
            ["orders", "work orders", "production", "deliveries", "invoices"],
            ["cases", "arrangements", "burials", "cremations"],
        ),
        (
            "funeral_home",
            ["cases", "arrangements", "services", "families", "decedents"],
            ["orders", "work orders", "production", "pours"],
        ),
        (
            "cemetery",
            ["burials", "plots", "interments", "services", "families"],
            ["orders", "work orders", "production", "cases", "arrangements"],
        ),
        (
            "crematory",
            ["cremations", "services", "certificates", "families", "decedents"],
            ["orders", "work orders", "production", "pours", "cases", "burials"],
        ),
    ],
)
def test_vertical_terminology_block_renders(
    db_session, vertical, use_terms, forbidden_in_donot
):
    """For each vertical, the rendered v2 prompt contains the
    appropriate USE and DO-NOT-USE terminology lines — and ONLY that
    vertical's branch (the {% elif %} branching means exactly one
    fires).

    Pattern mirrors test_briefing_vertical_terminology.py — assert on
    the 'Use ONLY' and 'Do NOT use:' lines, not on absence of
    forbidden terms (those legitimately appear in the 'Do NOT use'
    list and would trigger false positives)."""
    user_id = _make_user(vertical=vertical)
    variables = _call_ask_question_and_capture_variables(db_session, user_id)
    assert variables["vertical"] == vertical
    rendered = _render_active_prompt(
        db_session, "triage.task_context_question", variables
    )

    # The terminology block header appears once regardless of
    # vertical — branches produce different USE/DO-NOT-USE content.
    assert "VERTICAL-APPROPRIATE TERMINOLOGY" in rendered, (
        f"{vertical}: prompt missing terminology block entirely"
    )

    # Extract the 'Do NOT use:' line for precise forbidden-term check.
    lines = rendered.splitlines()
    do_not_use_line = next(
        (line for line in lines if line.strip().startswith("- Do NOT use:")),
        None,
    )
    use_line = next(
        (
            line
            for line in lines
            if line.strip().startswith("-")
            and not line.strip().startswith("- Do NOT use:")
            and ("," in line)
            and not line.strip().startswith("- This tenant's")
        ),
        None,
    )
    assert use_line is not None, f"{vertical}: could not find 'use' line"
    assert do_not_use_line is not None, (
        f"{vertical}: could not find 'Do NOT use:' line"
    )

    for term in use_terms:
        assert term in use_line.lower(), (
            f"{vertical}: expected {term!r} in USE line, got: {use_line!r}"
        )
    for forbidden in forbidden_in_donot:
        assert forbidden in do_not_use_line.lower(), (
            f"{vertical}: expected {forbidden!r} in DO-NOT-USE line, "
            f"got: {do_not_use_line!r}"
        )


def test_unknown_vertical_falls_back_to_generic(db_session):
    """Companies with an empty / unrecognized vertical still render a
    valid prompt — the {% else %} branch in the terminology block
    kicks in."""
    user_id = _make_user(vertical="telecom")  # not in the known list
    variables = _call_ask_question_and_capture_variables(db_session, user_id)
    rendered = _render_active_prompt(
        db_session, "triage.task_context_question", variables
    )
    assert "generic business language" in rendered
    # None of the vertical-specific term blocks should appear.
    assert "cases, arrangements, services, families" not in rendered
    assert "burials, plots, interments" not in rendered


def test_ss_cert_prompt_also_renders_vertical_block(db_session):
    """Apply the same check to the ss_cert prompt — second queue
    must have the terminology block too."""
    from app.models.user import User
    from app.services.intelligence import prompt_renderer
    from app.models.intelligence import (
        IntelligencePrompt,
        IntelligencePromptVersion,
    )

    # For this one we don't need to fire a real call; directly render
    # the active v2 with a manufacturing vertical variable.
    prompt = (
        db_session.query(IntelligencePrompt)
        .filter(
            IntelligencePrompt.company_id.is_(None),
            IntelligencePrompt.prompt_key == "triage.ss_cert_context_question",
        )
        .one()
    )
    version = (
        db_session.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == prompt.id,
            IntelligencePromptVersion.status == "active",
        )
        .one()
    )
    variables = {
        "item_json": "{}",
        "user_question": "why?",
        "tenant_context": "test",
        "related_entities_json": "[]",
        "vertical": "manufacturing",
        "user_role": "admin",
        "queue_name": "SS Cert Triage",
        "queue_description": "Approve certs",
        "item_type": "social_service_certificate",
    }
    system, user = prompt_renderer.render(version, variables)
    rendered = (system or "") + "\n\n" + (user or "")
    assert "VERTICAL-APPROPRIATE TERMINOLOGY" in rendered
    assert (
        "orders, work orders, production, deliveries, invoices, quotes, customers"
        in rendered
    )
