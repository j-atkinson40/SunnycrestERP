"""What counts as a change, and which one Opas asks about. No database, no model.

James's dispatch of 2026-10-26, clause 1. The database-backed half — the record, the
rulebook, the route — is in `test_rulebook.py`; these are the rules, so this file has no
`DATABASE_URL` guard. That split is the 2026-10-23 lesson: a module-level skip made 44
tests one SKIPPED line locally while CI ran them, and a pure-function test among them
broke.

⚠️ FOUR OF THE SIX CASES HERE ASSERT THAT OPAS DOES **NOT** ASK, which is most of the
feature. "Not a change: a field first filled by the person, an answer to Opas's own
question or choice list, churn while typing." An absence is satisfied by a detector that
never fires at all, so every one of them sits beside a positive control.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest

from app.services.capture.why import (
    IMPORTANCE,
    SOURCE_DEFAULT,
    SOURCE_EXTRACTION,
    SOURCE_PREFILL,
    Change,
    ask_payload,
    changes,
    display,
    is_continuation,
    prompt_for,
    remember,
    top_change,
)


class FakeSession:
    """The three fields `why` reads, and nothing else.

    ⚠️ NOT A `CaptureSession`. Every function under test reads `opas_proposed`,
    `resolutions`, `values`, `object_type` and `sales_order_id` — so a real model here
    would need a database to be constructed and would test the ORM rather than the rule.
    The shape is taken from the COLUMNS, not from reading `why.py`.
    """

    def __init__(self, **kw):
        self.opas_proposed = kw.get("opas_proposed")
        self.resolutions = kw.get("resolutions")
        self.values = kw.get("values")
        self.object_type = kw.get("object_type", "sales_order")
        self.sales_order_id = kw.get("sales_order_id", "order-1")


# ── what Opas is remembered as having proposed ────────────────────────────────


def test_a_first_reading_is_remembered_with_its_source():
    row = FakeSession()
    remember(row, {"vault": "Monticello Burial Vault", "funeral_home": "Hopkins"})
    assert row.opas_proposed == {
        "vault": {"value": "Monticello Burial Vault", "source": SOURCE_EXTRACTION},
        "funeral_home": {"value": "Hopkins", "source": SOURCE_EXTRACTION},
    }


def test_a_switched_field_is_a_default_rather_than_a_reading():
    """⚠️ JAMES NAMES THIS SOURCE SEPARATELY — "a default it picked like burial versus
    urn". A misread and a default being wrong are different events, and the rule drafted
    from one should not read like the other."""
    row = FakeSession()
    remember(row, {"vault": "Monticello Burial Vault"},
             switch_fields=frozenset({"vault"}))
    assert row.opas_proposed["vault"]["source"] == SOURCE_DEFAULT


def test_churn_refreshes_and_an_edit_freezes():
    """⚠️ THE WHOLE OF "compare settled values only". `mont` finishing as `monticello`
    must not read as a change; `monticello` becoming `continental` must."""
    row = FakeSession()
    remember(row, {"vault": "Mont"}, continuing=True)
    remember(row, {"vault": "Monticello Burial Vault"}, continuing=True)
    assert row.opas_proposed["vault"]["value"] == "Monticello Burial Vault", "refreshed"

    # The person goes back and changes the word: what Opas HAD is the baseline.
    remember(row, {"vault": "Continental Burial Vault"}, continuing=False)
    assert row.opas_proposed["vault"]["value"] == "Monticello Burial Vault", "frozen"

    # ⚠️ AND A FIELD THAT IS NEW AFTER THE EDIT IS STILL RECORDED. Freezing is per
    # FIELD; an edit must not stop Opas proposing anything ever again.
    remember(row, {"vault": "Continental Burial Vault", "cemetery": "St. Mary's"},
             continuing=False)
    assert row.opas_proposed["cemetery"]["value"] == "St. Mary's"


def test_a_resolved_field_is_never_overwritten_by_the_persons_own_choice():
    """⚠️ THE ONE THAT MAKES THE DETECTION WORK AT ALL. `values` arrives WITH resolutions
    applied, so for a resolved field it already holds the person's choice. Writing that
    in would make Opas the author of the change and leave nothing to ask about.
    """
    row = FakeSession(resolutions={"vault": "Continental Burial Vault"})
    remember(row, {"vault": "Monticello Burial Vault"})
    assert row.opas_proposed is None or "vault" not in (row.opas_proposed or {})
    # The control: an unresolved field on the same call IS recorded.
    remember(row, {"vault": "X", "cemetery": "St. Mary's"})
    assert row.opas_proposed["cemetery"]["value"] == "St. Mary's"


def test_an_empty_value_is_not_a_proposal():
    row = FakeSession()
    remember(row, {"vault": "", "cemetery": None, "funeral_home": "   "})
    assert row.opas_proposed in (None, {})


@pytest.mark.parametrize("old,new,expected", [
    (None, "order hopkins", True),
    ("", "order hopkins", True),
    ("order hopkins", "order hopkins monticello", True),
    ("order hopkins", "order hopkins ", True),
    ("order hopkins monticello", "order hopkins continental", False),
    # ⚠️ A DELETION IS TREATED AS AN EDIT, which errs toward asking. Stated as a case
    # rather than left to be discovered: the alternative errs toward silence.
    ("order hopkins monticello", "order hopkins", False),
])
def test_is_continuation(old, new, expected):
    assert is_continuation(old, new) is expected


# ── what counts as a change ───────────────────────────────────────────────────


def test_the_change_opas_asks_about():
    row = FakeSession(
        opas_proposed={"vault": {"value": "Monticello Burial Vault", "source": "default"}},
        values={"vault": "Continental Burial Vault"},
    )
    got = changes(row)
    assert len(got) == 1
    assert (got[0].field_id, got[0].was, got[0].now) == (
        "vault", "Monticello Burial Vault", "Continental Burial Vault",
    )
    assert prompt_for(got[0]) == (
        "You changed the vault from Monticello Burial Vault "
        "to Continental Burial Vault. Why?"
    )


def test_a_field_the_person_filled_first_is_not_a_change():
    """Opas proposed nothing, so there is nothing it got wrong."""
    row = FakeSession(opas_proposed={}, values={"cemetery": "St. Mary's Cemetery"})
    assert changes(row) == []
    # The control: the same field, proposed and then changed, IS one.
    assert len(changes(FakeSession(
        opas_proposed={"cemetery": {"value": "Oakwood", "source": "extraction"}},
        values={"cemetery": "St. Mary's Cemetery"},
    ))) == 1


def test_a_value_opas_kept_is_not_a_change():
    row = FakeSession(
        opas_proposed={"vault": {"value": "Monticello Burial Vault", "source": "default"}},
        values={"vault": "Monticello Burial Vault"},
    )
    assert changes(row) == []


def test_case_and_whitespace_are_not_a_change():
    """⚠️ EXTRACTION TITLE-CASES AND PEOPLE DO NOT. Asking why somebody changed a value
    to itself is how the office learns the feature is noise."""
    row = FakeSession(
        opas_proposed={"vault": {"value": "Monticello Burial Vault", "source": "x"}},
        values={"vault": "  monticello burial vault "},
    )
    assert changes(row) == []


def test_a_value_deleted_is_not_a_change_to_ask_about():
    """"You changed the vault from Monticello to nothing. Why?" is not a sentence worth
    sending — and deleting is a different event from replacing."""
    row = FakeSession(
        opas_proposed={"vault": {"value": "Monticello Burial Vault", "source": "x"}},
        values={},
    )
    assert changes(row) == []


def test_dates_compare_the_same_whichever_way_they_arrive():
    """⚠️ JSONB HANDS BACK STRINGS AND EXTRACTION HANDS BACK OBJECTS, and the same
    session hands over both — `values` is read from the column on one request and built
    in memory on another."""
    row = FakeSession(
        opas_proposed={"service_date": {"value": "2026-10-28", "source": "extraction"}},
        values={"service_date": date(2026, 10, 28)},
    )
    assert changes(row) == []
    assert display(datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)) == "2026-10-28"
    assert display(time(10, 0)) == "10:00:00"
    assert display(None) == ""


# ── which one ─────────────────────────────────────────────────────────────────


def test_one_question_at_most_and_the_most_important_change_wins():
    """James's order, verbatim: "vault, funeral home, cemetery, service date/time, then
    the rest"."""
    row = FakeSession(
        opas_proposed={
            "service_time": {"value": "10:00", "source": "extraction"},
            "funeral_home": {"value": "Hopkins", "source": "extraction"},
            "vault": {"value": "Monticello", "source": "default"},
            "deceased_name": {"value": "smith", "source": "extraction"},
        },
        values={
            "service_time": "11:00", "funeral_home": "Riverside",
            "vault": "Continental", "deceased_name": "hart",
        },
    )
    got = changes(row)
    assert [c.field_id for c in got] == [
        "vault", "funeral_home", "service_time", "deceased_name",
    ]
    assert top_change(row).field_id == "vault"
    # ⚠️ ONE. The payload carries a single change however many moved.
    assert ask_payload(row)["field"] == "vault"


