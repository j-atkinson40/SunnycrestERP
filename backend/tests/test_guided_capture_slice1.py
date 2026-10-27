"""Guided capture, slice 1: the question, its pills, and what changing an answer clears.

James's dispatch of 2026-10-27. Each test names the clause it holds.

⚠️ THE EXPECTED ORDERINGS ARE HAND-COMPUTED AND WRITTEN AS LITERALS, never derived by
calling the thing under test. CLAUDE.md §11 shape 9: a check written from the
implementation asserts the value the implementation produces. So every expectation here
is worked out from the RULING — "at least 2 orders and at least 25%, max 3", "this
customer's usual first, then the tenant's most ordered" — with the arithmetic shown.

⚠️ AND THE ORDER FIXTURES ARE REAL `OrderFacts`, not dicts shaped like them. The pills
read attributes off whatever `load_facts` returns; a dict double would agree with my
reading of that code rather than with the code.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest

from app.services.capture import schema
from app.services.capture.pills import (
    BURIAL_ONLY_EQUIPMENT,
    DAYS_OFFERED,
    MAX_PILLS,
    Pill,
    _habit_then_tenant,
    _service_days,
)
from app.services.capture.schema import (
    CREMATION_CHIP,
    CREMATION_EQUIPMENT_HINT,
    CREMATION_EQUIPMENT_QUESTION,
    hint_for,
    next_field,
    next_question,
    question_for,
)
from app.services.capture.vault_form import (
    CREMATION_FORMS,
    FORM_BURIAL_VAULT,
    FORM_URN,
    FORM_URN_VAULT,
    VIA_RECORDED_NAME,
    VaultForm,
    _key,
    _step_recorded_name,
)
from app.services.order_list.customer import (
    MAX_HABITS,
    MIN_HABIT_ORDERS,
    MIN_HABIT_SHARE,
    rank_habits,
)
from app.services.order_list.stage import OrderFacts
from app.services.personalization.questions import ANSWER_NONE
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture


def order(**over) -> OrderFacts:
    """One order, with only the fields the pills read set.

    ⚠️ THE REAL DATACLASS, so a field renamed on `OrderFacts` turns these red rather
    than leaving a dict double agreeing with a stale reading.
    """
    base = dict(
        id="o", number="SO-1", deceased_name="Smith", funeral_home="Hopkins",
        total=Decimal("0"), status="confirmed",
    )
    base.update(over)
    return OrderFacts(**base)


# ── CLAUSE 2: the field label and the question, both given verbatim ────────────────

def test_the_deceased_field_is_labelled_Deceased_and_asked_in_his_words():
    """⚠️ BOTH HALVES OF ONE CLAUSE: 'Field label "Deceased" (not "For"), question
    "What is the name of the deceased?"'.

    ⚠️ AND NOTHING IN THE SHIPPED SURFACE EVER READ "For" — measured 2026-10-27, no
    label "For" exists anywhere in `backend/app` or `frontend/src`. The real change is
    "Deceased name" -> "Deceased". Recorded here rather than silently treated as done,
    because a reader checking the dispatch against the code would otherwise look for a
    label that was never there and conclude the clause was missed.
    """
    label = {f.field_id: f.label for f in schema.PLATFORM_DEFAULT_FIELDS}["deceased_name"]
    assert label == "Deceased"
    assert question_for("deceased_name") == "What is the name of the deceased?"


def test_the_question_and_the_field_come_from_ONE_walk():
    """⚠️ THE DEFECT THIS PREVENTS IS TWO WALKS DISAGREEING. The pills answer
    `next_field`; the sentence above them comes from `next_question`. If those walked
    the call order separately they could name different fields while both looked
    right, and the office would see a question about the cemetery over pills for the
    vault. Asserted across EVERY field rather than a sample.

    ⚠️ AND IT PASSES MULTI-FIELD SETS, WHICH A BREAK TEST FORCED. My first version asked
    only one field at a time — `next_question([f]) == question_for(next_field([f]))` —
    and a deliberate break replacing the shared walk with `sorted(set(missing))[0]`
    turned NOTHING red. Of course it didn't: over a one-element set every ordering
    agrees. The test was checking that two functions agree about a question with one
    possible answer.

    The disagreement only shows where CALL ORDER differs from ALPHABETICAL order, so
    the sets below are chosen to span that gap — `cemetery` sorts before
    `funeral_home` and is asked after it, `vault` sorts last and is asked third.
    """
    assert schema.CALL_ORDER, "control: an empty call order makes this vacuous"
    for field_id in schema.CALL_ORDER:
        assert next_question([field_id]) == question_for(next_field([field_id])), field_id

    # ⚠️ EVERY ADJACENT PAIR, both ways round, so the two readings must agree about
    # WHICH of two fields comes first and not merely about one field's sentence.
    order = list(schema.CALL_ORDER)
    for earlier, later in zip(order, order[1:]):
        for pair in ({earlier, later}, {later, earlier}):
            assert next_question(pair) == question_for(next_field(pair)), pair
            # and the shared walk must pick the one that is earlier in CALL ORDER
            assert next_field(pair) == earlier, (pair, next_field(pair))

    # ⚠️ A SET WHOSE CALL ORDER AND ALPHABETICAL ORDER DISAGREE, named explicitly so a
    # reader can see the gap being exercised rather than trusting the loop above.
    assert sorted({"funeral_home", "cemetery"})[0] == "cemetery"
    assert next_field({"funeral_home", "cemetery"}) == "funeral_home"


def test_nothing_missing_has_no_field_and_reads_READY():
    assert next_field(set()) is None
    assert next_field(None) is None
    assert question_for(None) == schema.READY_TO_REVIEW
    # ⚠️ THE READY STATE HAS A HINT AS OF 2026-10-27, and this asserted None. The old
    # ready line was "Ready. Press Enter to review." — it carried the instruction
    # itself. The fixes make the sentence "That's everything." with the instruction in
    # the hint and on the pill, which is the prototype's own split.
    assert hint_for(None) == schema.READY_HINT


def test_a_field_outside_the_call_order_is_still_asked():
    """⚠️ ASKED LAST AND ASKED PLAINLY, never skipped — a field nobody thought to
    prioritise is still a gap. This is the behaviour `next_question` already had; it
    has to survive the extraction of `next_field`."""
    assert next_field({"made_up_field"}) == "made_up_field"
    assert question_for("made_up_field") == "made up field?"


# ── CLAUSE 2: the urn vault makes it a cremation ───────────────────────────────────

def test_the_equipment_question_changes_wording_for_a_cremation():
    """'the equipment question offers the cremation setups from the catalog'.

    ⚠️ THE SENTENCE CHANGES, NOT ONLY THE ANSWERS. Leaving it as "What equipment?"
    over three cremation setups reads as the same question with options missing."""
    assert question_for("cemetery_equipment") == "What equipment?"
    assert question_for("cemetery_equipment", cremation=True) == CREMATION_EQUIPMENT_QUESTION
    assert hint_for("cemetery_equipment", cremation=True) == CREMATION_EQUIPMENT_HINT
    # ⚠️ AND IT CHANGES NOTHING ELSE. `cremation=True` on every other field must be
    # inert, or the flag has become a second question-selection rule.
    for field_id in schema.CALL_ORDER:
        if field_id == "cemetery_equipment":
            continue
        assert question_for(field_id, cremation=True) == question_for(field_id), field_id


def test_an_urn_is_a_cremation_and_a_burial_vault_is_not():
    assert FORM_URN_VAULT in CREMATION_FORMS
    # ⚠️ `urn` IS A CREMATION TOO. An `urn` is the urn itself and an `urn_vault` is the
    # vault it goes into; either on an order means the family chose cremation. Keeping
    # only `urn_vault` would read an urn-only order as a burial.
    assert FORM_URN in CREMATION_FORMS
    assert FORM_BURIAL_VAULT not in CREMATION_FORMS
    assert VaultForm(FORM_URN_VAULT, VIA_RECORDED_NAME).is_cremation is True
    assert VaultForm(FORM_BURIAL_VAULT, VIA_RECORDED_NAME).is_cremation is False


def test_an_unknown_vault_is_not_a_cremation_and_says_it_is_unknown():
    """⚠️ "NO VAULT YET" AND "A BURIAL VAULT" ARE DIFFERENT STATES. Defaulting an
    unnamed vault to burial would show burial equipment to somebody who has not chosen
    a vault, and the cremation chip exists precisely to mark that a kind is now
    established."""
    unknown = VaultForm(None, None)
    assert unknown.is_cremation is False
    assert unknown.is_known is False


def test_the_recorded_name_step_reads_urn_before_vault():
    """⚠️ ORDER WITHIN THE STEP, AND REVERSING IT BREAKS EVERY URN VAULT. "Monticello
    Urn Vault" contains both "urn" and "vault"; the urn test must run first or the more
    general reading wins and every urn vault reads as a burial vault."""
    assert _step_recorded_name(_key("Monticello Urn Vault")) == FORM_URN_VAULT
    assert _step_recorded_name(_key("Urn Vault - Standard")) == FORM_URN_VAULT
    assert _step_recorded_name(_key("Monticello Burial Vault")) == FORM_BURIAL_VAULT


def test_the_recorded_name_step_refuses_equipment_that_happens_to_say_vault():
    """⚠️ FOUND BY A PRODUCTION PROBE, NOT BY REVIEW. "Vault Placer" is graveside
    equipment and contains the word "vault", so the name step claimed `burial_vault`
    for it. Out of domain rather than wrong — nobody captures it as the vault — but a
    function that answers confidently about something it was not asked about hands its
    next caller a wrong answer."""
    assert _step_recorded_name(_key("Vault Placer")) is None
    assert _step_recorded_name(_key("Lowering Device & Grass")) is None
    assert _step_recorded_name(_key("Graveside Setup Service")) is None


def test_the_squeeze_ignores_the_punctuation_that_differs_between_tiers():
    """Measured spellings: the tenant writes `Urn Vault - Standard`, the platform
    writes `Universal Urn Vault (Cream & Gold)`. Comparing literally misses both."""
    assert _key("Urn Vault - Standard") == "urn vault standard"
    assert _key("Universal Urn Vault (Cream & Gold)") == "universal urn vault cream gold"
    assert _key(None) == ""
    assert _key("") == ""


# ── CLAUSE 3: the habit rule, shared with the Customer Pane ────────────────────────

def test_the_habit_rule_is_both_bars_not_either():
    """James, 2026-10-24: "at least 2 orders and at least 25%… A 1-of-10 is history,
    not a habit."

    Hand-computed, 10 orders:
      A on 4  -> 4 >= 2 and 4/10 = 40% >= 25%   KEPT
      B on 2  -> 2 >= 2 but 2/10 = 20% <  25%   dropped by the SHARE bar
      C on 1  -> 1 <  2                         dropped by the COUNT bar
    """
    assert MIN_HABIT_ORDERS == 2
    assert MIN_HABIT_SHARE == 0.25
    values = ["A"] * 4 + ["B"] * 2 + ["C"] + [None] * 3
    assert rank_habits(values, total=10) == [("A", 4)]


def test_the_habit_rule_caps_at_three():
    """Hand-computed, 8 orders, four values on 2 each = 25% each, all four qualify;
    the cap keeps three. Ties break by NAME, so the kept three are A, B, C."""
    assert MAX_HABITS == 3
    values = ["A", "A", "B", "B", "C", "C", "D", "D"]
    assert rank_habits(values, total=8) == [("A", 2), ("B", 2), ("C", 2)]


def test_the_denominator_is_the_customers_orders_not_the_recorded_ones():
    """⚠️ THE DISTINCTION THE RULING FORCES AND THE CODE COULD EASILY LOSE. A customer
    with 10 orders of which 2 name a cemetery, both the same, is 2/10 = 20% — NOT a
    habit. Counting only the recorded ones would make it 2/2 = 100% and report a habit
    off two orders, which is exactly the "1-of-10 is history" case one step along."""
    values = ["St. Mary's", "St. Mary's"] + [None] * 8
    assert rank_habits(values, total=10) == []
    # and the same two values over a 4-order customer ARE a habit: 2 >= 2, 50% >= 25%
    assert rank_habits(["St. Mary's", "St. Mary's", None, None], total=4) == [("St. Mary's", 2)]


def test_usual_first_then_the_tenants_most_ordered():
    """'Order: this customer's usual first… then the tenant's most ordered.'

    Hand-computed. This customer has 4 orders: Continental x3 (75% -> habit),
    Monticello x1 (25% share but 1 < 2 orders -> not a habit). The tenant at large has
    ordered Monticello 9 times and Venetian 5.

      usual  = [Continental]            (the only one clearing both bars)
      tail   = [Monticello(9), Venetian(5)]   by count descending
      result = Continental, Monticello, Venetian

    ⚠️ CONTINENTAL IS FIRST EVEN THOUGH MONTICELLO IS MORE POPULAR TENANT-WIDE. That
    inversion IS the ruling — if the tenant's counts won, the feature would be "most
    ordered" and the phrase "this customer's usual first" would mean nothing.
    """
    got = _habit_then_tenant(
        mine=["Continental", "Continental", "Continental", "Monticello"],
        mine_total=4,
        everyone=["Monticello"] * 9 + ["Venetian"] * 5,
    )
    assert got == ["Continental", "Monticello", "Venetian"]


def test_the_tenant_tail_is_not_habit_filtered():
    """⚠️ DELIBERATE, AND THE OPPOSITE CHOICE EMPTIES THE ROW. `rank_habits` answers
    "is this a habit of this customer" — a claim about a person. The tail answers "what
    does this licensee sell", which only has to be popular. Applying the 25% bar to a
    tenant with twenty products would leave a question with one pill on it."""
    got = _habit_then_tenant(mine=[], mine_total=0, everyone=["A"] * 3 + ["B"] + ["C"])
    # B and C are 1-of-5 = 20%, under the habit bar, and are still offered.
    assert got == ["A", "B", "C"]


def test_a_customer_with_no_history_falls_straight_to_the_tenants_counts():
    got = _habit_then_tenant(mine=[], mine_total=0, everyone=["X", "X", "Y"])
    assert got == ["X", "Y"]


def test_the_usual_one_is_not_offered_twice():
    """⚠️ WITHOUT DEDUPING, THE USUAL ANSWER TAKES TWO OF THE FOUR SLOTS. Habits and
    tenant-frequency are two rankings over the SAME population — a home's usual vault
    is usually also the tenant's most ordered — so concatenating them repeats it."""
    got = _habit_then_tenant(
        mine=["Monticello", "Monticello"], mine_total=2,
        everyone=["Monticello"] * 5 + ["Venetian"],
    )
    assert got == ["Monticello", "Venetian"]
    assert len(got) == len(set(got))


