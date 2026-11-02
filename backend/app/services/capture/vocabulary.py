"""The words a director is likely to type, gathered once when capture opens.

⚠️ FETCHED ONCE AND MATCHED CLIENT-SIDE, BY RULING (James, 2026-10-16): "Matching is
client-side only... keystroke latency must not depend on the network." A completion
that asks the server per keystroke is a completion that stutters on a bad connection,
and the bar is the one surface where a director is mid-sentence.

⚠️ IT IS THE TENANT'S VOCABULARY, NOT THE PLATFORM'S, AND THAT IS WHAT MAKES THE
RULING'S OWN EXAMPLE WORK. Measured 2026-10-16: the platform catalog holds BOTH
`Monticello Burial Vault` and `Monticello Urn Vault`, so "monti" is ambiguous across
the catalog and — by the dispatch's own tie-break — would offer nothing, contradicting
the verify line "'monti' offers 'cello Burial Vault'". Scoped to what sunnycrest
actually carries, only the burial vault remains and the completion is unambiguous.

⚠️ AND IT IS ALSO THE MORE CORRECT SCOPE. Completing to a vault the tenant does not
sell produces an order that Approve then refuses with "has no product on this tenant"
— the bar would be suggesting the thing the next screen rejects.

⚠️ KINDS, AND TWO OF THEM FILL THE VAULT ROW. `vault` and `vault_alias` are catalog
VARIANTS; `product` is what the TENANT calls the thing it stocks, which is usually the
family rather than the variant ("Venetian", not "White Venetian Burial Vault"). A
product name resolves through the ordinary product resolver like any other name, so a
family that maps to several variants ASKS. Ranked below the variants — see
`prefix_resolve` — so a prefix that already reaches a variant is unaffected.

⚠️ PLATFORM TERMS ARE STILL INCLUDED, RANKED BELOW. A director may legitimately name a
vault the tenant has not stocked; the capture allows it and Approve says so clearly.
What the tenant carries simply wins a tie.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.capture.schema import EQUIPMENT_PACKAGES, SERVICE_LOCATIONS
from app.services.capture.vault_form import (
    FormResolver,
    admits_name,
    is_vault_form,
)

#: The chairs phrasings the bar may complete to, in the order a director is likeliest
#: to want them. ⚠️ HELD BESIDE `typed_extraction._CHAIRS_BARE` AND
#: `_CHAIRS_EXTRA_BARE` BY `test_the_vocabulary.py`, so a phrasing the extractor learns
#: cannot stay un-offerable, and one the bar offers cannot be un-understood.
CHAIRS_PHRASES: tuple[str, ...] = ("chairs", "extra chairs")


@dataclass(frozen=True)
class Term:
    """One completable phrase."""

    #: What the bar completes TO, in the office's own capitalisation.
    text: str
    #: Which row it would fill — shown as context, never completed into.
    kind: str
    #: True when this tenant carries it. Breaks ties; see the module docstring.
    carried: bool = False
    #: A disambiguator shown beside the term, e.g. a cemetery's town.
    note: str | None = None
    #: The catalog form (`burial_vault`, `urn_vault`, ...) for vault terms.
    #:
    #: ⚠️ CARRIED SO THE CLIENT CAN APPLY THE FORM DEFAULT James RULED ON 2026-10-16.
    #: The ghost needs to know that two matches differ ONLY by form; the display name
    #: alone cannot tell it, because "Monticello Burial Vault" and "Monticello Urn
    #: Vault" differ by two words and nothing marks which word is the form.
    form: str | None = None


def build_vocabulary(db: Session, tenant_id: str) -> list[Term]:
    """Everything the bar may complete, in no particular order."""
    out: list[Term] = []
    seen: set[tuple[str, str]] = set()

    def add(value: str | None, kind: str, carried: bool = False,
            note: str | None = None, form: str | None = None):
        v = (value or "").strip()
        if not v:
            return
        key = (kind, v.casefold())
        if key in seen:
            return
        seen.add(key)
        out.append(Term(text=v, kind=kind, carried=carried, note=note, form=form))

    # ── the parties ────────────────────────────────────────────────────
    for r in db.execute(
        text("SELECT name FROM company_entities WHERE company_id = :t"), {"t": tenant_id}
    ):
        add(r.name, "funeral_home", carried=True)

    # ⚠️ THE TOWN RIDES AS A NOTE, NOT AS PART OF THE TERM. "cemeteries with town" in
    # the dispatch is about showing which St. Mary's is meant; folding it into the
    # completable text would make "st m" complete to "ary's Cemetery, Skaneateles",
    # which is not what anybody types.
    for r in db.execute(
        text("SELECT name, city FROM cemeteries WHERE company_id = :t AND is_active"),
        {"t": tenant_id},
    ):
        add(r.name, "cemetery", carried=True, note=r.city)

    # ── the catalog: what the tenant stocks, then the platform's names ──
    carried_names = {
        (r.name or "").casefold()
        for r in db.execute(
            text("SELECT name FROM products WHERE company_id = :t AND is_active"),
            {"t": tenant_id},
        )
    }
    # ⚠️ ONLY THE FORMS THAT CAN BE A VAULT, SINCE 2026-11-02 (ruling A/C). This query
    # is the PLATFORM catalogue and it has no company filter on purpose —
    # `product_variant_templates` is platform data, not tenant data, so there is no
    # tenant to filter it by; what it needed was a FORM filter, which it never had.
    # Measured 2026-11-02: it was emitting 6 `equipment` and 9 `urn` variants as kind
    # `vault`, and `KINDS_VAULT` then let the prefix pass resolve them into the VAULT
    # row. `Graveside Chairs` was one of the six.
    for r in db.execute(
        text(
            "SELECT DISTINCT v.display_name, t.form "
            "FROM product_variant_templates v "
            "JOIN product_templates t ON t.id = v.product_template_id "
            "WHERE v.display_name IS NOT NULL"
        )
    ):
        if not is_vault_form(r.form):
            continue
        add(r.display_name, "vault",
            carried=r.display_name.casefold() in carried_names, form=r.form)

    # ── the tenant's own product names ─────────────────────────────────
    # ⚠️ RULED BY JAMES 2026-10-21: "People say 'a Venetian', not 'a White Venetian
    # Burial Vault'." The catalog spells those variants `White Venetian Burial Vault`
    # and `Gold Venetian Burial Vault`, so "venet" is a prefix of NEITHER and reached
    # nothing — in the ghost as well as the extractor. A tenant's `products` row is
    # named the way the office talks, so it is the route to the family.
    #
    # ⚠️ IT WAS ALREADY READ HERE AND THROWN AWAY. `carried_names` above reads the same
    # table purely to decide a boolean; the NAMES went nowhere. One query, one extra
    # loop.
    #
    # ⚠️ RANKED BELOW THE VARIANTS, AND THAT RANKING IS WHAT KEEPS "monti" WORKING.
    # See `prefix_resolve`: a product-name match is dropped whenever a variant or alias
    # match exists. Without it, "monti" on sunnycrest would match the carried variant
    # `Monticello Burial Vault` AND the product `Monticello Burial Vault`-family stem,
    # two different texts, and go from resolving to ASKING — a regression on the
    # phrasing James had just confirmed working. Measured both ways.
    # ⚠️ AND ONLY THE ONES THAT CAN BE A VAULT, SINCE 2026-11-02. James: *"Ghost
    # vocabulary excludes product names that are billing lines; chairs words come from
    # the chairs vocabulary."* Kind `product` is in `KINDS_VAULT` AND in the ghost's
    # `INTERIOR_KINDS`, so an unfiltered tenant product name was completable at any
    # interior word and resolvable into the VAULT row. That is how typing "chairs"
    # ghost-completed to `Extra Chairs (Over 8)` — measured, suffix `" (Over 8)"`, a
    # price-list overage name offered to a director mid-sentence.
    #
    # ⚠️ NOTHING COMPLETABLE IS LOST BY THIS. The bundles are already here as kind
    # `equipment` from `EQUIPMENT_PACKAGES` below — `Full Equipment`, `Tent Only`,
    # `Lowering Device Only`, `Vault Placer` — which is the vocabulary that actually
    # fills the equipment row. Measured on Sunnycrest's eleven products: the four real
    # vaults stay as kind `product`, and the seven that go are the five bundles (still
    # present as `equipment`), `Extra Chairs (Over 8)` (now the chairs vocabulary
    # below) and `Graveside Setup Service`, which no field captures.
    #
    # ⚠️ ONE RESOLVER FOR THE WHOLE LOOP, NOT ONE PER NAME. `FormResolver` exists
    # because exactly this shape — `form_of` in a loop — put twenty-five catalogue
    # index builds behind a blocking latency gate once already.
    forms = FormResolver(db, tenant_id)
    for r in db.execute(
        text(
            "SELECT name FROM products WHERE company_id = :t AND is_active "
            "AND name IS NOT NULL"
        ),
        {"t": tenant_id},
    ):
        if not admits_name(forms, r.name):
            continue
        add(r.name, "product", carried=True)

    # ⚠️ ALIASES ARE INCLUDED BECAUSE THEY ARE THE ONLY ROUTE TO SOME VARIANTS —
    # `product_name_resolver.build_index` says so in terms, naming `Veteran`, `SST`
    # and `Basic Gray`. A completion list missing them would be unable to finish a
    # word the engine can resolve.
    # ⚠️ FILTERED BY THE VARIANT'S FORM SINCE 2026-11-02, AND THE TERM STILL CARRIES NO
    # FORM OF ITS OWN. An alias is a nickname and may point at several variants —
    # `Veteran` reaches both the burial and the urn Triune — so there is no single form
    # to attach, and attaching the first one would feed the ghost's form-default rule a
    # fact that is only half true. What CAN be done is refuse an alias whose variant is
    # not a vault, which closes the door by construction.
    #
    # ⚠️ MEASURED BEFORE IT SHIPPED: all 56 confirmed aliases point at vault forms, so
    # this filter removes nothing today. It is here so the data cannot open a door
    # later — an alias confirmed against an equipment variant would otherwise be
    # completable into the VAULT row with no form anywhere to catch it.
    for r in db.execute(
        text(
            "SELECT a.alias_text, v.display_name, t.form "
            "FROM platform_product_aliases a "
            "JOIN product_variant_templates v ON v.id = a.variant_template_id "
            "JOIN product_templates t ON t.id = v.product_template_id "
            "WHERE a.is_confirmed IS TRUE"
        )
    ):
        if not is_vault_form(r.form):
            continue
        add(r.alias_text, "vault_alias",
            carried=(r.display_name or "").casefold() in carried_names,
            note=r.display_name)

    # ── the fixed vocabularies, from the schema rather than retyped ────
    for _slug, label in EQUIPMENT_PACKAGES:
        add(label, "equipment", carried=True)

    # ⚠️ THE CHAIRS WORDS, FROM THE EXTRACTOR'S OWN VOCABULARY, BY RULING (James,
    # 2026-11-02): *"chairs words come from the chairs vocabulary, not the Extra Chairs
    # product."* Before this the only chairs term in the bar was the price-list name
    # `Extra Chairs (Over 8)`, so the ghost completed toward a billing line — and once
    # that name is correctly excluded above, a director typing "chai" would have been
    # offered nothing at all. This is the other half of the same ruling.
    #
    # ⚠️ A SEPARATE KIND, AND IT IS DELIBERATELY NOT IN `KINDS_VAULT`. The chairs row
    # is filled by `typed_extraction._chairs`, which reads these same phrasings; the
    # prefix pass must not try to resolve "chairs" as a product name again.
    #
    # ⚠️ THE TWO PHRASES MEAN DIFFERENT THINGS AND BOTH ARE OFFERED. "chairs" is the
    # normal chairs a family bundle includes; "extra chairs" is an overage. That is the
    # distinction ruling B turns on, so the bar offers both rather than completing one
    # into the other.
    for phrase in CHAIRS_PHRASES:
        add(phrase, "chairs", carried=True)
    for loc in SERVICE_LOCATIONS:
        add(loc.replace("_", " ").title(), "service_location", carried=True)

    # ⚠️ PERSONALIZATION PHRASES ARE THE WORDS THE OFFICE SAYS, and they are the one
    # group with no table to read. They come from the extractor's own vocabulary so
    # the bar cannot offer a phrase the engine would not understand.
    for phrase in (
        "Nameplate only", "Nameplate and cover emblem", "Cover emblem only",
        "Life's Reflections", "Legacy Series print", "Vinyl",
    ):
        add(phrase, "personalization", carried=True)

    for r in db.execute(
        text("SELECT DISTINCT print_name FROM legacy_prints WHERE print_name IS NOT NULL")
        if _has_table(db, "legacy_prints") else text("SELECT NULL AS print_name WHERE false")
    ):
        add(r.print_name, "legacy_print", carried=True)

    return out


def _has_table(db: Session, name: str) -> bool:
    """⚠️ CHECKED RATHER THAN ASSUMED. The Legacy print catalogue is a later arc's
    table and is absent on some databases; a vocabulary endpoint that 500s because one
    optional source is missing would take the whole bar's completion down."""
    return bool(
        db.execute(
            text("SELECT to_regclass(:n)"), {"n": f"public.{name}"}
        ).scalar()
    )
