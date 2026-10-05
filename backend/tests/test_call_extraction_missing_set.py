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
    return capture.template_for(capture.SALES_ORDER)


#: ⚠️ REQUIRED, AND PERMANENTLY UNEXTRACTABLE AT THIS CALL SITE. Added to the
#: template 2026-10-05 by ruling: every funeral has a service location and
#: `graveside` is an answer rather than an absence. Nothing extracts it — the
#: managed prompt does not ask, `ringcentral_call_extractions` has no column, and
#: `_captured_from_result` cannot map what the payload does not carry. So a
#: "complete" call result still leaves exactly this one field missing, and that
#: is CORRECT: a required field nobody answered is missing.
#:
#: Named here rather than repeated as a literal so the next reader finds one fact
#: with one reason, and so a second such field has somewhere to join.
UNEXTRACTABLE_REQUIRED = {"service_location"}

#: Unconditional, unmapped by the adapter, and NOT required — so they never
#: appear in `missing` and their absence is invisible in the missing set.
#:
#: ⚠️ KEPT SEPARATE FROM THE REQUIRED SET ON PURPOSE. Both are "the adapter
#: cannot supply this", but only the required one is a reported gap. Merging them
#: would make the suite assert that optional unmapped fields show up as missing,
#: which is the opposite of what optional means. Added 2026-10-05 with the three
#: new fields; nothing extracts dates or equipment from a call yet.
UNEXTRACTABLE_OPTIONAL = {"date_of_birth", "date_of_death", "cemetery_equipment"}

UNEXTRACTABLE = UNEXTRACTABLE_REQUIRED | UNEXTRACTABLE_OPTIONAL


def _unconditional_ids(template):
    return {f.field_id for f in template if not f.is_conditional}


def _extractable_unconditional_ids(template):
    """Unconditional fields the call payload can actually supply."""
    return _unconditional_ids(template) - UNEXTRACTABLE


def _conditional_ids(template):
    return {f.field_id for f in template if f.is_conditional}


class TestTheKeyMapping:
    def test_mapping_covers_exactly_the_unconditional_fields(self):
        """⚠️ SET EQUALITY, NOT A COUNT. A count of 8 == 8 passes when a key is
        both missing and misspelled, which is the pair of mistakes most likely to
        occur together during a rename."""
        template = _template()
        assert (set(_captured_from_result(FULL_RESULT))
                == _extractable_unconditional_ids(template))

    def test_the_only_unmappable_unconditional_field_is_the_named_one(self):
        """⚠️ THE GROWTH, ASSERTED IN BOTH DIRECTIONS. The adapter covers every
        unconditional field except `service_location`. If a second field ever
        becomes unmappable this fails and the exception has to be declared
        deliberately rather than absorbed into a shrinking set."""
        template = _template()
        gap = _unconditional_ids(template) - set(_captured_from_result(FULL_RESULT))
        assert gap == UNEXTRACTABLE, (
            f"the unmappable set is {sorted(gap)}, declared {sorted(UNEXTRACTABLE)}"
        )

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
    def test_a_full_result_leaves_exactly_the_unextractable_field_missing(self):
        """⚠️ RENAMED FROM `..._leaves_nothing_missing`, 2026-10-05, and the
        rename is the finding. A full call result is no longer complete, because
        `service_location` joined the template as required and nothing extracts
        it. `state.missing == ()` was true of an 11-field template and is now
        false — asserting the exact remainder rather than relaxing to
        `len(missing) <= 1` keeps the claim checkable."""
        state = capture.evaluate(
            _captured_from_result(FULL_RESULT),
            vault_product_id=None,
            platform_fields=_template(),
        )
        assert set(state.missing) == UNEXTRACTABLE_REQUIRED
        assert not state.is_complete, (
            "a call-sourced capture cannot be complete while a required field "
            "has no extraction source — if this passes, either the field was "
            "made optional or something started supplying it"
        )

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
        # The model's bogus entry is absent; what remains is the one field the
        # payload cannot carry, not anything the model said.
        assert set(state.missing) == UNEXTRACTABLE_REQUIRED


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
        # ⚠️ REQUIRED only. Optional unconditional fields are never "missing" —
        # see test_capture_schema's partition test for why CaptureState has no
        # bucket for them at all.
        required_unconditional = {
            f.field_id for f in template if not f.is_conditional and f.required
        }
        assert set(state.missing) == required_unconditional