# ── CLAUSE 3: the days, and what a sub is for ──────────────────────────────────────

def test_the_day_pills_are_the_next_three_service_days_skipping_sunday():
    """The prototype's own rule: `if(d.getDay()!==0)`, starting at `i=1`.

    Hand-computed from Friday 2026-10-30:
      Sat 31 Oct, Sun 1 Nov (SKIPPED), Mon 2 Nov, Tue 3 Nov
    """
    assert DAYS_OFFERED == 3
    got = _service_days(date(2026, 10, 30))
    assert [p.value for p in got] == ["2026-10-31", "2026-11-02", "2026-11-03"]
    assert [p.label for p in got] == ["Tomorrow", "Monday", "Tuesday"]
    # ⚠️ THE DATE IS THE SUB, NOT THE LABEL. "Monday" is the answer; "Nov 2" is what
    # tells this Monday from the next one.
    assert [p.sub for p in got] == ["Oct 31", "Nov 2", "Nov 3"]


def test_tomorrow_is_named_tomorrow_only_when_it_is_tomorrow():
    """From Saturday, tomorrow is Sunday — which is skipped — so the first pill is
    Monday and must NOT be labelled "Tomorrow"."""
    got = _service_days(date(2026, 10, 31))
    assert got[0].label == "Monday", [p.label for p in got]
    assert "Tomorrow" not in [p.label for p in got]


def test_a_pill_carries_no_price_ever():
    """'answer only: no prices or descriptions'. The `sub` field exists for the three
    things the dispatch names — a town, a date, the word "cremation" — and a Pill has
    no price field at all, so a price cannot be put on one by accident."""
    assert set(Pill("v", "l").as_dict()) == {"value", "label"}
    assert set(Pill("v", "l", "s").as_dict()) == {"value", "label", "sub"}
    assert not hasattr(Pill("v", "l"), "price")


def test_at_most_four_answers_are_offered():
    """'up to 3-4 answers per question'."""
    assert MAX_PILLS == 4


# ── CLAUSE 4: what changing an answer clears ───────────────────────────────────────

def test_only_burial_equipment_is_cleared_by_an_urn_vault():
    """'urn after burial clears equipment'.

    ⚠️ EACH PACKAGE IS BURIAL-ONLY FOR A PHYSICAL REASON, not by convention: a
    lowering device lowers a casket into a grave and a vault placer sets a burial
    vault. Neither happens at a committal. Tent and chairs happen at both."""
    assert "lowering_device_only" in BURIAL_ONLY_EQUIPMENT
    assert "lowering_device_and_grass" in BURIAL_ONLY_EQUIPMENT
    assert "vault_placer" in BURIAL_ONLY_EQUIPMENT
    assert "full_equipment" in BURIAL_ONLY_EQUIPMENT
    assert "tent_only" not in BURIAL_ONLY_EQUIPMENT
    assert "extra_chairs" not in BURIAL_ONLY_EQUIPMENT
    assert "none" not in BURIAL_ONLY_EQUIPMENT


