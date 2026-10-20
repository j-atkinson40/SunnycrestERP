""""Send the model the least it needs" — and the door's own guarantees.

James's ruling, 2026-10-20: *"Send the model the least it needs, and adopt that as a
rule. Working out 'hopkins order' needs a surname at most. Answering 'when's the service'
for the order in front needs no model at all. A deceased person's name only goes to a
model when it's actually needed."*

⚠️ THE RULE IS ABOUT THE ONE PIECE OF SENSITIVE DATA IN THE SYSTEM. A funeral order
carries a dead person's name, their funeral home, their cemetery and the day they are
buried. Three of those are business records; the first is not. These tests exist so that
the subtraction cannot be undone by a later edit adding a field "for context".
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.cemetery import Cemetery
from app.models.company import Company
from app.models.customer import Customer
from app.models.product import Product
from app.models.sales_order import SalesOrder
from app.services.order_list import model_context
from app.services.order_list.proposal import PROMPT_KEY, propose
from app.services.order_list.question import accept_model_text

DECEASED = "Hildegard Mortensen"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        s.execute(sql_text("SELECT 1"))
    except Exception as exc:
        s.close()
        pytest.skip(f"database unavailable: {exc}")
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def tenant(db):
    company = Company(
        id=str(uuid.uuid4()), name="Door Co", slug=f"door-{uuid.uuid4().hex[:8]}",
        is_active=True, vertical="manufacturing",
    )
    db.add(company)
    db.flush()
    customer = Customer(
        id=str(uuid.uuid4()), company_id=company.id,
        name="Hopkins Funeral Home", is_active=True,
    )
    db.add(customer)
    db.add(Customer(
        id=str(uuid.uuid4()), company_id=company.id,
        name="Riverside Memorial Chapel", is_active=True,
    ))
    db.add(Cemetery(
        id=str(uuid.uuid4()), company_id=company.id,
        name="St. Mary's Cemetery", city="Skaneateles",
    ))
    db.add(Product(
        id=str(uuid.uuid4()), company_id=company.id,
        name="Monticello Burial Vault", price=Decimal("1405.00"), is_active=True,
    ))
    db.flush()
    # ⚠️ AN ORDER WITH A DECEASED NAME ON IT, which is the whole point: the name is IN
    # the tenant's data, reachable by one join from everything the context builder reads,
    # and must still not appear in the context.
    order = SalesOrder(
        id=str(uuid.uuid4()), company_id=company.id, number="SO-2026-0001",
        customer_id=customer.id, order_date=datetime.now(timezone.utc),
        status="confirmed", order_type="funeral",
        subtotal=Decimal("1405.00"), tax_rate=Decimal("0"), tax_amount=Decimal("0"),
        total=Decimal("1405.00"), deceased_name=DECEASED,
        scheduled_date=date(2026, 10, 23), service_time=time(11, 0),
    )
    db.add(order)
    db.flush()
    return company


# ───────────────────────────────────────────────────────────────────────────
# the least it needs
# ───────────────────────────────────────────────────────────────────────────

def test_the_context_carries_the_three_name_lists_and_the_phrase(db, tenant):
    ctx = model_context.build(db, tenant.id, "hopkins orders in october", date(2026, 10, 20))
    v = ctx.as_variables()
    assert v["today"] == "2026-10-20"
    assert v["phrase"] == "hopkins orders in october"
    assert "Hopkins Funeral Home" in v["funeral_homes"]
    assert "Riverside Memorial Chapel" in v["funeral_homes"]
    assert "St. Mary's Cemetery, Skaneateles" in v["cemeteries"]
    assert "Monticello Burial Vault" in v["vaults"]
    assert v["truncated"] == "no"


def test_NO_DECEASED_NAME_REACHES_THE_MODEL(db, tenant):
    """⚠️ THE RULE, ASSERTED AGAINST THE WHOLE RENDERED BLOCK rather than per field.

    A field-by-field check passes while a name sits in a field nobody thought to look
    at. This searches every value the model would receive for the name that is one join
    away from all three queries.
    """
    for phrase in [
        "hopkins orders",
        "mortensen order",                      # the phrase itself names her
        "Hildegard Mortensen orders in october",  # ⚠️ and spells her name out in full
        "anything going to st marys this week",
    ]:
        v = model_context.build(db, tenant.id, phrase, date(2026, 10, 20)).as_variables()
        blob = " | ".join(f"{k}={v[k]}" for k in sorted(v) if k != "phrase")
        assert "Mortensen" not in blob, f"a deceased name reached the model via {phrase!r}"
        assert "Hildegard" not in blob, f"a deceased name reached the model via {phrase!r}"


def test_the_phrase_is_passed_THROUGH_and_that_is_the_one_exception(db, tenant):
    """⚠️ IF THE PERSON TYPED THE NAME, THE PHRASE CARRIES IT, and it must.

    `OrderQuestion.decedent` is filled from the phrase, so a request about a named person
    cannot work without it. This is the ruling's "only when it's actually needed", and it
    is worth asserting because the test above would otherwise read as "no name, ever" —
    which would be a different and unimplementable rule.
    """
    v = model_context.build(db, tenant.id, "Mortensen order", date(2026, 10, 20)).as_variables()
    assert v["phrase"] == "Mortensen order"
    # and the name is in the phrase ONLY
    assert sum("Mortensen" in str(x) for x in v.values()) == 1


def test_no_forbidden_key_is_ever_in_the_variables(db, tenant):
    """⚠️ THE RATCHET. A later edit adding `decedents` "for context" would render fine,
    answer fine, and start sending a dead person's name out of the tenant. This is what
    fails instead.
    """
    v = model_context.build(db, tenant.id, "x", date(2026, 10, 20)).as_variables()
    offenders = model_context.FORBIDDEN_KEYS & set(v)
    assert offenders == set(), f"forbidden keys in the model context: {offenders}"
    # ⚠️ AND THE RATCHET HAS TEETH: the list is non-empty and names the field that
    # matters, so it cannot be satisfied by an empty FORBIDDEN_KEYS.
    assert "deceased_name" in model_context.FORBIDDEN_KEYS
    assert len(model_context.FORBIDDEN_KEYS) >= 10


def test_as_variables_is_explicit_rather_than_reflective(db, tenant):
    """⚠️ `asdict` WOULD CARRY ANY FIELD A FUTURE EDIT ADDS. The method lists its keys,
    so a new dataclass field reaches the prompt only if someone also writes it here.
    """
    import ast
    import inspect

    # ⚠️ THE DOCSTRING IS STRIPPED BEFORE SEARCHING, AND THE FIRST VERSION OF THIS TEST
    # DID NOT DO THAT — it failed on the word "asdict" inside the very comment
    # explaining why `asdict` is not used. The same defect is recorded in CLAUDE.md §11
    # ("My source check matched its own comment"), and it found this one too.
    src = inspect.getsource(model_context.ModelContext.as_variables)
    tree = ast.parse(src.strip())
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)
    body = fn.body[1:] if ast.get_docstring(fn) is not None else fn.body
    code = "\n".join(ast.unparse(node) for node in body)

    assert "asdict" not in code
    assert "__dict__" not in code
    assert "vars(" not in code
    for key in ("today", "phrase", "funeral_homes", "cemeteries", "vaults"):
        assert f"'{key}'" in code or f'"{key}"' in code


def test_another_tenants_names_do_not_travel(db, tenant):
    other = Company(
        id=str(uuid.uuid4()), name="Other Co", slug=f"door-{uuid.uuid4().hex[:8]}",
        is_active=True, vertical="manufacturing",
    )
    db.add(other)
    db.flush()
    db.add(Customer(
        id=str(uuid.uuid4()), company_id=other.id,
        name="Someone Else Funeral Home", is_active=True,
    ))
    db.flush()
    v = model_context.build(db, tenant.id, "x", date(2026, 10, 20)).as_variables()
    assert "Someone Else" not in v["funeral_homes"]
    # ⚠️ THE CONTROL: this tenant's own name IS there, so the absence above is about
    # scoping rather than about an empty query.
    assert "Hopkins Funeral Home" in v["funeral_homes"]


def test_the_lists_are_capped_and_say_so(db, tenant):
    for i in range(model_context.NAME_CAP + 5):
        db.add(Customer(
            id=str(uuid.uuid4()), company_id=tenant.id,
            name=f"Bulk Home {i:03d}", is_active=True,
        ))
    db.flush()
    ctx = model_context.build(db, tenant.id, "x", date(2026, 10, 20))
    assert len(ctx.funeral_homes) == model_context.NAME_CAP
    # ⚠️ AND THE TRUNCATION IS DECLARED, so the prompt can tell the model that a name it
    # was not shown may still exist — otherwise a capped list reads as exhaustive.
    assert ctx.truncated is True
    assert ctx.as_variables()["truncated"] == "yes"


def test_an_inactive_customer_or_product_does_not_travel(db, tenant):
    db.add(Customer(
        id=str(uuid.uuid4()), company_id=tenant.id,
        name="Closed Down Funeral Home", is_active=False,
    ))
    db.add(Product(
        id=str(uuid.uuid4()), company_id=tenant.id,
        name="Discontinued Vault", price=Decimal("1.00"), is_active=False,
    ))
    db.flush()
    v = model_context.build(db, tenant.id, "x", date(2026, 10, 20)).as_variables()
    assert "Closed Down" not in v["funeral_homes"]
    assert "Discontinued" not in v["vaults"]


# ───────────────────────────────────────────────────────────────────────────
# the door, and the engine deciding
# ───────────────────────────────────────────────────────────────────────────

def test_no_api_key_means_the_rules_stand_AND_NO_CALL_IS_ATTEMPTED(db, tenant, monkeypatch):
    """⚠️ MODEL-DOWN, ASSERTED AT THE DOOR — AND THE FIRST VERSION OF THIS TEST WAS NOT
    DISCRIMINATING. It asserted only that `propose` returns `None` with no key, which the
    `except Exception: return None` handler below also produces: the Anthropic client
    raises on a missing key, so the test passed whether or not the guard existed. A break
    test removing `if not settings.ANTHROPIC_API_KEY` turned nothing red.

    What the guard uniquely buys is that NO CALL IS ATTEMPTED — no wasted round trip, no
    stack trace in the log for a condition that is not an error. That is asserted
    directly, and the exception handler cannot supply it.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "", raising=False)

    import app.services.intelligence.intelligence_service as svc

    calls: list[str] = []

    def spy(*_a, **kw):
        calls.append(kw.get("prompt_key", "?"))
        raise RuntimeError("should not have been reached")

    monkeypatch.setattr(svc, "execute", spy)
    assert propose("anything going to st marys this week", date(2026, 10, 20),
                   db, tenant.id) is None
    assert calls == [], f"a call was attempted with no key: {calls}"

    # ⚠️ THE CONTROL: with a key present the same spy IS reached, so "no call" above is
    # about the guard rather than about a `propose` that never calls anything.
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test-not-real", raising=False)
    assert propose("anything going to st marys this week", date(2026, 10, 20),
                   db, tenant.id) is None
    assert calls == [PROMPT_KEY], f"the door did not reach Intelligence: {calls}"