class TestTheServerDecidesWhatIsCapturedToo:
    """⚠️ THE UNSTATED HALF OF THE RULE, persisted by r197.

    `The model extracts; the server decides what is missing` left `answered`
    unspecified. The server computed it, wrote it to one log line and discarded
    it, so the client had nothing to render for "captured" and re-derived it —
    twice, from two hardcoded lists that disagree with each other and with the
    template. The pair is now symmetric: both are server-computed, both are
    persisted, the client renders both and derives neither.

    ⚠️ These are CONSTRUCTED INPUTS over an EMPTY TABLE, like the rest of this
    file. `ringcentral_call_extractions` holds 0 rows and the overlay has no
    production entrance, so there is no behaviour to compare against — this is
    the whole of the evidence, not a net under a working path.
    """

    def test_the_answered_set_is_not_empty_for_a_full_result(self):
        """⚠️ POSITIVE CONTROL FIRST. Every assertion below is about the CONTENT
        of the answered set; if it were empty they would pass while proving
        nothing."""
        template = _template()
        state = capture.evaluate(
            _captured_from_result(FULL_RESULT),
            vault_product_id=None,
            platform_fields=template,
        )
        assert set(state.answered) == _extractable_unconditional_ids(template), (
            f"expected every extractable unconditional field answered from a "
            f"full result; got {sorted(state.answered)}"
        )

    def test_answered_and_missing_partition_the_applicable_fields(self):
        """The two sets are complements, not two opinions. Anything neither
        answered nor missing must be in `not_applicable` — the third outcome."""
        template = _template()
        state = capture.evaluate(
            {"deceased_name": "John Smith", "cemetery": "St Mary's"},
            vault_product_id=None,
            platform_fields=template,
        )
        assert set(state.answered) == {"deceased_name", "cemetery"}
        assert set(state.answered) & set(state.missing) == set(), (
            "a field cannot be both answered and missing"
        )
        # ⚠️ FOUR SETS, FROM THE TYPE ITSELF. For one commit this test derived
        # the optional-unanswered bucket locally because CaptureState had no slot
        # for it; it has one now, so the assertion reads the type rather than
        # reconstructing what the type forgot.
        covered = (set(state.answered) | set(state.missing)
                   | set(state.unanswered_optional) | set(state.not_applicable))
        assert covered == {f.field_id for f in template}, (
            f"these template fields appear in no set: "
            f"{ {f.field_id for f in template} - covered}"
        )

    def test_none_is_answered_and_lands_in_answered_not_missing(self):
        """`none` clears a requirement — the ruling this engine is built on. It
        must appear in `answered`, which is only checkable now that `answered`
        is a persisted output rather than a log line."""
        template = _template()
        state = capture.evaluate(
            {"grave_location": "none"},
            vault_product_id=None,
            platform_fields=template,
        )
        assert "grave_location" in state.answered
        assert "grave_location" not in state.missing

    def test_an_optional_unanswered_field_has_a_home(self):
        """⚠️ THE SET THAT DID NOT EXIST, AND WHY IT HAD TO.

        `date_of_birth`, `date_of_death` and `cemetery_equipment` are optional and
        nothing extracts them from a call. Before 2026-10-05 they were in no set
        at all — not answered, not missing, not inapplicable — so a consumer
        reading CaptureState could not tell them from fields the engine had
        forgotten. "Absent from all three sets" is not a state.
        """
        template = _template()
        state = capture.evaluate(
            _captured_from_result(FULL_RESULT),
            vault_product_id=None,
            platform_fields=template,
        )
        assert set(state.unanswered_optional) == UNEXTRACTABLE_OPTIONAL
        # and they are NOT reported as gaps
        assert not (set(state.unanswered_optional) & set(state.missing))
        assert state.is_complete is False, "the required gap still stands"

    def test_an_order_IS_COMPLETE_with_optional_fields_unanswered(self):
        """⚠️ THE READY-TO-APPROVE STATE, AND NOTHING TESTED IT UNTIL A BREAK TEST
        CAME BACK BLIND.

        Every other test here has a required gap outstanding, so `is_complete` is
        False for that reason and folding `unanswered_optional` into it changed
        nothing — break E3 turned zero tests red. The discriminating case is the
        one a licensee actually reaches: every REQUIRED field answered, the
        optional dates and equipment left blank, order ready to approve.

        If `is_complete` ever folds in `unanswered_optional`, no order is
        approvable until someone answers three fields the design does not require.
        That is the whole reason the property was left alone.
        """
        template = _template()
        answers = {
            f.field_id: "x" for f in template
            if f.required and not f.is_conditional
        }
        state = capture.evaluate(
            answers, vault_product_id=None, platform_fields=template)

        assert state.missing == (), (
            f"a required field is still unanswered: {state.missing}"
        )
        assert state.unanswered_optional, (
            "no optional field is unanswered — this test cannot discriminate"
        )
        assert state.is_complete is True, (
            "an order with only OPTIONAL fields unanswered is not complete — "
            "nothing would ever be approvable"
        )

    def test_an_ANSWERED_optional_field_is_answered_not_optional_unanswered(self):
        """⚠️ THE CONTROL. A set that collected every optional field regardless of
        its answer would satisfy the test above."""
        template = _template()
        state = capture.evaluate(
            {**_captured_from_result(FULL_RESULT), "date_of_birth": "1948-03-14"},
            vault_product_id=None,
            platform_fields=template,
        )
        assert "date_of_birth" in state.answered
        assert "date_of_birth" not in state.unanswered_optional

    def test_the_model_cannot_influence_the_answered_set(self):
        """⚠️ THE DISCRIMINATING CASE, and the mirror of what r196-era code did
        wrong with `missing`. A model that volunteers its own answered list must
        not be able to add a field to the real one."""
        template = _template()
        poisoned = dict(FULL_RESULT)
        poisoned["answered_fields"] = ["legacy_print", "nameplate_cover_emblem"]
        state = capture.evaluate(
            _captured_from_result(poisoned),
            vault_product_id=None,
            platform_fields=template,
        )
        assert "legacy_print" not in state.answered
        assert "nameplate_cover_emblem" not in state.answered