def test_every_burial_only_package_is_a_real_package():
    """⚠️ THE CONTROL THAT STOPS THIS SET ROTTING INTO A NO-OP. A typo'd slug here
    would quietly stop clearing that package, and `BURIAL_ONLY_EQUIPMENT` reading as a
    thoughtful list is exactly what would keep anyone from checking."""
    real = {value for value, _ in schema.EQUIPMENT_PACKAGES}
    assert len(real) >= 5, real  # control: an empty vocabulary makes the next line vacuous
    assert BURIAL_ONLY_EQUIPMENT, "control: an empty set is trivially a subset"
    assert BURIAL_ONLY_EQUIPMENT <= real, BURIAL_ONLY_EQUIPMENT - real


def test_the_cremation_chip_is_the_servers_word():
    """⚠️ COMPOSED SERVER-SIDE like every other label, by the standing rule that the
    pane lays out and does not phrase."""
    assert CREMATION_CHIP == "Cremation"


def test_the_chip_is_only_for_a_cremation_not_for_a_burial():
    """⚠️ THE PROTOTYPE SHOWS BOTH — `k==='urn'?'Cremation':'Burial'` — AND THE
    DISPATCH ASKS ONLY FOR THE CREMATION CHIP. A "Burial" chip on nine orders in ten is
    chrome that says what the rest of the pane already says. Asserted because the
    prototype is the other way and a later reader may "restore" it."""
    assert not hasattr(schema, "BURIAL_CHIP")


# ── the hints ──────────────────────────────────────────────────────────────────────

def test_a_hint_is_a_statement_and_the_question_is_the_question():
    """⚠️ THE ONE LINE TELLS THE DIRECTOR SOMETHING THEY CANNOT SEE — how to answer in
    words, or a fact about the answer set. Two questions stacked is two things being
    asked, and the whole 2026-10-15 ruling was that Opas asks for ONE thing.

    ⚠️ THIS ASSERTION REPLACED A VACUOUS ONE, AND THE REPLACEMENT IS THE POINT. I first
    wrote `assert hint.lower() not in question.lower()`, which cannot fail: every hint
    is longer than its question, so a longer string is never a substring of a shorter
    one. It read as a check on restatement and tested the lengths. The trailing "?" is
    a property that can actually be violated — and would be, by anyone adding a hint
    phrased as a follow-up question."""
    assert schema.CALL_HINTS, "control: an empty hint map makes this vacuous"
    for field_id, hint in schema.CALL_HINTS.items():
        question = schema.CALL_QUESTIONS.get(field_id, "")
        assert hint != question, field_id
        assert not hint.rstrip().endswith("?"), (field_id, hint)
        assert question.rstrip().endswith("?"), (field_id, question)


def test_every_hint_belongs_to_a_field_that_is_asked_about():
    """⚠️ A HINT FOR A FIELD NOBODY ASKS ABOUT CAN NEVER APPEAR. It would read as
    shipped copy and be unreachable — the same shape as the four placeholder strings
    that could not render in 2026-10-20."""
    asked = set(schema.CALL_ORDER)
    for field_id in schema.CALL_HINTS:
        assert field_id in asked, field_id


def test_a_field_with_nothing_worth_saying_has_no_hint():
    """⚠️ THE MAP IS DELIBERATELY SPARSE. A question is required, so `CALL_QUESTIONS`
    falls back to a label; a hint is not, so this returns None rather than inventing
    one."""
    assert hint_for("cemetery") is None
    assert hint_for("service_location") is None


# ── CLAUSE 3, END TO END: `pills_for` itself, against a real session ───────────────
#
# ⚠️ THE HELPERS ABOVE ARE PURE AND THE PUBLIC FUNCTION IS NOT. Testing only
# `_habit_then_tenant` and `_service_days` would leave `pills_for` — the thing every
# caller uses — unexercised, which is the "complete machinery behind an unprovisioned
# entrance" shape in miniature: correct parts, no test that they are wired together.

canonical_tenant = make_canonical_tenant_fixture()


@pytest.fixture()
def db():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def a_real_user(db):
    """⚠️ `capture_sessions.user_id` IS FK-CONSTRAINED TO `users`, so a made-up id is a
    ForeignKeyViolation rather than a harmless placeholder. Found by writing `"u1"` and
    watching it raise — which is the constraint doing its job and worth keeping as a
    reason rather than a workaround.

    ⚠️ IT READS AN EXISTING SEEDED USER rather than creating one. A user created here
    is a row to tear down, and `_tenant.py` already records what an incomplete teardown
    costs; the canonical tenant's own users are the obvious thing to borrow.
    """
    from sqlalchemy import text

    user_id = db.execute(
        text("SELECT id FROM users WHERE company_id = :t ORDER BY email LIMIT 1"),
        {"t": TESTCO_ID},
    ).scalar()
    if user_id is None:
        pytest.skip("the canonical tenant has no seeded users on this machine")
    return user_id


def _resolved(db_session, values: dict):
    """The schema as the engine resolves it, which is what `pills_for` reads.

    ⚠️ RESOLVED RATHER THAN HAND-BUILT. `ResolvedField.permitted_answers` is stamped by
    `resolve_schema` from the availability tables; a hand-made `ResolvedField` would
    carry whatever I believed it carries, and the narrowing rule this exercises is
    exactly the thing I could get wrong.
    """
    from app.services.capture import template_for, SALES_ORDER
    from app.services.capture.schema import resolve_schema
    from app.services.personalization.enrollment import resolve_availability_config

    return resolve_schema(
        vault_product_id=None,
        personalization_config=resolve_availability_config(db_session, TESTCO_ID),
        platform_fields=template_for(SALES_ORDER),
        answers=values,
    )


def test_pills_for_a_free_text_field_is_EMPTY_not_invented(db, canonical_tenant):
    """⚠️ AN EMPTY TUPLE IS A REAL ANSWER AND MEANS "TYPE IT". A family name is not
    pickable from a list, and the prototype marks those questions `free:true` rather
    than inventing options. The caller renders the hint instead of a row of pills."""
    from app.services.capture.pills import pills_for

    values: dict = {}
    for field_id in ("deceased_name", "date_of_birth", "grave_location"):
        got = pills_for(
            db, tenant_id=TESTCO_ID, field_id=field_id, values=values,
            resolved_fields=_resolved(db, values), today=date(2026, 10, 27), facts=[],
        )
        assert got == (), (field_id, got)


def test_pills_for_the_day_need_no_history(db, canonical_tenant):
    """⚠️ THE DAYS ARE THE ONE FIELD WHOSE ANSWERS ARE NOT COUNTED FROM ANYTHING, which
    is why `pills_for` returns them before it reads a single order. A tenant on its
    first ever order still gets three days."""
    from app.services.capture.pills import pills_for

    got = pills_for(
        db, tenant_id=TESTCO_ID, field_id="service_date", values={},
        resolved_fields=_resolved(db, {}), today=date(2026, 10, 30), facts=[],
    )
    assert [p.value for p in got] == ["2026-10-31", "2026-11-02", "2026-11-03"]


def test_pills_never_exceed_the_cap_on_any_field(db, canonical_tenant):
    """⚠️ ASSERTED OVER EVERY FIELD RATHER THAN THE ONE I HAPPENED TO BUILD. The cap is
    applied per-branch inside `pills_for` — six separate `[:MAX_PILLS]` slices — so a
    branch added later without one would be invisible to a test that checked the vault.

    ⚠️ AND THE FIXTURE IS DELIBERATELY WIDER THAN THE CAP. Seven distinct vaults and
    five cemeteries across twelve orders; a fixture with four of each would satisfy the
    cap without exercising it.
    """
    from app.services.capture.pills import pills_for

    facts = [
        order(vault=f"Vault {i}", cemetery=f"Cem {i}", funeral_home="Hopkins",
              service_time=time(10, 0), cemetery_city="Auburn")
        for i in range(7)
    ] + [
        order(vault="Monticello", cemetery="St. Mary's", funeral_home="Hopkins",
              service_time=time(13, 0), cemetery_city="Skaneateles")
        for _ in range(5)
    ]
    values = {"funeral_home": "Hopkins"}
    resolved = _resolved(db, values)
    for field_id in schema.CALL_ORDER:
        got = pills_for(
            db, tenant_id=TESTCO_ID, field_id=field_id, values=values,
            resolved_fields=resolved, today=date(2026, 10, 27), facts=facts,
        )
        assert len(got) <= MAX_PILLS, (field_id, [p.label for p in got])


