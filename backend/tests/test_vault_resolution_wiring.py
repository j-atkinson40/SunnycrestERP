"""The vault phrase reaches the resolver, and the conditionals finally appear.

⚠️ THE CENTRAL ASSERTION HERE HAS NEVER BEEN TRUE IN THIS CODEBASE UNTIL NOW.

`resolve_schema` omits the three conditional personalization questions when
`vault_product_id is None`. That argument was None at every call site since the
field existed, because nothing turned a vault NAME into a product id. So those
three questions had never been asked on any call — not intermittently, never —
and `resolve_schema`'s only conditional branch had never executed.

`test_the_conditionals_APPEAR_once_a_vault_resolves` is the assertion that proves
the loop is closed. It is also the reason this file exists rather than more cases
in an existing one: it is a claim about the whole path, not about a function.

⚠️ THREE OUTCOMES, AND THE MIDDLE ONE IS THE NEW BEHAVIOUR. A caller treating
"ambiguous" and "unresolved" alike discards the entire reason the resolver returns
a set — `Resolution.variant_template_id` is None in BOTH cases, so reading it
alone collapses them. `TestTheAmbiguousCaseIsAQuestionNotAFailure` is where this
would go wrong.

⚠️ COLD PATH. `ringcentral_call_extractions` holds 0 rows in dev and 0 in
production, and the overlay has no entrance, so these are constructed inputs
against the real catalog.
"""
from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.services import capture
from app.services.call_extraction_service import (
    _resolution_payload,
    _resolve_vault_phrase,
    resolve_and_evaluate,
)
from app.services.capture import SALES_ORDER, template_for

#: Resolves to exactly one variant — BV-BTRI, via the full display name.
UNAMBIGUOUS = "Bronze Triune Burial Vault"
#: Resolves to two — BV-BTRI and UV-BTRI. The question is FORM.
AMBIGUOUS = "Bronze Triune"


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _conditional_ids():
    """⚠️ NARROWED 2026-10-06 TO THE AVAILABILITY-GATED FIELDS, AND THE NARROWING IS
    THE POINT. This read `if f.is_conditional`, which was the same set while the only
    conditional shape WAS the availability lookup. Piece 4 added three conditionals
    that depend on ANSWERS rather than on the vault — `eta`,
    `service_location_other`, `nameplate_date_format` — and those correctly do NOT
    appear when a vault resolves, because what they wait on is a different field.

    Left broad, this file would have asserted that resolving a vault makes every
    conditional field appear, which is false and is not what these tests are about.
    """
    from app.services.capture.conditions import AvailabilityOffered

    return {
        f.field_id
        for f in template_for(SALES_ORDER)
        if isinstance(f.applies_when, AvailabilityOffered)
    }


class TestTheLoopIsClosed:
    def test_the_conditionals_APPEAR_once_a_vault_resolves(self, db):
        """⚠️ THE ASSERTION THAT HAS NEVER BEEN TRUE HERE BEFORE.

        With a resolved vault the three personalization questions enter the
        capture state. They arrive as NOT_CONFIGURED rather than OFFERED — no
        licensee has configured availability (`wilbert_program_enrollments` holds
        zero rows), and canon says NOT CONFIGURED MEANS ASK. So they are present
        and unanswered, which is correct: the question applies until a licensee
        says otherwise.
        """
        # ⚠️ THROUGH THE SEAM, NOT AROUND IT. An earlier version of this test
        # called `capture.evaluate` itself with the resolved id — which proved
        # the two pieces compose and NOT that the service wires them. Reverting
        # `vault_product_id` to None turned no test red. `resolve_and_evaluate`
        # is the real path.
        r, state = resolve_and_evaluate(db, {"vault_type": UNAMBIGUOUS})
        assert r.resolved, [c.sku for c in r.candidates]
        appeared = _conditional_ids() & (set(state.missing) | set(state.answered))
        assert appeared == _conditional_ids(), (
            f"the conditional questions did not appear: expected "
            f"{sorted(_conditional_ids())}, saw {sorted(appeared)}"
        )
        assert not set(state.not_applicable) & _conditional_ids()

    def test_they_are_STILL_omitted_without_a_vault(self, db):
        """⚠️ THE CONTROL, and it is the old behaviour. A change that made the
        conditionals appear unconditionally would satisfy the test above while
        asking about personalization before a vault is named — which canon
        forbids: applicability is unknown until there is a product to read it
        against."""
        _, state = resolve_and_evaluate(db, {})
        # ⚠️ `indeterminate`, NOT `not_applicable` — CHANGED BY PIECE 4, AND THIS IS
        # THE CORRECTNESS GAIN RATHER THAN A RELAXATION. Before 2026-10-06 these
        # landed in `not_applicable`, which asserts "this vault does not offer the
        # question". No vault has been named, so nothing of the kind was established.
        # The two states were the same silence; now they are not.
        assert set(state.indeterminate) >= _conditional_ids()
        assert not set(state.not_applicable) & _conditional_ids(), (
            "a question nobody can resolve yet must NOT read as not-offered"
        )
        assert not _conditional_ids() & set(state.missing)