class TestTheColumnAndTheSerializer:
    """r197's two halves: the column exists as declared, and the pair is served."""

    def test_the_column_is_nullable_with_no_default(self):
        """⚠️ NULL means no answered set was computed for this row; `[]` means
        the capture answered nothing. A default would assert the second for rows
        nothing computed one for — CLAUDE.md §5."""
        from app.models.ringcentral_call_extraction import RingCentralCallExtraction

        col = RingCentralCallExtraction.__table__.c.answered_fields
        assert col.nullable is True
        assert col.default is None, "a Python-side default would re-assert on insert"
        assert col.server_default is None

    def test_the_serializer_returns_both_halves(self):
        """The asymmetry this closes was visible here: `missing_fields` was
        served and `answered_fields` did not exist."""
        import inspect

        from app.api.routes import call_intelligence

        src = inspect.getsource(call_intelligence._serialize_extraction)
        assert '"missing_fields"' in src
        assert '"answered_fields"' in src, (
            "the serializer sends missing but not answered — the client is left "
            "to re-derive the captured set, which is the defect r197 removes"
        )

    def test_the_client_type_declares_the_server_computed_pair(self):
        """⚠️ READS THE SHIPPED CLIENT. A field the server sends and the client
        does not declare cannot be rendered, and nothing in the backend would
        say so — the same gap that let two hardcoded lists live."""
        import pathlib

        ts = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
              / "contexts" / "call-context.tsx").read_text()
        assert "missing_fields: string[];" in ts
        assert "answered_fields: string[];" in ts, (
            "the client does not declare answered_fields, so it cannot render "
            "the server's captured set"
        )

    def test_the_service_persists_the_answered_set(self):
        """⚠️ A SOURCE ASSERTION, AND I AM SAYING SO RATHER THAN DRESSING IT UP.

        This reads the construction site instead of exercising it. That is the
        weaker kind of test — it pins what the file says, not what the code does,
        and a data test would be better.

        A data test is not reachable today: the only path that constructs a
        `RingCentralCallExtraction` is `extract_call_data`, which is gated on a
        Claude call, and the table holds 0 rows because the overlay has no
        production entrance. There is nothing to read back and no seam to call.

        What it does catch is the regression that matters: someone deleting the
        `answered_fields=` line while `missing_fields=` stays, which is exactly
        the asymmetry r197 exists to remove and which no other test in this file
        would notice. Replace this with a behavioural test when the extraction
        path becomes callable — the condition is RingCentral provisioning, the
        same gate the conditional-omission tests above are waiting on.
        """
        import inspect

        from app.services import call_extraction_service

        src = inspect.getsource(call_extraction_service)
        assert "missing_fields=list(capture_state.missing)" in src
        assert "answered_fields=list(capture_state.answered)" in src, (
            "the service computes answered and does not persist it — the r197 "
            "asymmetry is back, and the client is left to re-derive the "
            "captured set"
        )
