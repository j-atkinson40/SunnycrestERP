"""Reads for the Opas Product List and Product panes.

⚠️ THE SOURCE OF RECORD IS THE PLATFORM CATALOG, BY RULING (2026-10-06), and the reason
is a measurement rather than a preference: tenant `products` and the platform catalog are
DISJOINT POPULATIONS with nothing joining them.

    products.variant_template_id        0 of 27 populated
    products.sku = variant.sku          0 matches
    products.wilbert_sku = variant.sku  0 matches (wilbert_sku itself 0-populated)

So a pane reading tenant products could show a price and nothing else it wants — no kind,
no specs, no availability, no aliases. A pane reading the catalog can show everything
except price, because NO PRICE COLUMN EXISTS on any platform tier. Price returns when
`variant_template_id` is populated; that is its own piece of work.

⚠️ NULL MEANS NOT ESTABLISHED, SO THE KEY IS OMITTED — never sent as null, never as "". A
caller cannot then render an empty row by accident, which is what the "no empty states
inside the pane" ruling requires. This is the same discipline r196 applied to
`is_manufactured`: an absent value must not be presented as a measured one.

⚠️ READ-ONLY. Writes nothing. Takes `company_id` for the availability lookup only.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

#: Optional keys on a list row, by tier. ⚠️ `option_label` and `sku` are VARIANT-tier;
#: `family_slug` and `product_name` are TEMPLATE-tier. Measured 2026-10-06: none of the
#: four is NULL on any of the 52 active variants, which is why the omission contract needs
#: a constructed subject rather than live data to test it.
_LIST_OPTIONAL: tuple[str, ...] = ("option_label", "sku", "family_slug", "product_name")

#: Detail adds `description`, VARIANT-tier, which IS null for 15 of 52 — the one field in
#: either list that discriminates against live data.
_DETAIL_OPTIONAL: tuple[str, ...] = _LIST_OPTIONAL + ("description",)

#: The spec fields, in the order the pane renders them. Each is omitted when NULL.
#:
#: ⚠️ `spec_source` IS THE MEMBERSHIP MARKER, NOT A DIMENSION — r193 says so in terms:
#: "SO `spec_source` IS THE MEMBERSHIP MARKER, NOT `inside_length_in`", because one family
#: has a spec sheet that records no inside dimensions, and keying membership off a
#: dimension would report it as unmeasured.
_SPEC_FIELDS: tuple[str, ...] = (
    "inside_length_in",
    "inside_width_in",
    "inside_height_in",
    "outside_length_in",
    "outside_width_in",
    "outside_height_in",
    "weight_lb",
)


def present_only(row: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    """The subset of `keys` that `row` actually establishes.

    ⚠️ EXTRACTED 2026-10-06 SO IT CAN BE TESTED WITHOUT THE DATABASE, and the reason is a
    break test that came back green. The omission was inline in two loops; a break aimed at
    one of them left the other intact, and the live data has no NULL in four of the five
    fields, so nothing could tell the difference. A helper with constructed input can.

    Absent, None, "" and whitespace are all NOT ESTABLISHED. Whitespace in particular: a
    name of " " would render as a blank row that looks like a bug in the pane rather than a
    gap in the data.
    """
    out: dict[str, Any] = {}
    for key in keys:
        try:
            value = row[key]
        except (KeyError, IndexError):
            continue
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        out[key] = value
    return out


def list_variants(db: Session) -> list[dict[str, Any]]:
    """Every platform variant, grouped-ready and ordered.

    Ordering: `form`, then the family's `sort_order`, then the variant's own `sort_order`
    — the order already encoded in the catalog rather than one invented here. `tier` is
    the tie-break inside a family, which is how the catalog expresses good/better/best.
    """
    rows = db.execute(text(
        """
        SELECT v.id            AS variant_template_id,
               v.display_name  AS name,
               v.option_label  AS option_label,
               v.sku           AS sku,
               t.form          AS kind,
               t.family_slug   AS family_slug,
               t.display_name  AS product_name,
               -- ⚠️ THE GROUP ORDER IS DERIVED FROM THE PRICE LIST, NOT INVENTED, and this
               -- window is the whole mechanism. `product_families.sort_order` is populated
               -- 1..24 and already encodes the price list's sequence; what it does NOT give
               -- is an order for FORMS, because a family SPANS them (`triune` holds both a
               -- burial_vault and an urn_vault; `graveliner` holds a grave_liner and an urn
               -- vault). So a form's rank is where it FIRST APPEARS walking families in
               -- price-list order. That yields burial_vault, urn_vault, grave_liner, infant,
               -- equipment, urn — and it moves when the price list moves, which an explicit
               -- list in this file would not.
               MIN(f.sort_order) OVER (PARTITION BY t.form) AS form_rank,
               f.sort_order AS family_rank,
               -- `tier` is how the catalog says good/better/best inside a family; it breaks
               -- ties before the numeric order does.
               (COALESCE(v.tier, '') , COALESCE(v.sort_order, 2147483647)) AS variant_rank
          FROM product_variant_templates v
          JOIN product_templates t ON t.id = v.product_template_id
          LEFT JOIN product_families f ON f.slug = t.family_slug
         WHERE v.is_active IS TRUE
         ORDER BY form_rank, family_rank, variant_rank, v.display_name
        """
    )).mappings().all()

    out: list[dict[str, Any]] = []
    for r in rows:
        item: dict[str, Any] = {
            "variant_template_id": r["variant_template_id"],
            "name": r["name"],
            "kind": r["kind"],
        }
        # ⚠️ Omit rather than send null — via `present_only`, which is unit-tested with
        # constructed input. Inline, this was untestable on data that has no NULLs here.
        item.update(present_only(r, _LIST_OPTIONAL))
        out.append(item)
    return out


def variant_detail(
    db: Session, variant_template_id: str, *, company_id: str | None = None
) -> dict[str, Any] | None:
    """One variant, with only the facts that exist.

    Returns None when the id is unknown — the caller turns that into a 404 rather than an
    empty pane.
    """
    row = db.execute(text(
        f"""
        SELECT v.id AS variant_template_id, v.display_name AS name, v.option_label,
               v.sku, v.description,
               t.id AS product_template_id, t.form AS kind, t.family_slug,
               t.display_name AS product_name, t.spec_source, t.spec_asof,
               {', '.join('t.' + c for c in _SPEC_FIELDS)}
          FROM product_variant_templates v
          JOIN product_templates t ON t.id = v.product_template_id
         WHERE v.id = :vid
        """
    ), {"vid": variant_template_id}).mappings().first()
    if row is None:
        return None

    out: dict[str, Any] = {
        "variant_template_id": row["variant_template_id"],
        "name": row["name"],
        "kind": row["kind"],
    }
    out.update(present_only(row, _DETAIL_OPTIONAL))

    # --- Specs: present only if at least one field is non-null -------------------
    specs = present_only(row, _SPEC_FIELDS)
    if specs:
        # ⚠️ Decimals are serialised as strings by the route layer's encoder; the pane
        # renders them verbatim. Formatting is a display decision and is not made here.
        out["specs"] = {k: str(v) for k, v in specs.items()}
        if row["spec_source"] is not None:
            out["specs"]["spec_source"] = row["spec_source"]
        if row["spec_asof"] is not None:
            out["specs"]["spec_asof"] = row["spec_asof"].isoformat()

    # --- Confirmed aliases ------------------------------------------------------
    aliases = [
        a["alias_text"]
        for a in db.execute(text(
            "SELECT alias_text FROM platform_product_aliases "
            "WHERE variant_template_id = :vid AND is_confirmed IS TRUE "
            "ORDER BY alias_text"
        ), {"vid": variant_template_id}).mappings()
    ]
    if aliases:
        out["aliases"] = aliases

    # --- Personalization availability -------------------------------------------
    offered = _offered_questions(db, variant_template_id, company_id)
    if offered:
        out["personalization"] = offered

    return out


def _offered_questions(
    db: Session, variant_template_id: str, company_id: str | None
) -> list[dict[str, Any]]:
    """The questions this vault OFFERS, for this tenant. Empty when none.

    ⚠️ OFFERED ONLY — NOT_CONFIGURED IS NOT DATA. `read_availability` has three states,
    and NOT_CONFIGURED means the licensee has said nothing. The capture engine treats that
    as "ask"; a read-only pane has nothing to show for it, and rendering a pill from it
    would assert a capability nobody recorded.

    ⚠️ MEASURED 2026-10-06: THIS RETURNS EMPTY FOR EVERY VARIANT TODAY. Of 3
    `wilbert_program_enrollments` rows, all 3 carry a `personalization_config` and NONE
    has an `availability` key. The lookup is wired to the location the model's own comment
    rules it into — `wilbert_program_enrollments.personalization_config.availability` —
    so the pill lights up the day that key is populated, and renders nothing until then.
    That is the honest state, not a stub.
    """
    if company_id is None:
        return []
    from app.services.personalization.availability import (
        AvailabilityState,
        read_availability,
    )
    from app.services.personalization.questions import QUESTIONS

    config = db.execute(text(
        "SELECT personalization_config FROM wilbert_program_enrollments "
        "WHERE company_id = :c AND personalization_config IS NOT NULL LIMIT 1"
    ), {"c": company_id}).scalar()
    if not isinstance(config, dict):
        return []

    out: list[dict[str, Any]] = []
    for q in QUESTIONS:
        availability = read_availability(config, variant_template_id, q.question_id)
        if availability.state is AvailabilityState.OFFERED:
            out.append({
                "question_id": q.question_id,
                "label": q.display_label,
                "permitted_answers": list(availability.permitted_answers),
            })
    return out
