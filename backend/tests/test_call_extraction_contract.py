"""The call-extraction wire contract: the server sends what the client declares.

⚠️ THIS SUITE EXISTS BECAUSE THE TWO SIDES DISAGREED FOR 202 DAYS AND NOTHING
COULD SEE IT. The serializer sent flat strings plus one separate `confidence`
dict; all three client consumers typed every field as `{value, confidence}` and
read `field?.value`. `"a string"?.value` is `undefined`, so **every captured
value came through as undefined on every surface** — 14 rendered entries across
`ActiveCallCard`, `ReviewCard` and the call-log's `ExtractionDetails`, none of
which has ever displayed anything.

`missing_fields` is `string[]` on both sides and worked throughout. That is the
asymmetry in one line: the server-computed set functioned, the client-derived
set never did.

⚠️ AND NO EXISTING CHECK COULD HAVE CAUGHT IT. `tsc` validated the client against
the client's own type. Backend tests validated the serializer against nothing.
vitest mocks the API client. The overlay is unreachable in production, so nobody
could look at it either. A contract needs a test that reads BOTH SIDES, which is
what the set-equality test below is.

⚠️ COLD PATH, AND THE TWO REASONS ARE DIFFERENT. `ringcentral_call_log` holds 0
rows in production (measured 2026-10-05), so no surface has ever had an
extraction to render.

UNREACHABLE and UNEXERCISED are not the same, and only one applies to each
surface:

    CallOverlay      UNREACHABLE  — no authorize endpoint, so no tenant can
                                   connect a phone system and no call arrives
    /calls call log  REACHABLE, UNEXERCISED — the route is mounted and a user
                                   can open it; it renders nothing because the
                                   table is empty

I asserted the first about both and the second was the truth for the call log.
The distinction matters here because it decides what a test can stand in for: on
an unreachable surface these tests are the only possible evidence, while on a
reachable-but-empty one they are the evidence until the first real row arrives.

Either way these tests are the whole of the evidence, not a net under a working
path.
"""
from __future__ import annotations

import pathlib
import re
from datetime import date, time

import pytest

from app.api.routes.call_intelligence import (
    _EXTRACTED_FIELDS,
    _field,
    _serialize_extraction,
)
from app.models.ringcentral_call_extraction import RingCentralCallExtraction

_TS = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
       / "contexts" / "call-context.tsx")


def _ext(**kw) -> RingCentralCallExtraction:
    """An extraction row, unsaved. No DB and no Claude call."""
    base = dict(id="x", tenant_id="t", call_log_id="c")
    base.update(kw)
    return RingCentralCallExtraction(**base)


def _client_extraction_fields() -> set[str]:
    """The field names the shipped client declares on `CallExtraction`."""
    src = _TS.read_text()
    m = re.search(r"export interface CallExtraction \{(.*?)\n\}", src, re.S)
    assert m, "CallExtraction interface not found — the client was restructured"
    body = m.group(1)
    return set(re.findall(r"^\s*([a-z_]+): CallExtractionField \| null;", body, re.M))


class TestTheTwoSidesAgree:
    def test_the_field_sets_are_equal(self):
        """⚠️ THE TEST THAT WOULD HAVE CAUGHT THE ORIGINAL DEFECT, and the four
        phantom fields, and would catch either side drifting again.

        Set equality, not counts — equal cardinalities pass while membership is
        wrong, which is the shape that let four client-only names live.
        """
        server = set(_EXTRACTED_FIELDS)
        client = _client_extraction_fields()
        assert server, "server field tuple is empty — the control failed"
        assert client, "parsed no client fields — the regex is wrong, not the code"
        assert server == client, (
            f"the wire contract disagrees.\n"
            f"  server sends, client does not declare: {sorted(server - client)}\n"
            f"  client declares, server never sends:   {sorted(client - server)}"
        )

    def test_every_server_field_is_a_real_column(self):
        """A field in `_EXTRACTED_FIELDS` with no column would raise at request
        time, not at import."""
        cols = set(RingCentralCallExtraction.__table__.c.keys())
        missing = [f for f in _EXTRACTED_FIELDS if f not in cols]
        assert not missing, f"serialized but not columns: {missing}"

    def test_the_server_computed_pair_is_declared_on_both_sides(self):
        ts = _TS.read_text()
        payload = _serialize_extraction(_ext())
        for key in ("missing_fields", "answered_fields"):
            assert key in payload, f"the serializer does not send {key}"
            assert f"{key}: string[];" in ts, f"the client does not declare {key}"