def test_no_db_and_no_phrase_mean_no_call(db, tenant):
    assert propose("x", date(2026, 10, 20), None, tenant.id) is None
    assert propose("   ", date(2026, 10, 20), db, tenant.id) is None


def test_a_raising_model_means_the_rules_stand(db, tenant, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test-not-real", raising=False)

    import app.services.intelligence.intelligence_service as svc

    def boom(*_a, **_k):
        raise RuntimeError("provider is down")

    monkeypatch.setattr(svc, "execute", boom)
    assert propose("anything going to st marys", date(2026, 10, 20), db, tenant.id) is None


def test_the_engine_refuses_every_shape_the_prompt_forbids():
    """⚠️ THE PROMPT ASKS AND THE VALIDATOR DECIDES, and these are the same rules stated
    twice on purpose. A prompt is a request; sometimes the model will not comply.
    """
    assert accept_model_text("not json") is None
    assert accept_model_text('{"unsure": true, "picks": []}') is None
    assert accept_model_text('{"question": {"funeral_home": {"bad": "shape"}}}') is None

    # ⚠️ THESE THREE ARE REFUSED TWICE OVER, AND A BREAK TEST SHOWED IT. Removing the
    # top-level `_banned(payload)` call left them all green: `OrderQuestion` carries
    # `extra="forbid"`, so a banned key INSIDE a question object is rejected by pydantic
    # whether or not `_banned` ran. Two independent guards, which is worth having and is
    # not what this test was claiming to measure.
    assert accept_model_text('{"question": {"total": "1705.00"}}') is None
    assert accept_model_text('{"question": {"sql": "SELECT 1"}}') is None
    assert accept_model_text('{"question": {"nested": {"count": 3}}}') is None

    # ⚠️ AND THIS IS WHAT ONLY `_banned` CATCHES: a banned key OUTSIDE the question
    # object, beside a question that is perfectly valid. Pydantic never looks here, so
    # without the recursive check the answer would be ACCEPTED and the `sql` string
    # would travel on an otherwise legal request.
    assert accept_model_text(
        '{"sql": "SELECT 1", "question": {"funeral_home": "Hopkins Funeral Home"}}'
    ) is None
    assert accept_model_text(
        '{"unsure": true, "picks": [{"label": "x", "count": 3, '
        '"question": {"funeral_home": "Hopkins Funeral Home"}}]}'
    ) is None
    # ⚠️ THE CONTROL: a legal answer is accepted, so the six Nones above are about the
    # guards rather than about a validator that refuses everything.
    got = accept_model_text('{"question": {"funeral_home": "Hopkins Funeral Home"}}')
    assert got is not None and got.kind == "question"
    assert got.question.funeral_home == "Hopkins Funeral Home"


def test_the_prompt_key_the_door_asks_for_is_the_one_the_seed_writes():
    """⚠️ TWO FILES NAME ONE STRING. A rename in either without the other leaves the door
    shut again, silently — which is exactly the state this slice found it in.
    """
    from scripts.seed_opas_order_list_prompt import PROMPT_KEY as SEEDED

    assert PROMPT_KEY == SEEDED == "opas.order_list.interpret"


def test_every_jinja_variable_in_the_prompt_is_one_the_door_sends(db, tenant):
    """⚠️ A VARIABLE THE PROMPT USES AND THE CALLER DOES NOT SEND IS A RENDER ERROR AT
    RUNTIME, which `propose` would swallow as `None` — the door shut for a reason nobody
    could see.
    """
    import re

    from scripts.seed_opas_order_list_prompt import (
        SYSTEM_PROMPT, USER_TEMPLATE, VARIABLE_SCHEMA,
    )

    used = set(re.findall(r"{{\s*(\w+)\s*}}", SYSTEM_PROMPT + USER_TEMPLATE))
    sent = set(model_context.build(db, tenant.id, "x", date(2026, 10, 20)).as_variables())
    assert used <= sent, f"the prompt uses variables the door does not send: {used - sent}"
    assert used <= set(VARIABLE_SCHEMA), f"undeclared: {used - set(VARIABLE_SCHEMA)}"
    # and nothing is declared that is never used — a declared-but-unused variable is a
    # context block item nobody reads
    assert set(VARIABLE_SCHEMA) == used, f"declared but unused: {set(VARIABLE_SCHEMA) - used}"


def test_the_prompt_forbids_in_words_what_the_validator_refuses_in_code():
    """⚠️ NOT A STYLE CHECK. If the prompt stopped telling the model not to return a
    total, the model would start returning them, every answer would be refused, and the
    door would look broken rather than mis-prompted."""
    from scripts.seed_opas_order_list_prompt import SYSTEM_PROMPT
    from app.services.order_list.question import _BANNED_KEYS

    lowered = SYSTEM_PROMPT.lower()
    for word in ("total", "count", "sum", "sql"):
        assert word in _BANNED_KEYS
        assert word in lowered, f"the prompt never mentions {word!r}"
    assert "decedent names" in lowered