def test_the_cemetery_pill_carries_its_town_because_names_are_shared(db, canonical_tenant):
    """'towns on funeral homes and cemeteries'.

    ⚠️ THIS IS THE SAME FACT THE CEMETERY PANE'S "not the St. Mary's in Auburn" LINK
    EXISTS FOR. Two cemeteries genuinely share a name across towns, so a bare
    "St. Mary's" pill would be two different answers wearing one label.
    """
    from app.services.capture.pills import pills_for

    facts = [
        order(cemetery="St. Mary's Cemetery", cemetery_city="Skaneateles",
              funeral_home="Hopkins")
        for _ in range(4)
    ]
    values = {"funeral_home": "Hopkins"}
    got = pills_for(
        db, tenant_id=TESTCO_ID, field_id="cemetery", values=values,
        resolved_fields=_resolved(db, values), today=date(2026, 10, 27), facts=facts,
    )
    mine = [p for p in got if p.value == "St. Mary's Cemetery"]
    assert mine, [p.label for p in got]
    assert mine[0].sub == "Skaneateles"


def test_a_time_pill_is_written_the_way_the_office_says_it(db, canonical_tenant):
    """⚠️ NOT `13:00`. The standing rule since 2026-10-12 is that stored forms never
    reach a screen — the Service row showed `2027-03-02` and `funeral_home` raw, and
    both were ruled defects. A pill is not a row, so it carries its own one line for
    this rather than reaching into the row renderer's row-shaped API."""
    from app.services.capture.pills import pills_for

    facts = [order(service_time=time(13, 0), funeral_home="Hopkins") for _ in range(4)]
    values = {"funeral_home": "Hopkins"}
    got = pills_for(
        db, tenant_id=TESTCO_ID, field_id="service_time", values=values,
        resolved_fields=_resolved(db, values), today=date(2026, 10, 27), facts=facts,
    )
    assert [p.label for p in got] == ["1:00 PM"], [p.label for p in got]
    # ⚠️ THE STORED VALUE IS STILL THE STORED FORM. The label is for the eye; the value
    # is what `resolutions` records, and writing "1:00 PM" there would feed an unparsed
    # string into the extractor on the next read.
    assert [p.value for p in got] == ["13:00"]


def test_a_vault_pill_must_actually_BE_a_vault(db, canonical_tenant):
    """⚠️ FOUND BY A PRODUCTION PROBE, NOT BY A TEST, AND JAMES WOULD HAVE SEEN IT.
    The catalogue fallback matched `lower(name) LIKE '%vault%'`, which is true of
    "Vault Placer" — a piece of graveside equipment — so it was offered at ⌥4 under
    "Which vault?" on sunnycrest.

    ⚠️ THE FIX IS A FORM TEST, NOT A NAME TEST, which is the whole reason `VAULT_FORMS`
    exists: a "Graveliner" is the right answer to "which vault" and does not contain
    the word, while a "Vault Placer" contains it and is not.
    """
    from app.services.capture.vault_form import (
        FORM_BURIAL_VAULT,
        FORM_EQUIPMENT,
        FORM_GRAVE_LINER,
        FORM_URN,
        FORM_URN_VAULT,
        VAULT_FORMS,
    )

    assert FORM_BURIAL_VAULT in VAULT_FORMS
    assert FORM_URN_VAULT in VAULT_FORMS
    # ⚠️ A GRAVELINER IS A VAULT ANSWER DESPITE NOT SAYING SO, which is the case a name
    # test gets wrong in the other direction.
    assert FORM_GRAVE_LINER in VAULT_FORMS
    # ⚠️ AND EQUIPMENT IS NOT, which is the defect this closes.
    assert FORM_EQUIPMENT not in VAULT_FORMS
    # ⚠️ AN URN IS WHAT THE ASHES GO IN; AN URN VAULT IS WHAT THE URN GOES IN. The
    # field asks for the second, so a tenant selling both must not see eight urns here.
    assert FORM_URN not in VAULT_FORMS


def test_the_equipment_pills_are_only_what_the_tenant_can_BILL(db, canonical_tenant):
    """⚠️ A PACKAGE WITHOUT A PRODUCT IS NOT AN ANSWER. `approval.EQUIPMENT_PRODUCT_NAMES`
    maps each package to the product name a tenant must carry, `_product_by_exact_name`
    is exact, and `assess` reports a blocker when it is absent. Offering it anyway is
    the shape of the door offering an edit it could not perform (2026-10-26).

    ⚠️ AND "None" IS ALWAYS OFFERABLE, because declining equipment needs no product.
    Without it a tenant carrying no equipment products would get an equipment question
    with no answers at all.
    """
    from app.services.capture.pills import _tenant_equipment
    from app.services.personalization.questions import ANSWER_NONE

    allowed = _tenant_equipment(db, TESTCO_ID)
    assert ANSWER_NONE in allowed
    # ⚠️ THE CONTROL: every allowed slug must be a real package, or this set has
    # silently become "anything" and the assertion above means nothing.
    real = {value for value, _ in schema.EQUIPMENT_PACKAGES}
    assert allowed <= real, allowed - real


# ── CLAUSE 4, END TO END: answering, and what the answer clears ────────────────────
#
# ⚠️ WITHOUT THESE, `session_service.answer` AND THE `/answer` ROUTE ARE MACHINERY
# NOTHING HAS EVER CALLED — CLAUDE.md §11's "complete machinery behind an unprovisioned
# entrance", which is invisible to review (the code reads correctly) and invisible to a
# suite that only tests the pieces.
#
# ⚠️ AND THE LINE PATH'S CLEARING HAD A REAL BUG THAT ONLY RE-READING FOUND: the keys
# that went were computed as a symmetric difference of `row.resolutions` against the
# dict it had just been assigned — always empty. The note said something was cleared
# and nothing was. Fixed, and `test_the_clearing_reports_the_keys_it_removed` is why it
# cannot come back silently.

def test_answering_a_field_records_a_RESOLUTION_not_a_value(db, a_real_user, canonical_tenant):
    """⚠️ A RESOLUTION, BECAUSE A VALUE WOULD BE ERASED BY THE NEXT KEYSTROKE. Under
    whole-text capture `values` is rebuilt from the text on every read, so a pill's
    answer has to be the director's decision ABOUT the text rather than a reading of
    it. Exactly the reasoning `choose` records."""
    from app.services.capture import session_service

    row = session_service.start(db, company_id=TESTCO_ID, user_id=a_real_user)
    session_service.set_text(
        db, row.id, company_id=TESTCO_ID, user_id=a_real_user,
        text="order for hopkins thursday 10am",
    )
    updated, note = session_service.answer(
        db, row.id, company_id=TESTCO_ID, user_id=a_real_user,
        field_id="service_location", value="graveside",
    )
    assert (updated.resolutions or {}).get("service_location") == "graveside"
    assert note is None  # nothing to clear — the control for the next test
    db.rollback()


def test_answering_an_unknown_field_is_REFUSED_not_stored(db, a_real_user, canonical_tenant):
    """⚠️ `resolutions` IS READ BY `extract_text` ON EVERY RE-READ, so a key nothing
    consumes would sit there permanently, invisible and inert — and would look like a
    stored answer to anyone reading the row."""
    from app.services.capture import session_service

    row = session_service.start(db, company_id=TESTCO_ID, user_id=a_real_user)
    with pytest.raises(ValueError):
        session_service.answer(
            db, row.id, company_id=TESTCO_ID, user_id=a_real_user,
            field_id="favourite_colour", value="blue",
        )
    db.rollback()


def test_the_clearing_reports_the_keys_it_removed(db, canonical_tenant):
    """⚠️ THE UNIT UNDER TEST IS THE RULE, AND THE ARITHMETIC IS HAND-DONE.

    Burial vault + Full Equipment -> nothing clears: the equipment still fits.
    Urn vault   + Full Equipment -> the equipment goes, because a lowering device
                                    lowers a casket into a grave and that does not
                                    happen at a committal.
    """
    from app.services.capture.clears import clear_what_no_longer_fits

    # ⚠️ A REAL URN VAULT NAME, so `form_of` answers from the catalogue rather than
    # from a fixture I invented. `Monticello Urn Vault` is one of the platform's six.
    after, note = clear_what_no_longer_fits(
        db, company_id=TESTCO_ID,
        resolutions={"vault": "Monticello Urn Vault", "cemetery_equipment": "full_equipment"},
        changed_field="vault",
    )
    assert "cemetery_equipment" not in after, after
    assert note is not None
    # ⚠️ THE NOTE NAMES THE PACKAGE THE WAY THE OFFICE READS IT, never by its id. A
    # note saying "full_equipment cleared" is the `funeral_home`-raw defect in a
    # sentence (ruled 2026-10-12).
    assert "Full Equipment" in note
    assert "full_equipment" not in note
    assert "cremation setup" in note