class TestTheFieldShape:
    def test_a_populated_field_is_value_and_confidence(self):
        e = _ext(deceased_name="John Smith", confidence_json={"deceased_name": 0.97})
        assert _field(e, "deceased_name") == {"value": "John Smith", "confidence": 0.97}

    def test_an_absent_field_is_none_not_an_empty_shape(self):
        """`None` rather than `{"value": "", ...}` — the client's `field?.value`
        guard distinguishes absent from empty, and an empty shape would render as
        a captured blank."""
        assert _field(_ext(), "deceased_name") is None

    def test_a_blank_string_is_absent(self):
        """Whitespace is not a decision — the same rule `is_answered` applies
        server-side in the capture engine."""
        assert _field(_ext(deceased_name="   "), "deceased_name") is None

    def test_confidence_is_none_when_the_model_did_not_say(self):
        """⚠️ NOT 0.0 AND NOT 1.0. A default would assert certainty or doubt that
        nothing measured — CLAUDE.md §5, in a float. The client renders no
        percentage for null."""
        e = _ext(deceased_name="John Smith", confidence_json={})
        assert _field(e, "deceased_name") == {"value": "John Smith", "confidence": None}

    def test_confidence_is_none_when_the_dict_is_null(self):
        e = _ext(deceased_name="John Smith", confidence_json=None)
        assert _field(e, "deceased_name")["confidence"] is None

    def test_a_non_numeric_confidence_is_rejected_to_none(self):
        """The model could return anything. A string in a numeric slot would
        reach the client's `confidence < 0.8` comparison."""
        e = _ext(deceased_name="J", confidence_json={"deceased_name": "high"})
        assert _field(e, "deceased_name")["confidence"] is None

    @pytest.mark.parametrize(
        "name,raw,expected",
        [("burial_date", date(2026, 10, 9), "2026-10-09"),
         ("service_time", time(14, 30), "14:30:00")],
    )
    def test_dates_and_times_reach_the_client_in_iso_form(self, name, raw, expected):
        """⚠️ THIS ASSERTION DOES NOT DISCRIMINATE, AND A BREAK TEST IS HOW I KNOW.

        Renaming from `..._are_isoformatted_...` because that is not what it
        proves. Removing `_field`'s `hasattr(raw, "isoformat")` branch entirely
        and falling back to `str(raw)` leaves this test GREEN — because for
        `date` and `time`, `str()` and `.isoformat()` return the same string:

            str(date(2026, 10, 9))  == "2026-10-09"  == .isoformat()
            str(time(14, 30))       == "14:30:00"    == .isoformat()

        So the isoformat branch is DEFENSIVE, not load-bearing — CLAUDE.md §11,
        "a guard whose protection is supplied by a layer beneath it". It is kept
        because the two forms DIVERGE for `datetime` (`str` gives a space,
        `isoformat` gives a `T`), and a future datetime column would otherwise
        serialize in a form `Date.parse` treats differently across engines. No
        column in `_EXTRACTED_FIELDS` is a datetime today, so that divergence is
        unreachable and deliberately untested rather than tested with a fixture
        the system cannot produce.

        What this test DOES pin, which is worth pinning: the value reaches the
        client as an ISO-form STRING nested under `value`, not as a Python repr
        and not at the top level. That is the part the reshape could have broken.
        """
        assert _field(_ext(**{name: raw}), name) == {"value": expected, "confidence": None}


class TestTheWholePayload:
    def test_every_declared_field_appears_even_when_empty(self):
        """⚠️ Present-and-null, not absent. The client reads
        `extraction.deceased_name?.value`; a missing KEY and a null VALUE behave
        the same in JS here, but an absent key breaks any consumer that
        enumerates the payload."""
        payload = _serialize_extraction(_ext())
        for name in _EXTRACTED_FIELDS:
            assert name in payload, f"{name} absent from the payload"
            assert payload[name] is None

    def test_the_flat_form_is_gone(self):
        """⚠️ THE DISCRIMINATING ASSERTION. A serializer that sent BOTH shapes
        would satisfy every test above while leaving the ambiguity that caused
        this. There must be no top-level `confidence` dict and no flat string."""
        payload = _serialize_extraction(
            _ext(deceased_name="John Smith", confidence_json={"deceased_name": 0.9})
        )
        assert "confidence" not in payload, (
            "the payload still carries a separate top-level confidence dict"
        )
        assert payload["deceased_name"] == {"value": "John Smith", "confidence": 0.9}
        assert not isinstance(payload["deceased_name"], str)
