"""Every enum field shows a LABEL in the API response — never its stored id.

⚠️ THE DEFECT, FROM JAMES'S PRODUCTION WALK. The Service row read `funeral_home`.
`rows.py::_render` did `str(v)` for every field, because nothing told it which fields
hold ids and which hold display text — and `cemetery_equipment` was the one enum field
whose extractor stored a LABEL while every other stored an id, so per-field there was
genuinely no way to know. Ruled 2026-10-12: enum fields store IDS, labels come from one
map declared beside the field's options in `schema.py`, never from the frontend, and
the inconsistency is fixed at the source.

⚠️ THE PARTITION IS THE CONTRACT: a field with `options` stores an id; a field without
stores what it shows. Asserted below, so a new enum field cannot quietly join the
second group and reach a screen as a slug.

⚠️ AND THE STRONG ASSERTION IS THE NEGATIVE ONE. Checking that the Service row says
"Funeral home" passes if someone hardcodes that one string. Checking that NO row value
anywhere equals ANY option id is the property, and it fails for a field nobody thought
to list here.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture import session_service
from app.services.capture.schema import PLATFORM_DEFAULT_FIELDS
from app.services.capture.typed_extraction import (
    _DATE_FORMAT_WORDS,
    _EQUIPMENT,
    _LEGACY_SERIES,
    _LOCATION_WORDS,
    _PERSONALIZATION,
)

BY_ID = {d.field_id: d for d in PLATFORM_DEFAULT_FIELDS}

#: ⚠️ THE SIX, LISTED SO ADDING A SEVENTH IS A VISIBLE EDIT TO THIS FILE.
ENUM_FIELDS = (
    "service_location",
    "nameplate_date_format",
    "legacy_series",
    "lifes_reflections_symbol",
    "cemetery_equipment",
    "personalization",
)

#: Every id any option set holds — the set no rendered row may ever contain.
ALL_OPTION_IDS = {
    ident for d in PLATFORM_DEFAULT_FIELDS for ident, _ in d.options
}


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", "")


@pytest.fixture(scope="module")
def db():
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


# ── the partition ───────────────────────────────────────────────────────

def test_exactly_the_six_enum_fields_declare_options():
    with_options = {d.field_id for d in PLATFORM_DEFAULT_FIELDS if d.options}
    assert with_options == set(ENUM_FIELDS), (
        f"the enum partition moved. extra={sorted(with_options - set(ENUM_FIELDS))} "
        f"missing={sorted(set(ENUM_FIELDS) - with_options)}. A new enum field needs a "
        f"label map beside its options in schema.py and a row in ENUM_FIELDS."
    )


def test_every_other_field_stores_its_display_value():
    """⚠️ THE OTHER HALF OF THE CONTRACT. `vault`, `cemetery` and `funeral_home` are
    resolved entities and the rest are free text or parsed dates; all of them store
    what they show, so they must declare no options."""
    assert {d.field_id for d in PLATFORM_DEFAULT_FIELDS if not d.options} == {
        "vault", "funeral_home", "deceased_name", "cemetery", "cemetery_city",
        "burial_date", "service_date", "service_time", "grave_location",
        "service_location_other", "eta", "date_of_birth", "date_of_death",
        "legacy_print_name",
        # ⚠️ ADDED 2026-10-14 AS `extra_chairs_count`, NOW TWO FIELDS (rulings A/B',
        # 2026-10-30). Each holds a number the director gave and shows that number —
        # there is no vocabulary to map, so no options. They belong on this side of
        # the partition for the same reason the dates do.
        #
        # ⚠️ AND THEY ARE ON THIS SIDE DESPITE BEING CHAIRS, which is worth saying
        # because `cemetery_equipment` is on the OTHER side with a label map. The
        # bundle is a vocabulary ("full_equipment" → "Full Equipment"); a count is a
        # number. Rulings A/B' split exactly along that line.
        "chairs_total",
        "chairs_extra",
    }


def test_no_option_id_is_also_a_label():
    """⚠️ IF AN ID EQUALLED ITS LABEL, every assertion in this file would pass while
    that field still rendered a slug — the id and the label would be the same string
    and indistinguishable. `none` is the one allowed overlap-shaped case and it is
    labelled "None", so there is none."""
    same = [
        (d.field_id, i) for d in PLATFORM_DEFAULT_FIELDS for i, lab in d.options
        if i == lab
    ]
    assert not same, same


# ── totality: every value the extractor can produce has a label ─────────

@pytest.mark.parametrize("field_id,produced", [
    ("cemetery_equipment", [v for _, v in _EQUIPMENT]),
    ("personalization", [v for _, v in _PERSONALIZATION]),
    ("legacy_series", [v for _, v in _LEGACY_SERIES]),
    ("nameplate_date_format", [v for _, v in _DATE_FORMAT_WORDS]),
    ("service_location", list(_LOCATION_WORDS.values())),
])
def test_every_value_the_extractor_can_produce_has_a_label(field_id, produced):
    """⚠️ A RATCHET OVER THE EXTRACTOR'S OWN VOCABULARIES, not a hand-written list.
    Adding a phrase that stores a new id fails here by name, rather than shipping a
    value whose only rendering is itself."""
    assert produced, f"{field_id}: read no values from the extractor — this is blind"
    known = {i for i, _ in BY_ID[field_id].options}
    missing = sorted(set(produced) - known)
    assert not missing, (
        f"{field_id}: the extractor can store {missing}, which has no label in "
        f"schema.py and would render as a raw id"
    )


def test_an_unknown_stored_value_renders_as_itself_rather_than_raising():
    """A row may predate a vocabulary change. A visible oddity an operator can report
    beats taking the whole pane down over one row."""
    assert BY_ID["service_location"].label_for("from_1998") == "from_1998"


# ── through the API response ────────────────────────────────────────────

@pytest.fixture
def session(db):
    """A capture session on a throwaway tenant+user, rolled back."""
    import uuid

    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    sp = db.begin_nested()
    slug = f"enumdisp-{uuid.uuid4().hex[:8]}"
    co = Company(id=str(uuid.uuid4()), name=slug, slug=slug, vertical="manufacturing")
    db.add(co)
    db.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    db.add(role)
    db.flush()
    u = User(id=str(uuid.uuid4()), company_id=co.id, email=f"{slug}@example.com",
             first_name="E", last_name="D", hashed_password="x", role_id=role.id)
    db.add(u)
    db.flush()
    yield co.id, u.id
    sp.rollback()


def test_the_API_response_shows_labels_for_every_enum_it_captured(db, session):
    cid, uid = session
    row = session_service.start(db, company_id=cid, user_id=uid)
    for line in ("service at the funeral home", "tent only", "nameplate only",
                 "years only", "standard series"):
        session_service.add_line(db, row.id, company_id=cid, user_id=uid, line=line)
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    # ⚠️ CONTROL FIRST. If nothing was captured, every assertion below passes
    # vacuously — "no slug on screen" and "nothing on screen" look identical.
    stored = state["values"]
    captured = [f for f in ENUM_FIELDS if f in stored]
    assert len(captured) >= 4, f"only captured {captured}; this test is measuring nothing"

    # The stored side is ids.
    assert stored["service_location"] == "funeral_home"
    assert stored["cemetery_equipment"] == "tent_only"
    assert stored["personalization"] == "nameplate_only"
    assert stored["nameplate_date_format"] == "years"

    # ⚠️ THE PROPERTY: no rendered row value is an option id, for ANY field.
    rows = state["surface"]["rows"]
    assert rows, "no surface rows came back"
    offenders = [
        (r["row_id"], r["value"]) for r in rows
        if r.get("value") in ALL_OPTION_IDS
    ]
    assert not offenders, (
        f"these rows rendered a stored id instead of its label: {offenders}"
    )

    shown = {r["row_id"]: r["value"] for r in rows}
    assert "Funeral home" in str(shown.values()), (
        f"the Service row never showed the label. rows={shown}"
    )
    assert "Tent Only" in str(shown.values()), shown