def test_a_burial_to_burial_change_clears_NOTHING(db, canonical_tenant):
    """⚠️ THE CASE THE OBVIOUS IMPLEMENTATION GETS WRONG. Clearing on every vault
    change would make the office re-answer a question whose answer did not become
    wrong — Monticello to Continental are both burial vaults and the lowering device
    still applies."""
    from app.services.capture.clears import clear_what_no_longer_fits

    after, note = clear_what_no_longer_fits(
        db, company_id=TESTCO_ID,
        resolutions={"vault": "Continental Burial Vault",
                     "cemetery_equipment": "full_equipment"},
        changed_field="vault",
    )
    assert after.get("cemetery_equipment") == "full_equipment"
    assert note is None


def test_changing_something_OTHER_than_the_vault_clears_nothing(db, canonical_tenant):
    """⚠️ THE GUARD IS ON THE FIELD THAT CHANGED, not on the state of the order.
    Answering the cemetery must not re-examine the equipment — a rule that ran on every
    answer would clear the equipment the moment somebody picked an urn vault AND THEN
    answered anything else, long after the note explaining it had gone."""
    from app.services.capture.clears import clear_what_no_longer_fits

    after, note = clear_what_no_longer_fits(
        db, company_id=TESTCO_ID,
        resolutions={"vault": "Monticello Urn Vault",
                     "cemetery_equipment": "full_equipment",
                     "cemetery": "St. Mary's Cemetery"},
        changed_field="cemetery",
    )
    assert after.get("cemetery_equipment") == "full_equipment"
    assert note is None


def test_an_equipment_answer_that_fits_a_cremation_SURVIVES_the_change(db, canonical_tenant):
    """⚠️ "Tent Only" IS NOT BURIAL-ONLY. A tent goes up at a committal too, so
    clearing it would be clearing an answer that is still correct — which is the same
    cost as not clearing a wrong one, paid in the office's time."""
    from app.services.capture.clears import clear_what_no_longer_fits

    after, note = clear_what_no_longer_fits(
        db, company_id=TESTCO_ID,
        resolutions={"vault": "Monticello Urn Vault", "cemetery_equipment": "tent_only"},
        changed_field="vault",
    )
    assert after.get("cemetery_equipment") == "tent_only"
    assert note is None


# ── CLAUSE 4's SECOND HALF, WHICH I SHIPPED BROKEN AND REPORTED AS WORKING ────────
#
# ⚠️ FOUR GREEN TESTS COVERED CLAUSE 4 AND ALL FOUR TESTED THE URN/EQUIPMENT HALF.
# "a vault without that personalization clears it" had no test at all, and the
# implementation could not run: it imported `resolve_availability_config` from
# `personalization.availability` (it lives in `personalization.enrollment`) AND called
# `resolve_schema(db, company_id=..., values=...)` against a keyword-only signature
# that takes none of those three. ImportError, then TypeError — and a bare
# `except Exception` swallowed both, so the rule was a permanent silent no-op.
#
# ⚠️ IT WAS FOUND BY A PRODUCTION RETEST PROBE THAT HAPPENED TO COPY THE SAME BAD
# IMPORT, NOT BY ANY TEST. The 48-break harness could not have caught it either:
# breaking a path that no test exercises turns nothing red. The gap was the absent
# test, and a break test cannot find an absence.


def _variant_of(db, name: str) -> str | None:
    """The variant id the CATALOGUE gives this name — never a literal.

    ⚠️ DERIVED, NOT HARDCODED, because availability is keyed by variant_template_id and
    a UUID pasted from one database is a fixture that silently tests nothing anywhere
    else. This is also the line that measures the real limitation: on testco only 2 of
    25 products resolve to a variant at all.
    """
    from app.services.product_name_resolver import build_index
    from app.services.product_name_resolver import resolve as resolve_vault

    return getattr(resolve_vault(build_index(db), name), "variant_template_id", None)


# ⚠️ A VAULT THAT RESOLVES, CHOSEN BY MEASUREMENT. `Wilbert Bronze` is one of the two
# testco products that reach a variant id, and its form is `burial_vault`, which is one
# of the two forms `AvailabilityOffered` accepts for the personalization question.
_RESOLVING_VAULT = "Wilbert Bronze"


def test_the_personalization_clear_REACHES_resolve_schema(db, canonical_tenant, monkeypatch):
    """⚠️ THE TEST WHOSE ABSENCE HID TWO DEFECTS. It asserts only that the branch RUNS —
    no clearing, no note — because running is exactly what was broken, and because an
    assertion about the outcome would have been satisfied by the swallowed no-op.

    The guard is on the KEYWORD NAMES. `resolve_schema` is keyword-only, so the old
    call's `db`/`company_id`/`values` could never bind; pinning the accepted names here
    means a future edit that reintroduces them fails on this test rather than
    disappearing into an except clause.
    """
    from app.services.capture import clears

    seen: list[dict] = []
    real = clears.resolve_schema

    def recording(**kwargs):
        seen.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(clears, "resolve_schema", recording)

    clears.clear_what_no_longer_fits(
        db, company_id=TESTCO_ID,
        resolutions={"vault": _RESOLVING_VAULT, "personalization": "legacy_print"},
        changed_field="vault",
    )

    # ⚠️ NON-ZERO IS THE WHOLE POINT. "No exception raised" was TRUE for the entire
    # period the rule did nothing, because the exception was caught. A call count is
    # the one reading the broken version could not produce.
    assert len(seen) == 1, f"the personalization branch did not run: {seen}"
    assert set(seen[0]) == {
        "vault_product_id", "personalization_config", "vault_form",
        "platform_fields", "answers",
    }, seen[0]


def test_a_vault_that_does_not_offer_the_personalization_CLEARS_it(
    db, canonical_tenant, monkeypatch
):
    """James's clause 4: "a vault without that personalization clears it."

    ⚠️ THE AVAILABILITY READ IS THE ONLY DOUBLE, AND IT HAS TO BE. Measured against
    testco: 4 variants narrow personalization, 25 products exist, and NO product
    resolves to a narrowing variant — so the positive case cannot be built from seeded
    data at all. The resolver, `resolve_schema`, the applies_when conditions, the
    permitted-answer narrowing and the label lookup are all real; only the licensee's
    config is crafted.
    """
    from app.services.capture import clears

    variant = _variant_of(db, _RESOLVING_VAULT)
    assert variant, "control: this vault must resolve, or the test proves nothing"

    monkeypatch.setattr(
        clears, "resolve_availability_config",
        lambda _db, _cid: {"availability": {variant: {"personalization": ["nameplate_only"]}}},
    )

    after, note = clears.clear_what_no_longer_fits(
        db, company_id=TESTCO_ID,
        resolutions={"vault": _RESOLVING_VAULT, "personalization": "legacy_print"},
        changed_field="vault",
    )

    assert "personalization" not in after, after
    assert note is not None
    # ⚠️ THE LABEL, NOT THE ID — the same ruling the equipment note is held to.
    assert "Legacy Series" in note, note
    assert "legacy_print" not in note, note


def test_a_vault_that_DOES_offer_the_personalization_keeps_it(
    db, canonical_tenant, monkeypatch
):
    """⚠️ THE DISCRIMINATOR. Without this, the test above passes against an
    implementation that clears personalization on every vault change — which is the
    equipment rule's own worked mistake, one field over."""
    from app.services.capture import clears

    variant = _variant_of(db, _RESOLVING_VAULT)
    monkeypatch.setattr(
        clears, "resolve_availability_config",
        lambda _db, _cid: {"availability": {variant: {"personalization": ["legacy_print", "nameplate_only"]}}},
    )

    after, note = clears.clear_what_no_longer_fits(
        db, company_id=TESTCO_ID,
        resolutions={"vault": _RESOLVING_VAULT, "personalization": "legacy_print"},
        changed_field="vault",
    )

    assert after.get("personalization") == "legacy_print"
    assert note is None