class TestTheSizeGoesInWithThePhrase:
    def test_a_separately_heard_size_resolves_the_family(self, db):
        """⚠️ THE `vault_size` RULING, EXERCISED. "Continental" alone is
        ambiguous between BV-CON and BV-CON34; with the size it is not. The
        extractor may hear the two apart, so the service rejoins them."""
        bare = _resolve_vault_phrase(db, {"vault_type": "Continental"})
        assert bare.ambiguous
        joined = _resolve_vault_phrase(
            db, {"vault_type": "Continental", "vault_size": "34 inch"})
        assert joined.resolved
        assert joined.candidates[0].sku == "BV-CON34"

    def test_an_unstocked_size_falls_back_to_the_family(self, db):
        """⚠️ THE FALLBACK, AND WHY IT IS NOT A SILENT GUESS. "Continental 40
        inch" matches nothing; without the fallback that is a dead end, when the
        bare family would at least have offered two candidates and a size
        question. It falls back to CANDIDATES, never to a pick."""
        r = _resolve_vault_phrase(
            db, {"vault_type": "Continental", "vault_size": "40 inch"})
        assert r.ambiguous
        assert {c.sku for c in r.candidates} == {"BV-CON", "BV-CON34"}
        assert r.variant_template_id is None

    def test_a_size_that_does_not_help_does_not_break_a_good_phrase(self, db):
        r = _resolve_vault_phrase(
            db, {"vault_type": UNAMBIGUOUS, "vault_size": "standard"})
        assert r.resolved


class TestTheAmbiguousCaseIsAQuestionNotAFailure:
    def test_the_payload_distinguishes_ambiguous_from_no_match(self, db):
        """⚠️ WHERE THIS WOULD GO WRONG. `variant_template_id` is None for BOTH,
        so a caller reading only that collapses them. The payload must not."""
        amb = _resolution_payload(_resolve_vault_phrase(db, {"vault_type": AMBIGUOUS}))
        none = _resolution_payload(
            _resolve_vault_phrase(db, {"vault_type": "a vault nobody sells"}))

        assert amb["resolved_variant_id"] is None
        assert none["resolved_variant_id"] is None
        # …and yet they are plainly different states
        assert len(amb["candidates"]) > 1
        assert none["candidates"] == []
        assert amb["discriminator"] == "form"
        assert none["discriminator"] is None
        assert amb != none

    def test_the_candidates_are_skus_a_human_can_read(self, db):
        """A uuid tells a reader nothing; BV-BTRI and UV-BTRI show at a glance
        that the question is burial-versus-urn."""
        p = _resolution_payload(_resolve_vault_phrase(db, {"vault_type": AMBIGUOUS}))
        assert set(p["candidates"]) == {"BV-BTRI", "UV-BTRI"}

    def test_an_ambiguous_phrase_leaves_the_conditionals_omitted(self, db):
        """Correct, and the reason the discriminator has to travel: without a
        resolved vault there is nothing to read availability against, so the
        questions stay out — and the ONLY thing that tells a user why is the
        question the payload carries."""
        r, state = resolve_and_evaluate(db, {"vault_type": AMBIGUOUS})
        # ⚠️ AMBIGUITY IS INDETERMINATE, NOT NOT-OFFERED, and this is the sharpest
        # case for the fifth set. The resolver returns a candidate set plus a
        # discriminator and NEVER a best match, so `variant_template_id` is None here
        # — identical to "no vault named". Before Piece 4 both produced
        # `not_applicable`, so "which of these two vaults?" was indistinguishable
        # from "this vault does not offer personalization".
        assert set(state.indeterminate) >= _conditional_ids()
        assert not set(state.not_applicable) & _conditional_ids()
        assert _resolution_payload(r)["discriminator"] == "form"

    def test_an_absent_phrase_is_not_attempted_rather_than_unmatched(self, db):
        """`phrase` empty and `candidates` empty — the row records that nothing
        was said about a vault, which is different from a phrase that failed."""
        p = _resolution_payload(_resolve_vault_phrase(db, {}))
        assert p["phrase"] == ""
        assert p["candidates"] == []


class TestThePersistedShape:
    def test_the_model_declares_the_column(self):
        from app.models.ringcentral_call_extraction import RingCentralCallExtraction

        col = RingCentralCallExtraction.__table__.c.vault_resolution
        assert col.nullable is True
        assert col.default is None and col.server_default is None

    def test_the_service_persists_the_resolution(self):
        """⚠️ A SOURCE ASSERTION, AND I AM LABELLING IT RATHER THAN DRESSING IT UP.

        A break test caught its absence: removing
        `vault_resolution=_resolution_payload(...)` from the row construction
        turned NO test red, because the only path that builds a
        `RingCentralCallExtraction` is `extract_call_data`, which is gated on a
        Claude call, and the table holds 0 rows in dev and production.

        Unlike `resolve_and_evaluate` — which I extracted as a seam precisely so
        its break would fire — the construction site cannot be reached without
        either a model call or restructuring the whole function, which is more
        than this change should carry.

        What it catches is the regression that matters: the persist line being
        deleted while the resolve stays, which would compute the resolution and
        throw it away. That is the shape this arc has found six times, and it
        would be invisible here otherwise. Replace with a behavioural test when
        the extraction path becomes callable.
        """
        import inspect

        from app.services import call_extraction_service

        src = inspect.getsource(call_extraction_service)
        assert "vault_resolution=_resolution_payload(vault_resolution)" in src, (
            "the service resolves the vault phrase and does not persist the "
            "result — the ambiguity reaches the client as silence"
        )

    def test_the_serializer_sends_it(self):
        import inspect

        from app.api.routes import call_intelligence

        src = inspect.getsource(call_intelligence._serialize_extraction)
        assert '"vault_resolution"' in src

    def test_the_client_declares_it(self):
        """⚠️ READS THE SHIPPED CLIENT. A field the server sends and the client
        does not declare cannot be rendered, and no backend test would say so."""
        import pathlib

        ts = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
              / "contexts" / "call-context.tsx").read_text()
        assert "vault_resolution" in ts
        assert "discriminator" in ts