def test_the_ranking_is_james_s_order():
    """⚠️ THE VALUE, PINNED. Every test above builds its fixture from field names, so
    each would stay green if the ranking were reordered to meet it. This came from
    outside the code."""
    assert IMPORTANCE == (
        "vault", "funeral_home", "cemetery", "service_date", "service_time",
    )


def test_an_unranked_field_sorts_after_every_ranked_one():
    assert Change("zzz", "Z", "a", "b", "x").rank > Change("service_time", "T", "a", "b", "x").rank


# ── when it asks ──────────────────────────────────────────────────────────────


def test_nothing_is_asked_before_the_order_exists():
    """⚠️ "It never asks while you're typing." An unapproved capture has no order, and
    that is what "after you approve" is in data."""
    row = FakeSession(
        opas_proposed={"vault": {"value": "Monticello", "source": "default"}},
        values={"vault": "Continental"},
        sales_order_id=None,
    )
    assert ask_payload(row) is None
    # The control: the same session, approved, does ask.
    row.sales_order_id = "order-1"
    assert ask_payload(row) is not None


def test_the_payload_carries_what_the_bar_needs_and_no_more():
    row = FakeSession(
        opas_proposed={"vault": {"value": "Monticello", "source": SOURCE_PREFILL}},
        values={"vault": "Continental"},
    )
    got = ask_payload(row)
    assert set(got) == {"field", "label", "was", "now", "source", "prompt"}
    assert got["label"] == "Vault", "the capture template's own label"
    assert got["source"] == SOURCE_PREFILL