def test_a_PROGRAMMING_error_in_the_availability_read_is_NOT_swallowed(
    db, canonical_tenant, monkeypatch
):
    """⚠️ THIS PINS THE STRUCTURAL FIX, which matters more than the two defects it
    caught. The except clause was `except Exception`, so a wrong module name and a
    wrong call signature both read as "this tenant has no availability config" —
    indistinguishable, at runtime, from the condition it was written for.
    """
    from app.services.capture import clears

    def boom(_db, _cid):
        raise TypeError("wrong signature, the exact class that hid for a whole slice")

    monkeypatch.setattr(clears, "resolve_availability_config", boom)

    with pytest.raises(TypeError):
        clears.clear_what_no_longer_fits(
            db, company_id=TESTCO_ID,
            resolutions={"vault": _RESOLVING_VAULT, "personalization": "legacy_print"},
            changed_field="vault",
        )


def test_a_DATABASE_error_in_the_availability_read_FAILS_OPEN(
    db, canonical_tenant, monkeypatch
):
    """⚠️ AND THE OTHER SIDE OF THE SAME NARROWING, or the fix above would be a
    regression rather than a repair. An unreachable config table must not delete the
    director's answers — that was the except clause's real purpose, and it still holds.
    """
    from sqlalchemy.exc import OperationalError

    from app.services.capture import clears

    def db_down(_db, _cid):
        raise OperationalError("SELECT 1", {}, Exception("connection reset"))

    monkeypatch.setattr(clears, "resolve_availability_config", db_down)

    after, note = clears.clear_what_no_longer_fits(
        db, company_id=TESTCO_ID,
        resolutions={"vault": _RESOLVING_VAULT, "personalization": "legacy_print"},
        changed_field="vault",
    )
    assert after.get("personalization") == "legacy_print"
    assert note is None


# ── CLAUSE 2's THREE FOLLOW-UP CHAINS ──────────────────────────────────────────────
#
# ⚠️ ALL THREE ALREADY WORKED, ON CONDITIONS THAT PREDATE THIS SLICE, and that is
# exactly why they are tested here rather than taken on trust. The dispatch names them
# as behaviour it expects — "A personalizable vault asks personalization next (only the
# options that vault offers); Legacy asks which print; any personalization asks dates"
# — and "it already works" is a claim about the engine that nothing in this slice
# would have noticed going false.

def _offers(answers_per_question: dict) -> dict:
    """A licensee's availability config for variant `v1`, in the shape the reader wants.

    ⚠️ THE `"availability"` WRAPPER IS LOAD-BEARING AND I LEFT IT OUT FIRST. Two tests
    failed, and measuring `read_availability` is what found it:

        {"v1": {"personalization": ["nameplate_only"]}}                 NOT_CONFIGURED
        {"availability": {"v1": {"personalization": ["nameplate_only"]}}}      OFFERED

    A bare map reads as "nothing has been said about this vault", so a fixture missing
    the wrapper silently tests the unconfigured path while claiming to test the
    configured one. Exactly the fixture-from-assumption shape — I wrote the shape I
    expected rather than the one `AVAILABILITY_KEY` names.
    """
    return {"availability": {"v1": dict(answers_per_question)}}


def _resolved_with(answers: dict, *, availability: dict | None = None):
    from app.services.capture import template_for, SALES_ORDER
    from app.services.capture.schema import resolve_schema

    return resolve_schema(
        vault_product_id="v1",
        personalization_config=availability,
        platform_fields=template_for(SALES_ORDER),
        answers=answers,
    )


def _ids(resolved) -> set[str]:
    return {f.definition.field_id for f in resolved}


def test_a_vault_offering_no_personalization_does_not_ASK_about_it():
    """'A personalizable vault asks personalization next' — and one that is not,
    does not. ⚠️ THE NEGATIVE IS THE HALF THAT MATTERS: a Monticello order at a
    licensee offering no personalization on the Monticello must not report
    personalization as missing, which `missing.py` already records as a ruling."""
    # ⚠️ AN EMPTY LIST, NOT AN ABSENT KEY, AND THE DIFFERENCE IS A RULING. The
    # enrollment resolver's own docstring: "`[]` is NOT_OFFERED — the licensee saying
    # 'none on this vault'", while an absent key is NOT_CONFIGURED, which means "ask,
    # nothing constrains the answer yet". My first fixture used `{}` and the field was
    # correctly still asked about; the test was wrong, not the engine.
    offers_nothing = _offers({"personalization": []})
    assert "personalization" not in _ids(_resolved_with({}, availability=offers_nothing))
    # ⚠️ THE CONTROL: with nothing said at all, it IS asked. Without this the assertion
    # above would pass against an engine that never asks about personalization.
    assert "personalization" in _ids(_resolved_with({}, availability=None))


def test_only_the_options_THAT_VAULT_OFFERS_become_pills():
    """'(only the options that vault offers)'.

    ⚠️ THE NARROWING IS THE CATALOGUE'S, READ OFF `permitted_answers`, not a rule in
    the pills. A vault permitting only a nameplate must not offer a Legacy print, and
    hard-coding which vaults take what would be a second catalogue.
    """
    from app.services.capture.pills import _enum_pills

    offers_one = _offers({"personalization": ["nameplate_only"]})
    resolved = _resolved_with({}, availability=offers_one)
    field = next(f for f in resolved if f.definition.field_id == "personalization")
    assert field.permitted_answers, "control: no narrowing means this proves nothing"

    pills = _enum_pills(field, mine=[], mine_total=0, everyone=[], allowed=None)
    values = [p.value for p in pills]
    assert "nameplate_only" in values
    # ⚠️ THE OPTION THE VAULT DOES NOT OFFER IS ABSENT, which is the assertion. The
    # field's own `options` tuple holds seven answers; the catalogue permits one.
    assert "legacy_print" not in values, values
    # ⚠️ AND "None" SURVIVES THE NARROWING, deliberately — declining personalization is
    # always available, whatever the vault physically takes.
    assert ANSWER_NONE in values
    # ⚠️ AND IT IS LAST, WHICH A BREAK TEST FORCED ME TO ASSERT. Removing the rule that
    # keeps it out of the ranking turned NOTHING red: I had only checked that it was
    # PRESENT. "None" is the most-chosen answer on plenty of tenants, so ranking it by
    # frequency puts "No personalization" first on a question about personalization —
    # technically the usual answer, and a worse question.
    assert values[-1] == ANSWER_NONE, values


def test_None_stays_last_even_when_it_is_the_MOST_chosen_answer():
    """⚠️ THIS TEST EXISTS BECAUSE THE PREVIOUS ONE COULD NOT SEE THE RULE. Removing
    the guard that keeps "None" out of the ranking turned nothing red there — with no
    order history the ranking is empty, so the ordering falls through to the options
    tuple, where `none` is last anyway. The assertion was true for a reason unrelated
    to the rule it named: CLAUDE.md §11 shape 6, a check passing for a reason unrelated
    to what it claims.

    So the fixture has to make "None" the most frequent answer, which it is on plenty
    of real tenants — and that is the whole point of the rule. Hand-computed: 9 orders
    declined personalization, 2 took a nameplate; by frequency "None" ranks FIRST, and
    it must still render LAST.
    """
    from app.services.capture.pills import _enum_pills

    offers_one = _offers({"personalization": ["nameplate_only"]})
    resolved = _resolved_with({}, availability=offers_one)
    field = next(f for f in resolved if f.definition.field_id == "personalization")

    pills = _enum_pills(
        field,
        mine=[], mine_total=0,
        everyone=[ANSWER_NONE] * 9 + ["nameplate_only"] * 2,
        allowed=None,
    )
    values = [p.value for p in pills]
    assert values[-1] == ANSWER_NONE, values
    assert values[0] == "nameplate_only", values


def test_an_empty_permitted_set_narrows_NOTHING():
    """⚠️ THE DISTINCTION THAT WOULD HIDE PERSONALIZATION ON MOST LICENSEES. The
    field's own docstring says empty means *"any answer the question defines is
    acceptable"* — reading it as a filter would empty the row on every tenant whose
    availability is not configured, which is most of them."""
    from app.services.capture.pills import _enum_pills

    resolved = _resolved_with({}, availability=None)
    field = next(
        (f for f in resolved if f.definition.field_id == "service_location"), None
    )
    assert field is not None
    assert not field.permitted_answers  # a plain field, no narrowing
    pills = _enum_pills(field, mine=[], mine_total=0, everyone=[], allowed=None)
    assert len(pills) == len(field.definition.options), [p.value for p in pills]


