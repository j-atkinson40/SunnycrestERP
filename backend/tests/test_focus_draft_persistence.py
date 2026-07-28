"""S-3b — focus_sessions draft persistence + THE HARD INVARIANT.

Persistence option (b): the editable quote draft persists to
focus_sessions (survives reload) and materializes NO quote before save.
The invariant test is the load-bearing gate for the whole ruling: a
draft — even a fully-formed one — must be invisible to the quotes domain
until explicit save.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def world(db_session):
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = db_session
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"FD {suffix}",
        slug=f"fd-{suffix}",
        is_active=True,
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
        email=f"a-{suffix}@fd.co",
        first_name="F",
        last_name="D",
        hashed_password="x",
        is_active=True,
        is_super_admin=True,
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    yield {"company_id": co.id, "user_id": user.id}

    from app.models.focus_session import FocusSession

    db.query(FocusSession).filter(FocusSession.company_id == co.id).delete(
        synchronize_session=False
    )
    db.query(User).filter(User.company_id == co.id).delete(
        synchronize_session=False
    )
    db.query(Role).filter(Role.company_id == co.id).delete(
        synchronize_session=False
    )
    db.query(Company).filter(Company.id == co.id).delete(
        synchronize_session=False
    )
    db.commit()


def _user(db, world):
    from app.models.user import User

    return db.query(User).filter(User.id == world["user_id"]).first()


def test_draft_persists_and_hydrates(db_session, world):
    from app.services.focus import focus_session_service as fss

    user = _user(db_session, world)
    draft = {
        "customer": {"id": "c1", "name": "Hopkins Funeral Home"},
        "lines": [
            {"productRef": "Monticello", "quantity": 3, "unitPrice": "1250.00"}
        ],
    }
    session = fss.create_or_resume_session(db_session, user, "quote-building")
    fss.update_draft_state(db_session, session, draft)
    db_session.commit()

    # Reload path: resume the same active session → the draft hydrates.
    resumed = fss.create_or_resume_session(db_session, user, "quote-building")
    assert resumed.id == session.id
    assert resumed.draft_state == draft


def test_draft_state_is_separate_from_layout_state(db_session, world):
    # The draft must NOT ride layout_state (which the tenant-default
    # cascade seeds/overwrites). Writing a draft leaves layout_state alone.
    from app.services.focus import focus_session_service as fss

    user = _user(db_session, world)
    session = fss.create_or_resume_session(db_session, user, "quote-building")
    fss.update_layout_state(db_session, session, {"widgets": {"x": 1}})
    fss.update_draft_state(db_session, session, {"lines": [{"q": 2}]})
    db_session.commit()
    assert session.layout_state == {"widgets": {"x": 1}}
    assert session.draft_state == {"lines": [{"q": 2}]}


def test_NO_QUOTE_DATA_BEFORE_SAVE_invariant(db_session, world):
    """THE INVARIANT (the whole ruling rests here). A fully-formed quote
    draft persisted to focus_sessions must materialize ZERO rows in the
    quotes domain. All quote reads (list / summary / get) hit the quotes
    table; zero rows there == invisible everywhere == option (b), not (c)."""
    from app.models.quote import Quote
    from app.services.focus import focus_session_service as fss

    user = _user(db_session, world)
    # A rich, fully-priced draft — the strongest test: even complete
    # quote content must not leak into the quotes domain pre-save.
    draft = {
        "customer": {"id": "c1", "name": "Hopkins Funeral Home"},
        "lines": [
            {
                "productRef": "Monticello",
                "productId": "p1",
                "quantity": 3,
                "unitPrice": "1250.00",
                "lineTotal": "3750.00",
            },
            {
                "productRef": "Continental",
                "productId": "p2",
                "quantity": 1,
                "unitPrice": "1607.00",
                "lineTotal": "1607.00",
            },
        ],
    }
    session = fss.create_or_resume_session(db_session, user, "quote-building")
    fss.update_draft_state(db_session, session, draft)
    db_session.commit()

    # THE ASSERTION — zero quotes materialized from the draft.
    quote_count = (
        db_session.query(Quote)
        .filter(Quote.company_id == world["company_id"])
        .count()
    )
    assert quote_count == 0, (
        "INVARIANT VIOLATED: a focus draft surfaced as a quote before save "
        "— this is persistence option (c) in disguise"
    )
    # And the draft IS durably persisted (option b — not lost).
    assert session.draft_state == draft
