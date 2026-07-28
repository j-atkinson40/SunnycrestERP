"""S-2 (§4.3) quote-preview — money-math + render + drift gates.

HAND-PROVEN money math (ruled decision 3). Every expected unit price,
line total, subtotal, and grand total below is computed BY HAND in the
test body and asserted against the assembler's output. No preview
pricing ships without this discipline.

The three money-math cases:
  A. 3× Monticello (a vault, non-conditional) — proves qty × price,
     banker's rounding at the line, subtotal, and the honest
     tax-unresolved path (no fabricated grand total).
  B. 1× call-office product — proves "Price on request", never a number.
  C. 2× a plain product with a deterministic 8% tax — proves the total
     assembly is subtotal + tax_amount (not re-rounded), matching
     quote_service.create_quote.

Plus: the DRIFT GUARD (preview and the final quote PDF share the one
`quote.standard` body_template), unresolved-product surfacing, plural
tolerance, price-list-reference tiered display, and endpoint wiring.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.services.command_bar.quote_preview import (
    QUOTE_TEMPLATE_KEY,
    DraftLine,
    assemble_quote_preview,
)


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def world(db_session):
    """A bare tenant with three products: a vault (Monticello, $1,250.00),
    a call-office product (no price), and a plain product ($500.00).
    Torn down fully to satisfy the company-litter tripwire."""
    from app.models.company import Company
    from app.models.product import Product
    from app.models.role import Role
    from app.models.user import User

    db = db_session
    suffix = uuid.uuid4().hex[:6]

    co = Company(
        id=str(uuid.uuid4()),
        name=f"QP {suffix}",
        slug=f"qp-{suffix}",
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
        email=f"a-{suffix}@qp.co",
        first_name="Q",
        last_name="P",
        hashed_password="x",
        is_active=True,
        is_super_admin=True,
        role_id=role.id,
    )
    db.add(user)
    monticello = Product(
        id=str(uuid.uuid4()),
        company_id=co.id,
        name="Monticello",
        sku=f"MON-{suffix}",
        price=Decimal("1250.00"),
        is_active=True,
        has_conditional_pricing=False,
        is_call_office=False,
        product_line="monticello",
    )
    call_office = Product(
        id=str(uuid.uuid4()),
        company_id=co.id,
        name="Custom Bronze Memorial",
        sku=f"CBM-{suffix}",
        price=None,
        is_active=True,
        is_call_office=True,
    )
    widget = Product(
        id=str(uuid.uuid4()),
        company_id=co.id,
        name="Grave Widget",
        sku=f"GW-{suffix}",
        price=Decimal("500.00"),
        is_active=True,
    )
    db.add_all([monticello, call_office, widget])
    db.commit()

    yield {
        "company_id": co.id,
        "user_id": user.id,
        "slug": co.slug,
        "monticello_id": monticello.id,
        "call_office_id": call_office.id,
        "widget_id": widget.id,
    }

    # Teardown — FK-safe order, delete everything this fixture created.
    from app.models.price_list_item import PriceListItem
    from app.models.price_list_version import PriceListVersion

    db.query(PriceListItem).filter(PriceListItem.tenant_id == co.id).delete(
        synchronize_session=False
    )
    db.query(PriceListVersion).filter(
        PriceListVersion.tenant_id == co.id
    ).delete(synchronize_session=False)
    db.query(Product).filter(Product.company_id == co.id).delete(
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


# ── Case A — 3× Monticello, tax unresolved ───────────────────────────


def test_case_a_three_monticellos(db_session, world):
    res = assemble_quote_preview(
        db_session,
        world["company_id"],
        customer_name="Hopkins Funeral Home",
        lines=[DraftLine(product_ref="Monticello", quantity=3)],
    )

    # HAND-PROOF:
    #   unit price          = product.price                 = $1,250.00
    #   line_total          = round_money(3 × 1250.00)      = $3,750.00
    #   subtotal            = Σ line_totals                 = $3,750.00
    #   tax                 = unresolved (bare tenant, no jurisdiction)
    #   grand total         = NONE (honest — no fabricated tax/total)
    assert res.line_count == 1
    ln = res.context["lines"][0]
    assert ln["description"] == "Monticello"
    assert ln["quantity"] == 3.0
    assert ln["unit_price_formatted"] == "$1,250.00"
    assert ln["line_total_formatted"] == "$3,750.00"

    assert res.subtotal == Decimal("3750.00")
    assert res.subtotal_formatted == "$3,750.00"

    assert res.tax_resolved is False
    assert res.total is None
    assert res.total_formatted is None
    # Template hides its Total row when total_formatted is empty.
    assert res.context["total_formatted"] == ""

    # The REAL quote template rendered the REAL prices (not a fork):
    assert "$1,250.00" in res.html
    assert "$3,750.00" in res.html
    assert "QUOTE" in res.html  # quote.standard chrome


# ── Case B — call-office → "Price on request" ────────────────────────


def test_case_b_call_office(db_session, world):
    res = assemble_quote_preview(
        db_session,
        world["company_id"],
        lines=[DraftLine(product_ref="Custom Bronze Memorial", quantity=1)],
    )

    assert res.has_call_office is True
    ln = res.context["lines"][0]
    assert ln["unit_price_formatted"] == "Price on request"
    assert ln["line_total_formatted"] == "—"
    # Nothing priced → no subtotal figure fabricated.
    assert res.subtotal == Decimal("0.00")
    assert res.subtotal_formatted == ""
    assert res.tax_resolved is False
    assert res.total_formatted is None
    assert "Price on request" in res.html


# ── Case C — total = subtotal + tax (deterministic 8%) ───────────────


def test_case_c_total_is_subtotal_plus_tax(db_session, world, monkeypatch):
    from app.services import tax_service
    from app.services.tax_service import LineTaxResolution

    def fake_resolve(db, company_id, *, lines, customer_id=None, **kw):
        taxable = sum((ln["amount"] for ln in lines), Decimal("0"))
        # A flat, deterministic 8% so the total is hand-provable.
        return LineTaxResolution(
            tax_amount=Decimal("80.00"),
            tax_rate=Decimal("0.08"),
            reason="test",
            resolved=True,
            source="jurisdiction",
            taxable_subtotal=taxable,
            exempt_subtotal=Decimal("0"),
            exempt_lines=[],
            gaps=[],
        )

    monkeypatch.setattr(tax_service, "resolve_line_tax", fake_resolve)

    res = assemble_quote_preview(
        db_session,
        world["company_id"],
        customer_id="cust-x",
        lines=[DraftLine(product_ref="Grave Widget", quantity=2)],
    )

    # HAND-PROOF:
    #   unit price   = $500.00
    #   line_total   = round_money(2 × 500.00) = $1,000.00
    #   subtotal     = $1,000.00
    #   tax (8%)     = $80.00
    #   total        = subtotal + tax = $1,080.00  (not re-rounded)
    assert res.subtotal == Decimal("1000.00")
    assert res.tax_resolved is True
    assert res.total == Decimal("1080.00")
    assert res.total_formatted == "$1,080.00"
    assert res.context["total_formatted"] == "$1,080.00"
    assert "$1,080.00" in res.html


# ── Drift guard — one template, no second renderer ───────────────────


def test_drift_guard_preview_shares_body_template_with_final(
    db_session, world
):
    import inspect

    from app.services import quote_service
    from app.services.documents import template_loader

    # The preview and the final quote PDF target the SAME key.
    assert QUOTE_TEMPLATE_KEY == "quote.standard"
    final_src = inspect.getsource(quote_service.generate_quote_document)
    assert "quote.standard" in final_src

    # And that key resolves to the real quote line-item document — the
    # one body_template both paths render (PDF only adds WeasyPrint).
    loaded = template_loader.load(
        QUOTE_TEMPLATE_KEY, company_id=world["company_id"], db=db_session
    )
    assert "{% for ln in lines %}" in loaded.body_template
    assert "ln.unit_price_formatted" in loaded.body_template
    assert "ln.line_total_formatted" in loaded.body_template


# ── Resolution behaviors ─────────────────────────────────────────────


def test_unresolved_product_listed_not_priced(db_session, world):
    res = assemble_quote_preview(
        db_session,
        world["company_id"],
        lines=[DraftLine(product_ref="Nonexistent Zzz Product", quantity=2)],
    )
    assert res.unresolved_products == ["Nonexistent Zzz Product"]
    assert res.line_count == 0
    assert res.subtotal_formatted == ""
    assert "No line items." in res.html


def test_plural_product_ref_resolves(db_session, world):
    res = assemble_quote_preview(
        db_session,
        world["company_id"],
        lines=[DraftLine(product_ref="Monticellos", quantity=3)],
    )
    assert res.line_count == 1
    assert res.context["lines"][0]["description"] == "Monticello"


# ── Fuzzy-with-refusal (S-2 staging-witness fix) ─────────────────────
#
# The witness caught that the live AI extraction emits qualifier-suffixed
# product names ("Monticello Standard") that the strict substring match
# can't resolve. These tests feed the resolver the strings the AI ACTUALLY
# EMITS — the gap the old money test (clean "Monticello") missed.


def test_qualifier_suffixed_name_resolves_via_fuzzy(db_session, world):
    # The AI emits "Monticello Standard"; the catalog has "Monticello".
    # Substring fast-path MISSES; the fuzzy fallback finds the SINGLE
    # candidate and resolves. HAND-PROOF: $1,250.00 × 3 = $3,750.00.
    res = assemble_quote_preview(
        db_session,
        world["company_id"],
        lines=[DraftLine(product_ref="Monticello Standard", quantity=3)],
    )
    assert res.ambiguous_products == []
    assert res.unresolved_products == []
    assert res.line_count == 1
    ln = res.context["lines"][0]
    assert ln["description"] == "Monticello"
    assert ln["unit_price_formatted"] == "$1,250.00"
    assert ln["line_total_formatted"] == "$3,750.00"
    assert res.subtotal == Decimal("3750.00")


def test_resolve_product_three_states(db_session, world):
    from app.services.command_bar.quote_preview import resolve_product

    # exact → resolved via the fast path (regression: unchanged behavior)
    r = resolve_product(db_session, world["company_id"], "Monticello")
    assert r.status == "resolved" and r.product.name == "Monticello"

    # qualifier-suffixed → resolved via fuzzy (single candidate)
    r = resolve_product(db_session, world["company_id"], "Monticello Standard")
    assert r.status == "resolved" and r.product.name == "Monticello"

    # nothing close → unresolved (0 candidates clear the threshold)
    r = resolve_product(db_session, world["company_id"], "Zzqqx Nonexistent")
    assert r.status == "unresolved" and r.product is None


@pytest.fixture
def two_variant_world(db_session):
    """A catalog with TWO Monticello variants — the ambiguity case."""
    from app.models.company import Company
    from app.models.product import Product

    db = db_session
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"AMB {suffix}",
        slug=f"amb-{suffix}",
        is_active=True,
    )
    db.add(co)
    db.flush()
    db.add_all(
        [
            Product(
                id=str(uuid.uuid4()),
                company_id=co.id,
                name="Monticello",
                sku=f"MON-{suffix}",
                price=Decimal("1250.00"),
                is_active=True,
                product_line="monticello",
            ),
            Product(
                id=str(uuid.uuid4()),
                company_id=co.id,
                name="Monticello Premium",
                sku=f"MONP-{suffix}",
                price=Decimal("1850.00"),
                is_active=True,
                product_line="monticello",
            ),
        ]
    )
    db.commit()
    yield {"company_id": co.id}

    db.query(Product).filter(Product.company_id == co.id).delete(
        synchronize_session=False
    )
    db.query(Company).filter(Company.id == co.id).delete(
        synchronize_session=False
    )
    db.commit()


def test_ambiguous_multi_variant_refuses(db_session, two_variant_world):
    # THE CORRECTNESS CORE. Catalog has "Monticello" ($1,250) AND
    # "Monticello Premium" ($1,850). Input "Monticello Standard" fuzzy-
    # matches BOTH above the similarity threshold → the resolver REFUSES.
    # A wrong price is worse than no price: NO line, NO subtotal, and the
    # ref is surfaced as ambiguous (NOT as "couldn't find").
    res = assemble_quote_preview(
        db_session,
        two_variant_world["company_id"],
        lines=[DraftLine(product_ref="Monticello Standard", quantity=2)],
    )
    assert res.line_count == 0
    assert res.subtotal_formatted == ""  # no fabricated price
    assert res.unresolved_products == []  # ambiguous, NOT "couldn't find"
    assert len(res.ambiguous_products) == 1
    amb = res.ambiguous_products[0]
    assert amb.product_ref == "Monticello Standard"
    # Both variants surfaced as candidates for the user to disambiguate.
    assert set(amb.candidates) >= {"Monticello", "Monticello Premium"}
    # And crucially: NEITHER price ($1,250 nor $1,850) appears anywhere.
    assert "$1,250.00" not in res.html
    assert "$1,850.00" not in res.html


# ── S-3b: multi-line money math + override + structured per-line ─────
#
# S-2 proved single-line. S-3b's point is MULTIPLE editable lines — fresh
# hand-proof of the multi-line subtotal, qty re-price, per-line override,
# and the structured per-line breakdown the editable core consumes.


def test_multiline_subtotal_across_products(db_session, world):
    # 3-line quote: 2× Monticello ($1,250) + 1× Grave Widget ($500)
    #             + 1× a call-office product.
    # HAND-PROOF (banker's rounding, per-line then summed):
    #   line1 = round_money(2 × 1250.00) = $2,500.00
    #   line2 = round_money(1 ×  500.00) =   $500.00
    #   call-office → "Price on request", EXCLUDED from subtotal
    #   subtotal = 2500.00 + 500.00      = $3,000.00
    res = assemble_quote_preview(
        db_session,
        world["company_id"],
        lines=[
            DraftLine(product_ref="Monticello", quantity=2),
            DraftLine(product_ref="Grave Widget", quantity=1),
            DraftLine(product_ref="Custom Bronze Memorial", quantity=1),
        ],
    )
    assert res.subtotal == Decimal("3000.00")
    assert res.subtotal_formatted == "$3,000.00"
    assert res.has_call_office is True
    assert res.line_count == 3

    # Structured per-line: 1:1 with input, in order, editable-UI-ready.
    assert len(res.lines) == 3
    l0, l1, l2 = res.lines
    assert l0.status == "resolved" and l0.description == "Monticello"
    assert l0.unit_price == "1250.00" and l0.line_total == "2500.00"
    assert l0.product_id is not None  # the editable row keys on this
    assert l1.status == "resolved" and l1.line_total == "500.00"
    assert l2.status == "call_office"
    assert l2.unit_price_formatted == "Price on request"
    assert l2.unit_price is None  # not priced


def test_quantity_edit_reprices_line_and_subtotal(db_session, world):
    two = assemble_quote_preview(
        db_session, world["company_id"],
        lines=[DraftLine(product_ref="Monticello", quantity=2)],
    )
    three = assemble_quote_preview(
        db_session, world["company_id"],
        lines=[DraftLine(product_ref="Monticello", quantity=3)],
    )
    assert two.subtotal == Decimal("2500.00")
    assert two.lines[0].line_total == "2500.00"
    assert three.subtotal == Decimal("3750.00")
    assert three.lines[0].line_total == "3750.00"


def test_per_line_price_override(db_session, world):
    # Director overrides Monticello to $1,200 (catalog is $1,250), qty 2.
    # HAND-PROOF: round_money(2 × 1200.00) = $2,400.00 (NOT catalog $2,500).
    res = assemble_quote_preview(
        db_session,
        world["company_id"],
        lines=[
            DraftLine(
                product_ref="Monticello",
                quantity=2,
                unit_price_override=Decimal("1200.00"),
            )
        ],
    )
    assert res.subtotal == Decimal("2400.00")
    ln = res.lines[0]
    assert ln.unit_price == "1200.00"
    assert ln.line_total == "2400.00"
    assert ln.price_overridden is True


def test_edited_ambiguous_line_refused_in_structured_lines(
    db_session, two_variant_world
):
    # A resolved line + an EDITED ambiguous line. The ambiguous line is
    # refused (no price), excluded from the subtotal, and surfaced in the
    # structured breakdown with its candidates — same as an extracted one.
    res = assemble_quote_preview(
        db_session,
        two_variant_world["company_id"],
        lines=[
            DraftLine(product_ref="Monticello", quantity=1),  # exact → resolves
            DraftLine(product_ref="Monticello Standard", quantity=2),  # ambiguous
        ],
    )
    assert res.subtotal == Decimal("1250.00")  # only the resolved line
    assert len(res.lines) == 2
    assert res.lines[0].status == "resolved"
    assert res.lines[1].status == "ambiguous"
    assert res.lines[1].unit_price is None  # NOT priced (refused)
    assert set(res.lines[1].candidates) >= {"Monticello", "Monticello Premium"}


@pytest.fixture
def mixed_world(db_session):
    """A catalog carrying BOTH ambiguity AND a call-office product — so a
    single quote can exercise a qty-edit line, an ambiguous edited line,
    and a call-office line together (the S-3b combined hand-proof)."""
    from app.models.company import Company
    from app.models.product import Product

    db = db_session
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"MIX {suffix}",
        slug=f"mix-{suffix}",
        is_active=True,
    )
    db.add(co)
    db.flush()
    db.add_all(
        [
            Product(
                id=str(uuid.uuid4()), company_id=co.id, name="Monticello",
                sku=f"MON-{suffix}", price=Decimal("1250.00"),
                is_active=True, product_line="monticello",
            ),
            Product(
                id=str(uuid.uuid4()), company_id=co.id,
                name="Monticello Premium", sku=f"MONP-{suffix}",
                price=Decimal("1850.00"), is_active=True,
                product_line="monticello",
            ),
            Product(
                id=str(uuid.uuid4()), company_id=co.id, name="Grave Widget",
                sku=f"GW-{suffix}", price=Decimal("500.00"), is_active=True,
            ),
            Product(
                id=str(uuid.uuid4()), company_id=co.id,
                name="Custom Bronze Memorial", sku=f"CBM-{suffix}",
                price=None, is_active=True, is_call_office=True,
            ),
        ]
    )
    db.commit()
    yield {"company_id": co.id}

    db.query(Product).filter(Product.company_id == co.id).delete(
        synchronize_session=False
    )
    db.query(Company).filter(Company.id == co.id).delete(
        synchronize_session=False
    )
    db.commit()


def test_combined_3line_qty_edit_ambiguous_and_call_office(
    db_session, mixed_world
):
    # THE S-3b COMBINED HAND-PROOF — one 3-line quote exercising all three
    # editable shapes at once, machine-checked against the endpoint:
    #
    #   line1  Grave Widget      qty 3  (a qty-edit line)
    #            → round_money(3 × 500.00)             = $1,500.00   RESOLVED
    #   line2  "Monticello Standard" qty 2 (edited, ambiguous)
    #            → fuzzy-matches Monticello + Monticello Premium
    #            → REFUSED: no price, EXCLUDED from subtotal
    #   line3  Custom Bronze Memorial qty 1 (call-office)
    #            → "Price on request", EXCLUDED from subtotal
    #
    #   subtotal = 1500.00 (only the one resolved line)  = $1,500.00
    #   NEITHER ambiguous candidate price ($1,250 / $1,850) may appear.
    res = assemble_quote_preview(
        db_session,
        mixed_world["company_id"],
        customer_name="Hopkins Funeral Home",
        lines=[
            DraftLine(product_ref="Grave Widget", quantity=3),
            DraftLine(product_ref="Monticello Standard", quantity=2),
            DraftLine(product_ref="Custom Bronze Memorial", quantity=1),
        ],
    )

    # Subtotal is the single resolved line — refused + call-office excluded.
    assert res.subtotal == Decimal("1500.00")
    assert res.subtotal_formatted == "$1,500.00"
    assert res.has_call_office is True

    # Structured per-line: 1:1 with input, IN ORDER, every state present.
    assert len(res.lines) == 3
    l0, l1, l2 = res.lines
    # line1 — qty-edit resolved
    assert l0.status == "resolved"
    assert l0.description == "Grave Widget"
    assert l0.quantity == 3.0
    assert l0.unit_price == "500.00"
    assert l0.line_total == "1500.00"
    # line2 — edited ambiguous → refused (no price), candidates surfaced
    assert l1.status == "ambiguous"
    assert l1.product_ref == "Monticello Standard"
    assert l1.unit_price is None
    assert l1.line_total is None
    assert set(l1.candidates) >= {"Monticello", "Monticello Premium"}
    # line3 — call-office
    assert l2.status == "call_office"
    assert l2.unit_price is None
    assert l2.unit_price_formatted == "Price on request"

    # A wrong price is worse than no price: no candidate price leaks.
    assert "$1,250.00" not in res.html
    assert "$1,850.00" not in res.html
    # The REAL quote template rendered the one real price (drift guard):
    assert "$1,500.00" in res.html
    assert "QUOTE" in res.html


# ── Price-list reference (tiered display is correct HERE) ─────────────


def test_price_list_reference_tiered_rows(db_session, world):
    from datetime import date

    from app.models.price_list_item import PriceListItem
    from app.models.price_list_version import PriceListVersion
    from app.services.command_bar.price_list_reference import (
        build_price_list_reference,
    )

    ver = PriceListVersion(
        id=str(uuid.uuid4()),
        tenant_id=world["company_id"],
        version_number=1,
        label="Spring 2026",
        status="active",
        effective_date=date(2026, 1, 1),
    )
    db_session.add(ver)
    db_session.flush()
    db_session.add(
        PriceListItem(
            id=str(uuid.uuid4()),
            tenant_id=world["company_id"],
            version_id=ver.id,
            product_name="Monticello",
            standard_price=Decimal("1500.00"),
            contractor_price=Decimal("1350.00"),
            homeowner_price=Decimal("1650.00"),
            unit="each",
        )
    )
    db_session.commit()

    data = build_price_list_reference(
        db_session, world["company_id"], product_refs=["Monticello"]
    )
    assert data["version_label"] == "Spring 2026"
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["on_list"] is True
    # Note these DIFFER from the order-charge price ($1,250) on purpose —
    # the reference surface shows the PUBLISHED list, not the order price.
    assert row["standard_price_formatted"] == "$1,500.00"
    assert row["contractor_price_formatted"] == "$1,350.00"
    assert row["homeowner_price_formatted"] == "$1,650.00"


def test_price_list_reference_product_not_on_list(db_session, world):
    from app.services.command_bar.price_list_reference import (
        build_price_list_reference,
    )

    data = build_price_list_reference(
        db_session, world["company_id"], product_refs=["Grave Widget"]
    )
    # Product resolves but no price-list item → on_list False, dashes.
    assert len(data["rows"]) == 1
    assert data["rows"][0]["on_list"] is False
    assert data["rows"][0]["standard_price_formatted"] == "—"


# ── Endpoint wiring ──────────────────────────────────────────────────


def test_quote_preview_endpoint(world):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    token = create_access_token(
        {"sub": world["user_id"], "company_id": world["company_id"]}
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": world["slug"],
    }
    client = TestClient(app)
    r = client.post(
        "/api/v1/command-bar/quote-preview",
        json={
            "customer_name": "Hopkins FH",
            "lines": [{"product_ref": "Monticello", "quantity": 3}],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subtotal_formatted"] == "$3,750.00"
    assert body["line_count"] == 1
    assert body["has_call_office"] is False
    assert "$1,250.00" in body["html"]


def test_price_list_reference_endpoint(world):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app

    token = create_access_token(
        {"sub": world["user_id"], "company_id": world["company_id"]}
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": world["slug"],
    }
    client = TestClient(app)
    r = client.post(
        "/api/v1/command-bar/price-list-reference",
        json={"products": ["Monticello"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "rows" in body
    assert len(body["rows"]) == 1
    assert body["rows"][0]["product_name"] == "Monticello"