def test_choosing_Legacy_asks_which_print():
    """'Legacy asks which print'.

    ⚠️ THE ENGINE'S CHAIN IS ONE STEP LONGER THAN THE PROTOTYPE'S, AND THAT IS NOT A
    DEVIATION TO FIX. The prototype goes Legacy -> which print. Here it is
    `personalization=legacy_print` -> `legacy_series` -> (if `standard`)
    `legacy_print_name`, because a Legacy CUSTOM order has no poster print to name.
    Both steps are reached by choosing Legacy, which is what the clause asks for.
    """
    offers_legacy = _offers({"personalization": ["legacy_print"]})
    before = _ids(_resolved_with({}, availability=offers_legacy))
    assert "legacy_series" not in before, "control: it must not be asked unprompted"

    picked = _ids(_resolved_with({"personalization": "legacy_print"},
                                 availability=offers_legacy))
    assert "legacy_series" in picked

    standard = _ids(_resolved_with(
        {"personalization": "legacy_print", "legacy_series": "standard"},
        availability=offers_legacy,
    ))
    assert "legacy_print_name" in standard

    # ⚠️ AND CUSTOM ARTWORK DOES NOT ASK FOR A POSTER PRINT, which is the case the
    # extra step exists for.
    custom = _ids(_resolved_with(
        {"personalization": "legacy_print", "legacy_series": "custom"},
        availability=offers_legacy,
    ))
    assert "legacy_print_name" not in custom


def test_ANY_personalization_asks_the_dates_and_none_does_not():
    """'any personalization asks dates'.

    ⚠️ IT IS `required_when`, NOT `applies_when`, AND THE DIFFERENCE IS VISIBLE. The
    dates are always SHOWN and become a GAP only once personalization is chosen —
    `FieldDefinition`'s own docstring names this as the case that needs both slots. So
    the assertion is about `missing`, not about membership.
    """
    from app.services.capture import evaluate, template_for, SALES_ORDER

    offers = _offers({"personalization": ["nameplate_only"]})

    def missing(answers: dict) -> set[str]:
        return set(evaluate(
            answers, vault_product_id="v1", personalization_config=offers,
            platform_fields=template_for(SALES_ORDER),
        ).missing)

    assert "date_of_birth" not in missing({}), "control: not a gap before a choice"
    chosen = missing({"personalization": "nameplate_only"})
    assert "date_of_birth" in chosen
    assert "date_of_death" in chosen
    # ⚠️ AND DECLINING IT ASKS FOR NOTHING. "none" is an ANSWER — it clears the
    # requirement rather than leaving it open.
    assert "date_of_birth" not in missing({"personalization": ANSWER_NONE})


# ── THE 2026-10-27 FIXES ───────────────────────────────────────────────────────────

def test_the_guided_walk_REACHES_the_equipment_question():
    """⚠️ THE DEFECT I SHIPPED AND REPORTED AS WORKING. `next_field(missing)` walks
    required-and-unanswered, and `cemetery_equipment` is `required_when=Never()` — so
    the equipment question was never asked, and "the equipment question offers the
    cremation setups from the catalog" was unreachable through the flow. I had verified
    it by calling `pills_for` on that field directly, which tests the pills and not
    whether the walk gets there.

    ⚠️ ASSERTED BY WALKING A WHOLE ORDER, not by inspecting the function. The defect was
    invisible to reading: every piece was correct.
    """
    from app.services.capture import evaluate, template_for, SALES_ORDER
    from app.services.capture.schema import guided_field

    tmpl = template_for(SALES_ORDER)
    answers: dict = {}
    asked: list[str] = []
    for _ in range(40):
        st = evaluate(answers, vault_product_id=None, personalization_config=None,
                      platform_fields=tmpl)
        f = guided_field(st)
        if f is None:
            break
        asked.append(f)
        answers[f] = "church" if f == "service_location" else "x"
    assert "cemetery_equipment" in asked, asked
    # ⚠️ THE CONTROL: the required ones must still be asked, and FIRST. A walk that
    # reached equipment by asking everything in schema order would satisfy the line
    # above and bury the cemetery behind the chairs.
    assert asked[:3] == ["funeral_home", "deceased_name", "vault"], asked
    assert asked.index("cemetery") < asked.index("cemetery_equipment"), asked


def test_the_guided_walk_NEVER_asks_the_burial_date():
    """⚠️ RULED AWAY 2026-10-13: "the burial is always the same day as the service. When
    it isn't, it is a graveside service." The field is kept and still extracted so a
    contradictory date becomes a visible conflict, and it is DERIVED at approve.

    ⚠️ MY FIRST `guided_field` ASKED IT. It ended `return sorted(optional)[0]` as a
    fallback — right for a REQUIRED field absent from `CALL_ORDER` ("still a gap"),
    wrong for an optional one, where absence from `CALL_ORDER` means nobody wants it
    asked. The walk printed "Burial date?" and reinstated a question the ruling removed.
    """
    from app.services.capture import evaluate, template_for, SALES_ORDER
    from app.services.capture.schema import guided_field, CALL_ORDER

    assert "burial_date" not in CALL_ORDER, "the premise: it is absent on purpose"
    tmpl = template_for(SALES_ORDER)
    answers: dict = {}
    for _ in range(40):
        st = evaluate(answers, vault_product_id=None, personalization_config=None,
                      platform_fields=tmpl)
        f = guided_field(st)
        if f is None:
            break
        assert f != "burial_date", "the ruling says this is never asked"
        answers[f] = "church" if f == "service_location" else "x"


def test_required_questions_come_before_optional_ones():
    """⚠️ NOT THE PROTOTYPE'S RULE, AND THE RIGHT ONE HERE. Its `nextField` walks
    `ORDER` and its model has no optional fields, so the distinction never arose. A
    director who has not named the cemetery should be asked for the cemetery before
    being asked about chairs — and `CALL_ORDER` alone would interleave them, because
    `cemetery_equipment` sits above `personalization` in it."""
    from app.services.capture.schema import guided_field

    class FakeState:
        missing = ("personalization",)
        unanswered_optional = ("cemetery_equipment",)

    # `cemetery_equipment` is EARLIER in CALL_ORDER than `personalization`, so a single
    # walk over CALL_ORDER would return it. Required wins.
    from app.services.capture.schema import CALL_ORDER
    assert CALL_ORDER.index("cemetery_equipment") < CALL_ORDER.index("personalization")
    assert guided_field(FakeState()) == "personalization"


def test_the_ready_line_is_his_words_and_carries_no_instruction():
    """James, 2026-10-27: "Opas says 'That's everything.' with a Review pill (⌥1) and
    Enter". ⚠️ THE OLD WORDING WAS ALSO HIS — "Ready. Press Enter to review." — and it
    was the line beside a Complete order BUTTON. With the pill carrying "Enter", a
    sentence that also says it says it twice."""
    from app.services.capture.schema import READY_TO_REVIEW, READY_HINT, question_for

    assert READY_TO_REVIEW == "That’s everything."
    assert question_for(None) == READY_TO_REVIEW
    assert "Enter" not in READY_TO_REVIEW
    # the instruction moved to the hint, which is the prototype's own split
    assert READY_HINT == "Press Enter to review, or click any line to change it."


def test_the_capture_surface_is_one_row_per_question_in_call_order():
    """'a two-column row per question in call order'.

    ⚠️ EVERY QUESTION FIELD MUST BE SOURCED BY SOME ROW, or a captured value is
    invisible — the 2026-10-12 ruling. Asserted over `CALL_ORDER` rather than over a
    list I typed here, so adding a question without a row fails this.
    """
    from app.services.capture.rows import row_field_ids
    from app.services.capture.surfaces import CAPTURE_SALES_ORDER as S
    from app.services.capture.schema import CALL_ORDER

    covered: set[str] = set()
    for row in S.rows:
        covered |= set(row_field_ids(row))
    assert not [f for f in CALL_ORDER if f not in covered], \
        [f for f in CALL_ORDER if f not in covered]

    # ⚠️ THE ROW ORDER FOLLOWS `CALL_ORDER`, which is the dispatch's stated authority
    # even though its parenthetical list is the prototype's order. Checked as a
    # relative ordering over the fields each row sources, because one row can source
    # several.
    order = {f: i for i, f in enumerate(CALL_ORDER)}
    firsts = [
        min((order[f] for f in row_field_ids(row) if f in order), default=10 ** 6)
        for row in sorted(S.rows, key=lambda r: r.order)
    ]
    assert firsts == sorted(firsts), firsts


def test_the_labels_are_the_prototypes():
    from app.services.capture.surfaces import CAPTURE_SALES_ORDER as S

    labels = {r.id: r.label for r in S.rows}
    assert labels["deceased_name"] == "Deceased"      # never "Deceased name"
    assert labels["vault"] == "Vault"                 # never "Vault / Product"
    assert labels["cemetery_equipment"] == "Equipment"
    assert labels["service_date"] == "Service day"
    assert labels["service_time"] == "Time"
    assert labels["service"] == "Service"
    # ⚠️ AND NOTHING READS "Deceased Name" ANYWHERE ON THIS SURFACE.
    assert all("Deceased name" != l and "Deceased Name" != l for l in labels.values())


