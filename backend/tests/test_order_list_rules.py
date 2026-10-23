"""Order-list rules. No database, no network, no model call.

The questions the spec names are pinned here, and so is the refusal to let a
model reply carry a query or a total. Stage, groups, and money are counted
from constructed facts so a wrong dot or a wrong sum fails without a tenant.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal

from app.services.order_list.proposal import propose
from app.services.order_list.question import (
    TRY_HINT,
    accept_model_text,
    interpret,
    pills_for,
    without_pill,
)
from app.services.order_list.stage import (
    DOTS_FILLED,
    DeliveryFact,
    OrderFacts,
    ProofFact,
    TaskFact,
    flag_of,
    format_money,
    group_of,
    group_order_for,
    lens_for,
    row_dict,
    select_default,
    select_flat,
    stage_of,
    sum_totals,
    total_sentence,
)
from app.services.order_list.question import OrderQuestion

# Thursday, the prototype's "today", so Friday is the next day.
TODAY = date(2026, 10, 8)


def _facts(**kwargs) -> OrderFacts:
    base = dict(
        id=kwargs.pop("id", "o1"),
        number=kwargs.pop("number", "SO-1"),
        deceased_name=kwargs.pop("deceased_name", "John R. Albright"),
        funeral_home=kwargs.pop("funeral_home", "Hopkins"),
        total=kwargs.pop("total", Decimal("100")),
    )
    base.update(kwargs)
    return OrderFacts(**base)


# ── the questions the spec names ────────────────────────────────────────


def test_orders_with_no_question_is_the_default_view():
    result = interpret("orders", today=TODAY)
    assert result.kind == "question"
    question = result.question
    assert question is not None and question.is_default
    assert question.title == "Open orders"
    assert pills_for(question) == []
    assert question.about_money is False


def test_hopkins_orders_this_month():
    result = interpret("Hopkins orders this month", today=TODAY)
    question = result.question
    assert question is not None
    assert question.funeral_home == "hopkins"
    assert question.when_label == "This month"
    assert question.service_from == date(2026, 10, 1)
    assert question.service_to == date(2026, 10, 31)
    assert question.title == "Hopkins orders this month"
    assert question.about_money is True
    assert [pill.label for pill in pills_for(question)] == ["Hopkins", "This month"]


def test_going_out_friday_is_the_coming_friday_and_not_a_money_question():
    result = interpret("what's going out Friday", today=TODAY)
    question = result.question
    assert question is not None
    assert question.going_out is True
    assert question.service_from == date(2026, 10, 9)
    assert question.service_to == date(2026, 10, 9)
    assert question.when_label == "Fri Oct 9"
    assert question.title == "Going out Friday"
    assert question.about_money is False
    assert [pill.label for pill in pills_for(question)] == ["Going out", "Fri Oct 9"]


def test_friday_includes_today_when_today_is_friday():
    result = interpret("going out friday", today=date(2026, 10, 9))
    assert result.question is not None
    assert result.question.service_from == date(2026, 10, 9)


def test_delivered_not_invoiced():
    result = interpret("delivered, not invoiced", today=TODAY)
    question = result.question
    assert question is not None
    assert question.delivered is True and question.invoiced is False
    assert question.title == "Delivered, not invoiced"
    assert question.about_money is True
    assert [pill.label for pill in pills_for(question)] == ["Delivered", "Not invoiced"]


def test_monticellos_since_june_is_a_vault_not_a_guessed_home():
    result = interpret("Monticellos since June", today=TODAY)
    question = result.question
    assert question is not None
    assert question.vault == "monticello"
    assert question.funeral_home is None
    assert question.service_from == date(2026, 6, 1)
    assert question.service_to is None
    assert question.when_label == "Since June"
    assert question.title == "Monticellos since June"
    assert question.about_money is True
    assert [pill.label for pill in pills_for(question)] == ["Monticello", "Since June"]


def test_since_june_before_june_is_last_years_june():
    result = interpret("monticellos since june", today=date(2026, 3, 1))
    assert result.question is not None
    assert result.question.service_from == date(2025, 6, 1)


def test_a_phrase_the_rules_do_not_know_is_not_guessed():
    result = interpret("asdf", today=TODAY)
    assert result.kind == "unrecognized"
    assert result.hint == TRY_HINT
    assert result.question is None


def test_the_albright_order_opens_an_order_rather_than_listing():
    result = interpret("the Albright order", today=TODAY)
    assert result.kind == "open_order"
    assert result.decedent_query == "albright"


def test_how_much_needs_an_open_question_and_does_not_invent_one():
    assert interpret("how much is that?", today=TODAY).kind == "unrecognized"
    current = interpret("going out friday", today=TODAY).question
    result = interpret("how much is that?", today=TODAY, current=current)
    assert result.kind == "total"
    assert result.question is current


def test_on_the_lens_keeps_the_question_and_changes_the_surface():
    result = interpret("what's going out Friday on the lens", today=TODAY)
    assert result.question is not None
    assert result.question.surface == "lens"
    assert result.question.title == "Going out Friday"


def test_a_corrected_phrase_wins_over_the_built_in_rule():
    corrected = interpret("orders this month", today=TODAY).question
    assert corrected is not None
    result = interpret(
        "Hopkins orders this month",
        today=TODAY,
        taught={"hopkins orders this month": corrected.model_dump(mode="json")},
    )
    assert result.question is not None
    assert result.question.funeral_home is None
    assert result.question.when_label == "This month"


def test_only_and_not_invoiced_narrow_the_open_question():
    current = interpret("orders this month", today=TODAY).question
    narrowed = interpret("only Hopkins", today=TODAY, current=current)
    assert narrowed.question is not None
    assert narrowed.question.unresolved_subject == "hopkins"
    assert narrowed.question.service_from == date(2026, 10, 1)
    invoiced = interpret("not invoiced", today=TODAY, current=narrowed.question)
    assert invoiced.question is not None
    assert invoiced.question.invoiced is False


def test_just_venetians_is_a_vault_plural():
    current = interpret("going out friday", today=TODAY).question
    result = interpret("just Venetians", today=TODAY, current=current)
    assert result.question is not None
    assert result.question.vault == "venetian"
    assert result.question.service_from == date(2026, 10, 9)


def test_removing_the_last_pill_returns_to_the_default_view():
    question = interpret("Hopkins orders this month", today=TODAY).question
    assert question is not None
    without_home = without_pill(question, "funeral_home")
    assert without_home.funeral_home is None
    assert without_home.when_label == "This month"
    assert without_pill(without_home, "when").is_default


def test_trailing_punctuation_does_not_miss():
    assert interpret("orders.", today=TODAY).question.is_default  # type: ignore[union-attr]


# ── a model reply is a question or it is nothing ───────────────────────


def test_model_json_with_sql_or_a_total_is_refused():
    assert accept_model_text('{"sql": "select 1", "funeral_home": "hopkins"}', TODAY) is None
    assert accept_model_text('{"question": {"funeral_home": "hopkins", "total": "10"}}', TODAY) is None
    assert accept_model_text("not json", TODAY) is None


def test_model_json_cannot_set_about_money_on_a_schedule_question():
    parsed = accept_model_text(
        '{"question": {"going_out": true, "title": "Going out Friday", "about_money": true}}', TODAY)
    assert parsed is not None and parsed.question is not None
    assert parsed.question.about_money is False


def test_the_model_door_stays_shut_without_a_session():
    assert propose("something the rules do not know", TODAY) is None


def test_model_unsure_is_numbered_picks_and_not_a_guess():
    parsed = accept_model_text(
        '{"unsure": true, "picks": ['
        '{"label": "Monticello, the vault", "question": {"vault": "monticello"}},'
        '{"label": "Monticello, the cemetery", "question": {"cemetery": "monticello"}}'
        "]}", TODAY)
    assert parsed is not None and parsed.kind == "picks"
    assert len(parsed.picks) == 2
    assert parsed.picks[0].question is not None
    assert parsed.picks[0].question.vault == "monticello"


# ── stage, groups, money ───────────────────────────────────────────────


def test_dots_match_the_four_steps():
    pending = _facts(proofs=[ProofFact(status="draft")])
    confirmed = _facts(service_date=date(2026, 10, 9), deliveries=[DeliveryFact(primary_assignee_id="u")])
    delivered = _facts(delivered_at=datetime(2026, 10, 2, tzinfo=timezone.utc), completed_at=datetime(2026, 10, 2, tzinfo=timezone.utc))
    invoiced = _facts(invoice_statuses=["sent"], delivered_at=datetime(2026, 10, 2, tzinfo=timezone.utc))
    assert stage_of(pending) == "proof" and DOTS_FILLED["proof"] == 0
    # ⚠️ THE RUNG IS `confirmed`, NOT `scheduled`, SINCE 2026-10-23. Nothing in this
    # platform schedules an order as a state, so the ladder may not claim it did.
    assert stage_of(confirmed) == "confirmed" and DOTS_FILLED["confirmed"] == 1
    assert "scheduled" not in DOTS_FILLED
    assert stage_of(delivered) == "delivered" and DOTS_FILLED["delivered"] == 2
    assert stage_of(invoiced) == "invoiced" and DOTS_FILLED["invoiced"] == 4
    assert 3 not in DOTS_FILLED.values()


def test_flags_and_which_group_they_land_in():
    change = _facts(proofs=[ProofFact(
        status="approved",
        approved_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        latest_version_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
    )])
    proof = _facts(tasks=[TaskFact(task_type="legacy_print", status="in_progress")])
    driver = _facts(service_date=date(2026, 10, 9))
    later = _facts(id="later", service_date=date(2026, 12, 1))
    close = _facts(id="close", delivered_at=datetime(2026, 9, 1, tzinfo=timezone.utc), service_date=date(2026, 9, 1))
    billed = _facts(
        id="billed",
        delivered_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        completed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        service_date=date(2026, 10, 2),
        invoice_statuses=["sent"],
    )
    quiet = _facts(
        id="quiet",
        service_date=date(2026, 10, 9),
        deliveries=[DeliveryFact(primary_assignee_id="driver")],
    )
    unbilled = _facts(
        id="unbilled",
        delivered_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        completed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        service_date=date(2026, 10, 2),
    )
    assert flag_of(change, TODAY) == "change"
    assert flag_of(proof, TODAY) == "proof"
    assert flag_of(driver, TODAY) == "nodriver"
    assert flag_of(later, TODAY) is None
    assert flag_of(close, TODAY) == "close"
    assert flag_of(billed, TODAY) is None
    assert group_of(change, TODAY) == "needs_something"
    assert group_of(driver, TODAY) == "needs_something"
    assert group_of(quiet, TODAY) == "going_out_this_week"
    assert group_of(close, TODAY) == "needs_something"
    assert group_of(unbilled, TODAY) == "delivered_not_invoiced"
    assert group_of(billed, TODAY) is None
    assert group_of(later, TODAY) is None


def test_every_delivered_not_invoiced_order_is_in_the_default_group():
    old = _facts(
        delivered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        service_date=date(2026, 1, 1),
    )
    assert group_of(old, TODAY) == "delivered_not_invoiced"
    grouped = select_default([old], TODAY)
    assert [item.id for item in grouped["delivered_not_invoiced"]] == [old.id]
    question = interpret("delivered, not invoiced", today=TODAY).question
    assert question is not None
    assert select_flat([old], question, TODAY) == [old]
    waiting = _facts(
        id="waiting",
        delivered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        service_date=date(2026, 1, 1),
    )
    assert group_of(waiting, TODAY) == "needs_something"


def test_default_groups_hide_empty_ones_and_accounting_leads_with_money():
    rows = [
        _facts(id="need", service_date=date(2026, 10, 9)),
        _facts(
            id="out",
            deceased_name="Edith M. Carr",
            service_date=date(2026, 10, 9),
            deliveries=[DeliveryFact(primary_assignee_id="d")],
        ),
    ]
    grouped = select_default(rows, TODAY)
    assert [key for key, members in grouped.items() if members] == [
        "needs_something", "going_out_this_week",
    ]
    assert group_order_for("office_staff")[0] == "needs_something"
    assert group_order_for("accountant")[0] == "delivered_not_invoiced"
    assert group_order_for(None)[0] == "needs_something"


def test_money_is_summed_from_the_rows_and_omitted_for_a_schedule_question():
    rows = [
        _facts(id="a", total=Decimal("100.50"), invoice_statuses=[]),
        _facts(id="b", total=Decimal("20"), invoice_statuses=["paid"]),
    ]
    money = interpret("Hopkins orders this month", today=TODAY).question
    schedule = interpret("going out friday", today=TODAY).question
    not_billed = interpret("delivered, not invoiced", today=TODAY).question
    assert money is not None and schedule is not None and not_billed is not None
    hopkins = sum_totals(rows, money)
    assert hopkins is not None
    assert hopkins["count"] == 2
    assert hopkins["total"] == "120.50"
    assert hopkins["show_money"] is True
    assert hopkins["show_not_invoiced"] is True
    going = sum_totals(rows, schedule)
    assert going is not None and going["show_money"] is False and going["total"] is None
    billed = sum_totals(rows, not_billed)
    assert billed is not None and billed["show_not_invoiced"] is False
    assert total_sentence(rows) == "2 orders · $120.50"
    assert format_money("6840.00") == "$6,840"


def test_row_omits_what_the_order_does_not_have_and_names_the_fix():
    bare = row_dict(_facts(deceased_name=None, funeral_home="Hopkins", service_date=None, service_time=None), TODAY)
    assert "service_date" not in bare
    assert "flag" not in bare
    assert bare["deceased_name"] == "Unnamed"
    flagged = row_dict(_facts(service_date=date(2026, 10, 9), service_time=time(9, 0)), TODAY)
    assert flagged["flag"] == "nodriver"
    assert flagged["action"] == "scheduling"
    assert flagged["action_label"] == "Open scheduling"
    assert flagged["time_label"] == "9:00"
    assert flagged["date_in_week"] is True
    assert flagged["date_primary"] == "Fri"


def test_lens_says_three_and_sends_the_rest_to_the_ipad():
    rows = [
        _facts(id=str(i), deceased_name=f"Person {name}", service_date=date(2026, 10, 9), service_time=time(9, 0))
        for i, name in enumerate(["Albright", "Carr", "Fenn", "Prisco", "Kemp"])
    ]
    lens = lens_for(title="Going out Friday", rows=rows, today=TODAY)
    assert lens["heading"] == "GOING OUT FRIDAY · 5"
    assert lens["pages"][0]["items"] == ["Albright 9:00", "Carr 9:00", "Fenn 9:00"]
    assert lens["pages"][0]["more"] == 2
    assert "iPad" in lens["cue"]
    short = lens_for(title="Going out Friday", rows=rows[:2], today=TODAY)
    assert short["cue"] == "tap: open the first"
    assert len(short["pages"]) == 1


def test_a_draft_invoice_is_not_invoiced_and_a_cancelled_order_is_not_listed():
    draft = _facts(invoice_statuses=["draft"], delivered_at=datetime(2026, 10, 2, tzinfo=timezone.utc), completed_at=datetime(2026, 10, 2, tzinfo=timezone.utc), service_date=date(2026, 10, 2))
    assert draft.invoiced is False
    assert group_of(draft, TODAY) == "delivered_not_invoiced"
    cancelled = _facts(status="cancelled", service_date=date(2026, 10, 9))
    question = interpret("going out friday", today=TODAY).question
    assert question is not None
    assert select_flat([cancelled], question, TODAY) == []


def test_no_legacy_work_is_not_a_proof_flag():
    plain = _facts(service_date=date(2026, 10, 9), deliveries=[DeliveryFact(primary_assignee_id="d")])
    assert plain.proof == "none"
    assert flag_of(plain, TODAY) is None
    assert stage_of(plain) == "confirmed"
