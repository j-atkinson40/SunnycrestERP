"""The call extraction's missing set is computed server-side, and two things
about it must not drift silently.

⚠️ THIS IS NOT A PARITY SUITE AND MUST NOT BE READ AS ONE. The parity run the
2026-10-02 dispatch asked for — stored model-supplied missing sets against the
new server-computed ones — has an EMPTY POPULATION: `ringcentral_call_extractions`
holds 0 rows in `bridgeable_dev` and `ringcentral_call_log` holds 0, because the
RingCentral overlay has no OAuth entrance and no tenant has ever produced a call.
"No disagreements found" over zero rows is the empty-control defect CLAUDE.md §11
names, so no such claim is made here. These are constructed inputs.

What they pin:

1. THE KEY MAPPING. Three of the eight field names differ between the extraction
   payload and the capture schema. A mismatch fails silently — the field reads as
   unanswered forever and is reported missing on every call, with nothing raised.

2. THE CONDITIONAL OMISSION. The three personalization questions are omitted at
   this call site because no vault name resolves to a product id. That omission is
   correct (DECISIONS 2026-09-22, "The capture list shows only the questions that
   apply") and PERMANENT here rather than transient. A later change must not start
   emitting them without a resolver, and must not stop omitting them by accident
   either — both directions are pinned.
"""
from __future__ import annotations

from datetime import date, time

from app.services import capture
from app.services.capture.missing import is_answered
from app.services.call_extraction_service import _captured_from_result

#: A result shaped the way the managed prompt returns one, fully populated.
FULL_RESULT = {
    "vault_type": "Bronze Triune",
    "funeral_home_name": "Hopkins Funeral Home",
    "deceased_name": "John Michael Smith",
    "vault_size": "Standard",
    "cemetery_name": "St Mary's",
    "burial_date": "2026-10-09",
    "burial_time": "14:00",
    "grave_location": "Section C, Lot 14, Space 2",
    # Keys the schema does not know about. Ignored rather than rejected.
    "special_requests": "veteran flag holder",
    "confidence": {"deceased_name": 0.97},
    "missing_fields": ["this is the model's guess and must be ignored"],
}


def _template():
    return capture.template_for(capture.FUNERAL_ORDER)


def _unconditional_ids(template):
    return {f.field_id for f in template if not f.is_conditional}


def _conditional_ids(template):
    return {f.field_id for f in template if f.is_conditional}


class TestTheKeyMapping:
    def test_mapping_covers_exactly_the_unconditional_fields(self):
        """⚠️ SET EQUALITY, NOT A COUNT. A count of 8 == 8 passes when a key is
        both missing and misspelled, which is the pair of mistakes most likely to
        occur together during a rename."""
        template = _template()
        assert set(_captured_from_result(FULL_RESULT)) == _unconditional_ids(template)

    def test_the_three_renamed_keys_land_on_the_schema_ids(self):
        """The whole point of the helper. `vault_type` is not `vault`."""
        got = _captured_from_result(FULL_RESULT)
        assert got["vault"] == "Bronze Triune"
        assert got["funeral_home"] == "Hopkins Funeral Home"
        assert got["cemetery"] == "St Mary's"

    def test_dates_and_times_are_parsed_not_passed_through(self):
        """Parsed values, so the missing set describes the row that is stored.
        An unparseable date persists as NULL; calling it answered would make the
        missing set and the row disagree."""
        got = _captured_from_result(FULL_RESULT)
        assert got["burial_date"] == date(2026, 10, 9)
        assert got["burial_time"] == time(14, 0)

    def test_an_unparseable_date_is_unanswered_rather_than_answered(self):
        got = _captured_from_result({**FULL_RESULT, "burial_date": "sometime next week"})
        assert got["burial_date"] is None
        assert not is_answered(got["burial_date"])


class TestTheServerComputesTheMissingSet:
    def test_a_full_result_leaves_nothing_missing(self):
        state = capture.evaluate(
            _captured_from_result(FULL_RESULT),
            vault_product_id=None,
            platform_fields=_template(),
        )
        assert state.missing == ()
        assert state.is_complete

    def test_an_absent_field_is_reported_missing_by_its_schema_id(self):
        result = {k: v for k, v in FULL_RESULT.items() if k != "cemetery_name"}
        state = capture.evaluate(
            _captured_from_result(result),
            vault_product_id=None,
            platform_fields=_template(),
        )
        assert "cemetery" in state.missing

    def test_the_models_own_missing_fields_key_is_ignored(self):
        """The violation this change retired. `FULL_RESULT` carries a bogus
        `missing_fields` entry; the computed set must owe it nothing."""
        state = capture.evaluate(
            _captured_from_result(FULL_RESULT),
            vault_product_id=None,
            platform_fields=_template(),
        )
        assert state.missing == ()


class TestTheConditionalOmissionIsPinnedInBothDirections:
    def test_the_template_still_carries_conditional_fields(self):
        """⚠️ THE POSITIVE CONTROL, AND IT IS READ FIRST. Every assertion below is
        about conditional fields being ABSENT from a result set. If the template
        stopped having any, those would all pass trivially and the omission would
        look verified while nothing was being checked."""
        assert len(_conditional_ids(_template())) > 0

    def test_no_conditional_field_appears_in_missing(self):
        state = capture.evaluate(
            {}, vault_product_id=None, platform_fields=_template()
        )
        assert _conditional_ids(_template()).isdisjoint(set(state.missing))

    def test_conditional_fields_land_in_not_applicable_and_nowhere_else(self):
        """⚠️ THIS TEST ASSERTED THE OPPOSITE AND WAS WRONG; THE CODE WAS RIGHT.
        It claimed `resolve_schema` drops conditional fields so completely that
        they cannot reach `not_applicable`. They do reach it, and that is the
        three-outcome model working as ruled: absent from `answered` and from
        `missing`, so the capture list renders neither, while a caller can still
        tell "nothing to ask" from "not asked yet".

        That is also what makes the skip measurable — the instrumentation at the
        call site reads `not_applicable` rather than recounting the template."""
        template = _template()
        state = capture.evaluate(
            _captured_from_result(FULL_RESULT),
            vault_product_id=None,
            platform_fields=template,
        )
        conditional = _conditional_ids(template)
        assert conditional.isdisjoint(set(state.answered))
        assert conditional.isdisjoint(set(state.missing))
        assert set(state.not_applicable) == conditional

    def test_everything_unconditional_is_accounted_for(self):
        """The complement of the omission: all 8 land somewhere, so the omission
        cannot quietly widen to swallow a real field."""
        template = _template()
        state = capture.evaluate(
            {}, vault_product_id=None, platform_fields=template
        )
        assert set(state.missing) == _unconditional_ids(template)