def test_every_row_can_be_clicked_to_ask_its_question_again():
    """'clicking a row asks that question again' — so every row must name a field.

    ⚠️ AND THE TARGET MUST BE A QUESTION, not just any field the row sources. The
    Cemetery row sources the name, the town and the ETA; its target is `cemetery`, so a
    click asks "Which cemetery?" rather than "Which town is the cemetery in?".
    """
    from app.services.capture.surfaces import CAPTURE_SALES_ORDER as S
    from app.services.capture.schema import CALL_ORDER

    for row in S.rows:
        assert row.edit_target is not None, row.id
        assert row.edit_target in CALL_ORDER, (row.id, row.edit_target)
    assert {r.id: r.edit_target for r in S.rows}["cemetery"] == "cemetery"
    assert {r.id: r.edit_target for r in S.rows}["service"] == "service_location"


def test_the_capture_surface_shows_optional_questions_and_the_summary_does_not():
    """⚠️ TWO RULINGS CONFLICT AND EACH IS RIGHT ABOUT ITS OWN SURFACE. 2026-10-14:
    "only needed rows and things you've actually said are shown… nine empty rows on a
    fresh order is a wall of grey". 2026-10-27: the row list includes Equipment, which
    is optional — so the first hides a row the second names.

    The capture pane is now the MAP, with the asked row outlined and every row
    clickable; the Review has neither. So the flag is per-surface.
    """
    from app.services.capture.surfaces import CAPTURE_SALES_ORDER, SUMMARY_SALES_ORDER

    assert CAPTURE_SALES_ORDER.show_unmentioned_optional is True
    assert SUMMARY_SALES_ORDER.show_unmentioned_optional is False


def test_the_equipment_row_is_relabelled_on_a_cremation():
    from app.services.capture.schema import CREMATION_EQUIPMENT_ROW_LABEL

    assert CREMATION_EQUIPMENT_ROW_LABEL == "Cremation setup"


def test_the_funeral_home_pills_offer_only_customers_who_have_ORDERED(db, canonical_tenant):
    """⚠️ WHAT JAMES SAW: "St. Mary's Cemetery and 'Fairview Burial Services' appear
    under 'Which funeral home?'". Both are customers; neither has ever placed an order.
    They were there because this branch padded the list from every ACTIVE customer — a
    pad I added that the dispatch never asked for.

    ⚠️ IT IS NOT THE `customer_type` FIX. No ruling on that has reached me, and measured
    on production the column is NULL on all five of Sunnycrest's customers, so nothing
    can tell a funeral home from a cemetery today. Order history is a different
    discriminator that happens to give the right answer here.

    ⚠️ AND IT HAS A KNOWN COST: a genuinely NEW funeral home has no orders either, so it
    is not offered until its first one is typed. Asserted below so the trade is visible
    rather than discovered.
    """
    from app.services.capture.pills import pills_for

    facts = [
        order(funeral_home="Hopkins Funeral Home"),
        order(funeral_home="Hopkins Funeral Home"),
        order(funeral_home="Riverside Memorial Chapel"),
    ]
    values: dict = {}
    got = pills_for(
        db, tenant_id=TESTCO_ID, field_id="funeral_home", values=values,
        resolved_fields=_resolved(db, values), today=date(2026, 10, 27), facts=facts,
    )
    offered = {p.value for p in got}
    assert "Hopkins Funeral Home" in offered
    assert "Riverside Memorial Chapel" in offered
    # ⚠️ THE CONTROL AND THE POINT: a customer with no orders is NOT offered, whatever
    # it is called. Testco's own customer list is seeded and wider than these two.
    assert offered == {"Hopkins Funeral Home", "Riverside Memorial Chapel"}, offered


def test_a_customer_with_no_orders_is_not_offered_even_if_it_is_the_only_one(db, canonical_tenant):
    """⚠️ THE COST, STATED AS A TEST. With no order history there are no funeral-home
    pills at all — the office types the name, which always works. Pills are an
    accelerator and never the only route, and this is the case the `customer_type`
    ruling is needed for."""
    from app.services.capture.pills import pills_for

    values: dict = {}
    got = pills_for(
        db, tenant_id=TESTCO_ID, field_id="funeral_home", values=values,
        resolved_fields=_resolved(db, values), today=date(2026, 10, 27), facts=[],
    )
    assert got == ()


def test_the_capture_surface_RENDERS_the_optional_equipment_row():
    """⚠️ THE FLAG'S VALUE IS NOT THE FLAG BEING READ, and a break test is why this
    exists. `test_the_capture_surface_shows_optional_questions_and_the_summary_does_not`
    asserts `show_unmentioned_optional is True` — which stays true if nothing consults
    it. Disabling the read in `rows.py` turned nothing red in this suite.

    ⚠️ SO THIS RENDERS. On a fresh order `cemetery_equipment` is applicable, optional
    and unanswered — exactly the row the 2026-10-14 rule hides and the 2026-10-27 list
    names — so its presence is the flag being obeyed.
    """
    from app.services.capture import template_for, SALES_ORDER
    from app.services.capture.rows import resolve_surface
    from app.services.capture.schema import resolve_schema
    from app.services.capture.surfaces import CAPTURE_SALES_ORDER

    fields = resolve_schema(
        vault_product_id=None, personalization_config=None,
        platform_fields=template_for(SALES_ORDER), answers={},
    )
    shown = {r.row_id for r in resolve_surface(CAPTURE_SALES_ORDER, fields, {}).rows}
    assert "cemetery_equipment" in shown, sorted(shown)
    # ⚠️ THE CONTROL: the required rows are there too, so a render that returned
    # everything unconditionally would not satisfy this by accident — the assertion
    # below is what fails if the surface stops hiding INAPPLICABLE rows.
    assert {"funeral_home", "deceased_name", "vault"} <= shown, sorted(shown)
    assert "legacy_print" not in shown, "inapplicable rows must still be absent"


def test_a_clicked_row_changes_the_QUESTION_and_an_unknown_field_is_IGNORED(
    db, a_real_user, canonical_tenant,
):
    """'clicking a row asks that question again' — and `asking` is validated.

    ⚠️ THIS EXISTS BECAUSE I HAD ONLY A PROBE. I verified the override by running a
    script against production data once and reported it as working. `asking` arrives
    from a QUERY STRING and decides which question Opas composes, so "I ran it and it
    looked right" is the weakest evidence in this file — and a probe cannot fail in CI.

    ⚠️ THE VALIDATION IS THE HALF THAT MATTERS. An unchecked value would let a stale
    client, a bookmarked URL or a hand-typed parameter put the pane on a question this
    order does not have — "Which Legacy print?" on an order with no personalization.
    """
    from app.services.capture import session_service

    row = session_service.start(db, company_id=TESTCO_ID, user_id=a_real_user)
    try:
        session_service.set_text(
            db, row.id, company_id=TESTCO_ID, user_id=a_real_user,
            text="order for hopkins",
        )

        # what Opas asks on its own
        plain = session_service.read_state(
            db, row.id, company_id=TESTCO_ID, user_id=a_real_user,
        )
        assert plain["question_field_id"] is not None
        assert plain["question_field_id"] != "cemetery", plain["question_field_id"]

        # the office clicks the Cemetery row
        clicked = session_service.read_state(
            db, row.id, company_id=TESTCO_ID, user_id=a_real_user, asking="cemetery",
        )
        assert clicked["question_field_id"] == "cemetery", clicked["question_field_id"]
        # ⚠️ AND THE SENTENCE FOLLOWS, which is what "asks that question again" means.
        # The outline alone was my first version and was not enough.
        assert clicked["question"] == "Which cemetery?", clicked["question"]

        # ⚠️ A FIELD THIS ORDER DOES NOT ASK ABOUT IS IGNORED, not honoured and not an
        # error: the pane falls back to the question Opas was already asking.
        for junk in ("legacy_print_name", "'; DROP TABLE--", "made_up_field", ""):
            got = session_service.read_state(
                db, row.id, company_id=TESTCO_ID, user_id=a_real_user, asking=junk,
            )
            assert got["question_field_id"] == plain["question_field_id"], (junk, got)

        # ⚠️ AND AN ALREADY-ANSWERED FIELD IS HONOURED, because changing an answer is
        # exactly why somebody clicks a filled row. That is the prototype's rule
        # (`S.focus` is preferred while applicable) read the other way round.
        assert "funeral_home" in plain["answered"], plain["answered"]
        again = session_service.read_state(
            db, row.id, company_id=TESTCO_ID, user_id=a_real_user,
            asking="funeral_home",
        )
        assert again["question_field_id"] == "funeral_home"
        assert again["question"] == "Which funeral home?"
    finally:
        db.rollback()
