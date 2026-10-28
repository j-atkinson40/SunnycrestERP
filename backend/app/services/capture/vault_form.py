"""Is this vault a burial vault or an urn vault — and therefore, is this a cremation?

James's dispatch of 2026-10-27, clause 2: *"An urn vault marks the order a
cremation: the pane shows a 'Cremation' chip and the equipment question offers the
cremation setups from the catalog."*

So something has to turn a captured value — `"Monticello Burial Vault"`,
`"Urn Vault - Standard"` — into a form. This is that something, and it is a LADDER
rather than a lookup because the designed path reaches nothing today.

⚠️ MEASURED ON PRODUCTION BEFORE IT WAS WRITTEN, AND THE MEASUREMENT IS THE DESIGN.
`product_templates.form` is exactly the right column with exactly the right
vocabulary (`urn_vault`, `burial_vault`, `grave_liner`, `urn`, `equipment`,
`infant`), and `products.variant_template_id` is the declared way to reach it.

⚠️ CORRECTED 2026-10-28. This paragraph read **"populated on 0 of 39 rows. Both
tenants: 0 of 10, 0 of 25"** — and the 39 never added up (10 + 25 = 35, and the 25
are testco, which is dev, not production). It is also no longer the state: James's
rulings of 2026-10-28 linked Sunnycrest's `Monticello Burial Vault`,
`Continental Burial Vault` and a new `Continental 34"`, so the designed path now
reaches three rows on production and zero on dev. `personalization_tier` is still
NULL everywhere and sunnycrest still has no product categories. See
`docs/investigations/2026-10-27-is-this-vault-a-cremation.md` and
`docs/investigations/2026-10-28-linking-sunnycrest-to-the-catalogue.md`.

⚠️ THE TENANT LINK IS FIRST. It is the designed path, and the moment a tenant's
products are linked it is authoritative — the lower rungs stop being consulted. A
tenant that has said "this product IS that catalogue variant" has settled the
question, and a name match must not overrule it.

⚠️ AND THIS FILE SAID EXACTLY THAT WHILE DOING THE OPPOSITE, FOR A DAY, BECAUSE I
BROKE IT. The sentence above is close to the original wording; the ladder then
acquired `_step_name_resolver` as a new first rung during the guided-capture slice,
in front of the link it was written to protect — so a linked product WAS "a correct
answer arriving and being overruled by a name match", which is the thing the
paragraph forbids, in the file that forbids it. Restored to the documented order by
James's ruling of 2026-10-28; the precedence now lives in ONE place, `variant_for`,
rather than being re-expressed at each of the four call sites that need it.

⚠️ AND STEP 4 IS THE ONE THAT CARRIES SUNNYCREST. `Urn Vault - Standard` matches no
platform row: the platform's twelve urn vaults are `Monticello Urn Vault`,
`Salute Urn Vault`, `Universal Urn Vault (Cream & Gold)` and so on. So on the tenant
James walks, the only thing saying this order is a cremation is the product's own
name. That is a weak basis and this module says so rather than implying otherwise.

⚠️ IT IS NOT THE ONE-WORD STOPLIST THAT WAS RULED OUT. The "Smith It" ruling
(2026-10-26) was *"fix it in the name rules (not a one-word stoplist)"* — about the
NAME EXTRACTOR, where a stoplist would paper over a grammar gap. Here there is no
richer structure being bypassed: the recorded name is the last place a product's
category lives when nothing else records it, and the alternative is answering
"unknown" for every vault on the tenant in use.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

#: The `product_templates.form` vocabulary, measured 2026-10-27 — six values, in
#: descending row count. Declared as constants so a typo is an AttributeError here
#: rather than a silent miss at a comparison.
FORM_URN = "urn"
FORM_BURIAL_VAULT = "burial_vault"
FORM_URN_VAULT = "urn_vault"
FORM_EQUIPMENT = "equipment"
FORM_GRAVE_LINER = "grave_liner"
FORM_INFANT = "infant"

#: ⚠️ THE FORMS THAT MEAN CREMATION, AND `urn` IS ONE OF THEM. An `urn` is the urn
#: itself and an `urn_vault` is the vault it goes into; either on an order means the
#: family chose cremation. Keeping only `urn_vault` would read an urn-only order as a
#: burial.
CREMATION_FORMS = frozenset({FORM_URN, FORM_URN_VAULT})

#: The forms a product must have to be offerable as the VAULT on an order.
#:
#: ⚠️ ADDED AFTER A PRODUCTION PROBE OFFERED "Vault Placer" AS A VAULT. The pills'
#: catalogue fallback matched `lower(name) LIKE '%vault%'`, which is true of a piece of
#: graveside equipment, and James would have seen it at ⌥4 under "Which vault?".
#:
#: ⚠️ `urn` IS DELIBERATELY NOT HERE WHILE `urn_vault` IS. An urn is what the ashes go
#: in; an urn VAULT is what the urn goes in, and the field asks for the second. A
#: tenant that sells both would otherwise offer eight urns under "Which vault?".
#:
#: ⚠️ AND `infant` AND `grave_liner` ARE BOTH IN, because both are the thing that goes
#: in the grave — a Graveliner is the answer to "which vault" even though it is not
#: called one, which is exactly why this is a form set rather than a name test.
VAULT_FORMS = frozenset({FORM_BURIAL_VAULT, FORM_URN_VAULT, FORM_GRAVE_LINER, FORM_INFANT})

#: ⚠️ THE PLATFORM CATEGORY NAMES, for step 3. `product_catalog_templates.category`
#: holds exactly three values, measured: 'Burial Vaults' (19), 'Urn Vaults' (12),
#: 'Cemetery Equipment' (6).
CATEGORY_FORMS: dict[str, str] = {
    "urn vaults": FORM_URN_VAULT,
    "burial vaults": FORM_BURIAL_VAULT,
    "cemetery equipment": FORM_EQUIPMENT,
}

#: How each step answered, carried alongside the form so a caller — and a test — can
#: tell a measured answer from a guess at the name.
VIA_NAME_RESOLVER = "name_resolver"
VIA_TENANT_LINK = "tenant_variant_link"
VIA_PLATFORM_TEMPLATE = "platform_template_name"
VIA_PLATFORM_CATALOG = "platform_catalog_name"
VIA_TENANT_CATEGORY = "tenant_category"
VIA_RECORDED_NAME = "recorded_name"

#: ⚠️ THE WEAKEST STEP IS NAMED so a caller can refuse to act on it if a later ruling
#: says it should. Nothing refuses it today; the chip is shown on it.
WEAKEST = VIA_RECORDED_NAME


def _key(value: object) -> str:
    """Squeeze a product name for comparison: lowercase, alphanumerics and spaces.

    ⚠️ PUNCTUATION GOES RATHER THAN BEING NORMALISED. `Urn Vault - Standard` and
    `Universal Urn Vault (Cream & Gold)` differ from their platform spellings by
    hyphens, parentheses and an ampersand; comparing those literally would miss rows
    that are plainly the same product.
    """
    squeezed = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", squeezed).strip()


class VaultForm:
    """A vault's form, and how it was established.

    ⚠️ A CLASS RATHER THAN A BARE STRING BECAUSE THE PROVENANCE IS LOAD-BEARING. The
    four steps are not equally trustworthy — one is a declared link and one is two
    words in a product name — and a caller that cannot tell them apart cannot report
    honestly or be tested on the difference.
    """

    __slots__ = ("form", "via")

    def __init__(self, form: str | None, via: str | None) -> None:
        self.form = form
        self.via = via

    @property
    def is_cremation(self) -> bool:
        """⚠️ FALSE WHEN THE FORM IS UNKNOWN, NOT None. An order whose vault cannot be
        placed is not thereby a cremation, and a tri-state here would push the
        uncertainty into every caller to re-decide. `via is None` says "we could not
        tell" for anyone who needs it."""
        return self.form in CREMATION_FORMS

    @property
    def is_known(self) -> bool:
        return self.via is not None

    def __repr__(self) -> str:  # pragma: no cover - diagnostics
        return f"VaultForm(form={self.form!r}, via={self.via!r})"


UNKNOWN = VaultForm(None, None)


def _step_name_resolver(db: Session, vault: object) -> str | None:
    """The catalogue's own resolver — `product_name_resolver` — asked first.

    ⚠️ THIS STEP WAS ADDED AFTER MEASURING, AND IT EXISTS BECAUSE THE PLATFORM ALREADY
    HAS AN ANSWER I WAS ABOUT TO DUPLICATE. `resolve_schema` takes a `vault_form`
    argument and `typed_extraction` already fills it from
    `resolve(index, phrase).candidates[0].form`. Writing a second detector beside that
    would be two answers to one question, which is the thing this codebase keeps
    finding and paying for.

    ⚠️ AND IT ANSWERS MORE OFTEN THAN ITS EXISTING CALLER DOES, deliberately.
    `typed_extraction` takes a form only when the phrase resolves to ONE variant, with
    a correct warrant: *"An ambiguous set can span forms ('Graveliner' spans
    grave_liner and urn_vault), so a form read off candidates[0] would be whichever
    the sort put first."* That is right about SPANNING sets and too strict about
    AGREEING ones. Measured on production: `Continental Burial Vault` returns TWO
    candidates — the 34-inch and the standard, which differ only by size — and both
    are `burial_vault`. Abstaining there discards an answer the catalogue is unanimous
    about.

    So the rule is unanimity, not uniqueness: every candidate must agree on the form.
    `Graveliner` (5 candidates spanning two forms) still abstains, which is the case
    the original warrant was protecting.

    ⚠️ IT DOES NOT CHANGE `typed_extraction`'s OWN BEHAVIOUR. That caller feeds
    `resolve_schema`, where a form decides which personalization questions APPLY, and
    loosening it there is a separate ruling with a different blast radius. This module
    answers "is this a cremation", and reported here the stricter rule simply means
    fewer answers.
    """
    phrase = str(vault or "").strip()
    if not phrase:
        return None
    try:
        from app.services.product_name_resolver import build_index
        from app.services.product_name_resolver import resolve as resolve_vault

        resolution = resolve_vault(build_index(db), phrase)
    except Exception:  # pragma: no cover - the ladder continues without it
        return None
    forms = {c.form for c in (resolution.candidates or ()) if getattr(c, "form", None)}
    if len(forms) == 1:
        return str(next(iter(forms)))
    return None


def _link_lookup(
    db: Session, tenant_id: str, name_key: str
) -> tuple[str | None, str | None]:
    """The designed path: the tenant's own product, linked to a catalogue variant.

    Returns `(variant_template_id, form)` — BOTH, because the two consumers of this
    link want different halves and asking twice would be two answers to one question.
    The form answers "is this a cremation"; the variant id is what personalization
    availability is keyed by.

    ⚠️ THE JOIN IS INNER ON `variant_template_id`, so an unlinked product cannot
    appear in these rows at all. That is what makes "unlinked behaves exactly as
    today" true by construction rather than by a guard someone has to remember.
    """
    from app.models.product import Product
    from app.models.product_template import ProductTemplate
    from app.models.product_variant_template import ProductVariantTemplate

    rows = db.execute(
        select(Product.name, Product.variant_template_id, ProductTemplate.form)
        .join(ProductVariantTemplate,
              ProductVariantTemplate.id == Product.variant_template_id)
        .join(ProductTemplate,
              ProductTemplate.id == ProductVariantTemplate.product_template_id)
        .where(Product.company_id == tenant_id)
    ).all()
    for product_name, variant_id, form in rows:
        if _key(product_name) == name_key:
            return (str(variant_id) if variant_id else None,
                    str(form) if form else None)
    return (None, None)


def _step_tenant_link(db: Session, tenant_id: str, name_key: str) -> str | None:
    """The form half of `_link_lookup`, kept as a named rung for the ladder."""
    return _link_lookup(db, tenant_id, name_key)[1]


def _step_platform_template(db: Session, name_key: str) -> str | None:
    """A platform template's own display name — `Monticello Urn Vault` and the rest."""
    from app.models.product_template import ProductTemplate

    rows = db.execute(
        select(ProductTemplate.display_name, ProductTemplate.form)
    ).all()
    for display_name, form in rows:
        if form and _key(display_name) == name_key:
            return str(form)
    return None


def _step_platform_catalog(db: Session, name_key: str) -> str | None:
    """The platform catalogue's product name, mapped through its category."""
    from app.models.product_catalog_template import ProductCatalogTemplate

    rows = db.execute(
        select(ProductCatalogTemplate.product_name, ProductCatalogTemplate.category)
    ).all()
    for product_name, category in rows:
        if _key(product_name) != name_key:
            continue
        mapped = CATEGORY_FORMS.get(_key(category))
        if mapped:
            return mapped
    return None


def _step_tenant_category(db: Session, tenant_id: str, name_key: str) -> str | None:
    """The tenant's own filing of its own product.

    ⚠️ THIS STEP EXISTS BECAUSE A PROBE AGAINST PRODUCTION FOUND THE LADDER ANSWERING
    NOTHING ON TESTCO — which is the tenant the dispatch names for verifying the urn
    path end to end. Testco's vaults are bare family names (`Monticello`,
    `Continental`, `Salute`, `Venetian`, `Monarch`, `Tribute`), so they match no
    platform product name and contain no "vault" word. 20 of 25 returned `None`.

    ⚠️ AND A BARE FAMILY NAME IS GENUINELY AMBIGUOUS AT THE PLATFORM TIER, which is
    why this reads the TENANT's category rather than the family. `monticello` has TWO
    platform templates — one `burial_vault`, one `urn_vault` — so "Monticello" alone
    cannot be resolved there and should not be. Testco files its own Monticello under
    `Burial Vaults - Single Reinforced`, which is an answer about testco's product.

    ⚠️ A PREFIX MATCH, NOT AN EQUALITY. Measured category names carry a reinforcement
    suffix: `Burial Vaults - Double Reinforced`, `- Non Reinforced`, `- Single
    Reinforced`, `- Triple Reinforced`. Matching exactly would miss all four.
    """
    from app.models.product import Product
    from app.models.product_category import ProductCategory

    rows = db.execute(
        select(Product.name, ProductCategory.name)
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .where(Product.company_id == tenant_id)
    ).all()
    for product_name, category_name in rows:
        if _key(product_name) != name_key:
            continue
        category_key = _key(category_name)
        for prefix, form in CATEGORY_FORMS.items():
            if category_key.startswith(prefix):
                return form
    return None


#: ⚠️ EQUIPMENT WORDS THE LAST STEP MUST NOT READ AS A VAULT, and a production probe
#: is why this exists. `Vault Placer` — a piece of graveside equipment — contains the
#: word "vault", so the name step claimed `burial_vault` for it.
#:
#: ⚠️ IT IS OUT OF DOMAIN RATHER THAN WRONG, strictly: `form_of` is asked about the
#: value of the VAULT field, and nobody captures "Vault Placer" there. But a function
#: that answers confidently about something it was not asked about is a function whose
#: next caller inherits a wrong answer, and the probe that surfaced it was not looking
#: for it. Narrowed rather than documented away.
_NOT_A_VAULT = ("placer", "lowering device", "tent", "chairs", "grass", "setup service")


def _step_recorded_name(name_key: str) -> str | None:
    """The product's own name, which is all sunnycrest has.

    ⚠️ ORDER MATTERS WITHIN THIS STEP AND IT IS NOT ALPHABETICAL. `Monticello Urn
    Vault` contains both "urn vault" and "vault"; the urn test runs first so the more
    specific reading wins. Reversing these two lines reads every urn vault as a
    burial vault, and `test_vault_form.py` holds that ordering by name.
    """
    if any(word in name_key for word in _NOT_A_VAULT):
        return None
    if "urn" in name_key:
        return FORM_URN_VAULT
    if "graveliner" in name_key or "grave liner" in name_key:
        return FORM_GRAVE_LINER
    if "vault" in name_key:
        return FORM_BURIAL_VAULT
    return None


class FormResolver:
    """`form_of` for many names, with the expensive reads done once.

    ⚠️ THIS EXISTS BECAUSE `form_of` IS FIVE TABLE READS AND I PUT IT IN A LOOP. The
    vault pills' catalogue fallback calls it per product to exclude non-vaults, and
    `build_index` alone is a full join over the variant catalogue and the alias table.
    Twenty-five products meant twenty-five index builds — on `_guided`, which runs on
    EVERY capture read, behind a BLOCKING latency gate.

    ⚠️ AND THE REGRESSION WAS FOUND BY A GATE RUN GOING FROM 0 ERRORS TO 10 AT THE SAME
    12% MARK, not by review. The per-product call read correctly and was the obvious
    way to write it.

    ⚠️ SCOPED TO ONE REQUEST, DELIBERATELY NOT MEMOIZED ON THE SESSION. A catalogue
    read cached across requests would serve a stale answer after a product is added,
    and "the vault I just created is not offered" is a worse failure than a slow read.
    """

    __slots__ = ("_db", "_tenant_id", "_index", "_templates", "_catalog",
                 "_tenant_links", "_tenant_categories", "_answers")

    def __init__(self, db: Session, tenant_id: str) -> None:
        self._db = db
        self._tenant_id = tenant_id
        self._index = None
        self._templates: dict[str, str] | None = None
        self._catalog: dict[str, str] | None = None
        self._tenant_links: dict[str, str] | None = None
        self._tenant_categories: dict[str, str] | None = None
        self._answers: dict[str, VaultForm] = {}

    # ⚠️ EACH TABLE IS READ ON FIRST NEED RATHER THAN IN `__init__`, so a caller that
    # only ever asks about a full platform name pays for the resolver and nothing else.
    # The ladder short-circuits, and most names stop at step 0.
    def _idx(self):
        if self._index is None:
            try:
                from app.services.product_name_resolver import build_index
                self._index = build_index(self._db)
            except Exception:  # pragma: no cover - the ladder continues without it
                self._index = False
        return self._index

    def _tmpl(self) -> dict[str, str]:
        if self._templates is None:
            from app.models.product_template import ProductTemplate
            self._templates = {
                _key(name): str(form)
                for name, form in self._db.execute(
                    select(ProductTemplate.display_name, ProductTemplate.form)
                ).all()
                if form and name
            }
        return self._templates

    def _cat(self) -> dict[str, str]:
        if self._catalog is None:
            from app.models.product_catalog_template import ProductCatalogTemplate
            out: dict[str, str] = {}
            for name, category in self._db.execute(
                select(ProductCatalogTemplate.product_name,
                       ProductCatalogTemplate.category)
            ).all():
                mapped = CATEGORY_FORMS.get(_key(category))
                if mapped and name:
                    out[_key(name)] = mapped
            self._catalog = out
        return self._catalog

    def _links(self) -> dict[str, str]:
        if self._tenant_links is None:
            from app.models.product import Product
            from app.models.product_template import ProductTemplate
            from app.models.product_variant_template import ProductVariantTemplate
            self._tenant_links = {
                _key(name): str(form)
                for name, form in self._db.execute(
                    select(Product.name, ProductTemplate.form)
                    .join(ProductVariantTemplate,
                          ProductVariantTemplate.id == Product.variant_template_id)
                    .join(ProductTemplate,
                          ProductTemplate.id == ProductVariantTemplate.product_template_id)
                    .where(Product.company_id == self._tenant_id)
                ).all()
                if form and name
            }
        return self._tenant_links

    def _categories(self) -> dict[str, str]:
        if self._tenant_categories is None:
            from app.models.product import Product
            from app.models.product_category import ProductCategory
            out: dict[str, str] = {}
            for name, category_name in self._db.execute(
                select(Product.name, ProductCategory.name)
                .join(ProductCategory, ProductCategory.id == Product.category_id)
                .where(Product.company_id == self._tenant_id)
            ).all():
                if not name:
                    continue
                category_key = _key(category_name)
                for prefix, form in CATEGORY_FORMS.items():
                    if category_key.startswith(prefix):
                        out[_key(name)] = form
                        break
            self._tenant_categories = out
        return self._tenant_categories

    def form_of(self, vault: object) -> VaultForm:
        """The same ladder as the module function, memoised per name."""
        name_key = _key(vault)
        if not name_key:
            return UNKNOWN
        cached = self._answers.get(name_key)
        if cached is not None:
            return cached

        found: VaultForm = UNKNOWN
        # ⚠️ THE TENANT LINK IS CHECKED FIRST HERE TOO, and the two implementations of
        # this ladder must not drift — `test_the_two_form_ladders_AGREE` pins it.
        # Before James's ruling of 2026-10-28 both asked the name resolver first.
        link = self._links().get(name_key)
        if link is not None:
            found = VaultForm(link, VIA_TENANT_LINK)
        index = self._idx()
        if not found.is_known and index is not False and index is not None:
            try:
                from app.services.product_name_resolver import resolve as resolve_vault
                resolution = resolve_vault(index, str(vault).strip())
                forms = {
                    c.form for c in (resolution.candidates or ())
                    if getattr(c, "form", None)
                }
                if len(forms) == 1:
                    found = VaultForm(str(next(iter(forms))), VIA_NAME_RESOLVER)
            except Exception:  # pragma: no cover
                found = UNKNOWN
        if not found.is_known:
            for table, via in (
                (self._tmpl(), VIA_PLATFORM_TEMPLATE),
                (self._cat(), VIA_PLATFORM_CATALOG),
                (self._categories(), VIA_TENANT_CATEGORY),
            ):
                hit = table.get(name_key)
                if hit is not None:
                    found = VaultForm(hit, via)
                    break
        if not found.is_known:
            hit = _step_recorded_name(name_key)
            if hit is not None:
                found = VaultForm(hit, VIA_RECORDED_NAME)

        self._answers[name_key] = found
        return found


class VaultVariant:
    """Which catalogue variant a captured vault name is, and how we know.

    ⚠️ ONE PLACE, BECAUSE FOUR CALLERS NEED THIS AND THEY MUST NOT DISAGREE.
    `form_of`, `FormResolver.form_of`, `clears` and `typed_extraction` all have to
    turn a vault NAME into a catalogue variant, and before this they each did it
    themselves — three of them by going straight to the name resolver, which is how a
    tenant's explicit link came to be ignored by everything except one rung of the
    form ladder.

    ⚠️ `form` AND `variant_template_id` HAVE DIFFERENT THRESHOLDS ON THE RESOLVER
    PATH, AND THAT ASYMMETRY IS DELIBERATE AND PRE-EXISTING. A variant id needs the
    name to resolve to exactly ONE candidate. A form only needs every candidate to
    AGREE — `Continental Burial Vault` returns two candidates that are both
    `burial_vault`, so the form is known while the variant is not. Collapsing them to
    one threshold would either discard a form the catalogue agrees on or invent a
    variant it does not.
    """

    __slots__ = ("variant_template_id", "form", "via")

    def __init__(self, variant_template_id: str | None, form: str | None,
                 via: str | None) -> None:
        self.variant_template_id = variant_template_id
        self.form = form
        self.via = via

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return (f"VaultVariant(variant_template_id={self.variant_template_id!r}, "
                f"form={self.form!r}, via={self.via!r})")


NO_VARIANT = VaultVariant(None, None, None)


def linked_variant(db: Session, *, tenant_id: str, vault: object) -> VaultVariant:
    """ONLY the tenant's explicit link. `NO_VARIANT` when the product is unlinked.

    ⚠️ SEPARATE FROM `variant_for` SO A CALLER WITH ITS OWN FALLBACK DOES NOT RESOLVE
    TWICE. `typed_extraction` keeps a STRICTER form rule than the ladder does — it
    takes a form only when the name resolves to exactly one candidate, where the
    ladder accepts unanimity across several — so it cannot use `variant_for`'s
    fallback. If it called `variant_for` and then its own resolver, `build_index`
    would read the product tables twice on every extraction, which is the hot path.
    """
    name_key = _key(vault)
    if not name_key:
        return NO_VARIANT
    variant_id, form = _link_lookup(db, tenant_id, name_key)
    if variant_id is None and form is None:
        return NO_VARIANT
    return VaultVariant(variant_id, form, VIA_TENANT_LINK)


def variant_for(db: Session, *, tenant_id: str, vault: object) -> VaultVariant:
    """The catalogue variant for a captured vault name. The TENANT'S LINK WINS.

    James's ruling of 2026-10-28: *"An explicit products.variant_template_id wins over
    name resolution wherever a vault's variant is resolved (form ladder AND
    availability). Unlinked products behave exactly as today."*

    ⚠️ THE FALLBACK IS BYTE-FOR-BYTE THE OLD BEHAVIOUR, which is the half of the
    ruling that is easy to break while satisfying the other half. An unlinked product
    reaches the same `resolve_vault` call, with the same uniqueness rule for the
    variant and the same unanimity rule for the form, and reports the same
    `via=name_resolver`.
    """
    if not _key(vault):
        return NO_VARIANT

    # ── the tenant's own declaration ───────────────────────────────────────────────
    linked = linked_variant(db, tenant_id=tenant_id, vault=vault)
    if linked.via is not None:
        return linked

    # ── the catalogue's name resolver ──────────────────────────────────────────────
    try:
        from app.services.product_name_resolver import build_index
        from app.services.product_name_resolver import resolve as resolve_vault

        resolution = resolve_vault(build_index(db), str(vault).strip())
    except Exception:  # pragma: no cover - the ladder continues without it
        return NO_VARIANT

    candidates = resolution.candidates or ()
    forms = {c.form for c in candidates if getattr(c, "form", None)}
    # ⚠️ UNANIMITY FOR THE FORM, UNIQUENESS FOR THE ID — see the class docstring.
    unanimous = str(next(iter(forms))) if len(forms) == 1 else None
    variant_id = getattr(resolution, "variant_template_id", None)
    if variant_id is None and unanimous is None:
        return NO_VARIANT
    return VaultVariant(str(variant_id) if variant_id else None, unanimous,
                        VIA_NAME_RESOLVER)


def form_of(db: Session, *, tenant_id: str, vault: object) -> VaultForm:
    """What form the captured vault is, and how we know.

    ⚠️ AN EMPTY VAULT IS `UNKNOWN`, NOT A BURIAL VAULT. "No vault chosen yet" and
    "a burial vault" are different states, and the whole point of the cremation chip
    is that it appears when a kind is established. Defaulting to burial would show
    burial equipment to somebody who has not named a vault.
    """
    name_key = _key(vault)
    if not name_key:
        return UNKNOWN

    # ⚠️ THE FIRST TWO RUNGS ARE NOW ONE CALL, AND THE ORDER INSIDE IT IS THE RULING.
    # `variant_for` asks the tenant's link before the name resolver; this used to be
    # two rungs with the resolver first, which overruled the link.
    first = variant_for(db, tenant_id=tenant_id, vault=vault)
    if first.form is not None:
        return VaultForm(first.form, first.via)

    for step, via in (
        (lambda: _step_platform_template(db, name_key), VIA_PLATFORM_TEMPLATE),
        (lambda: _step_platform_catalog(db, name_key), VIA_PLATFORM_CATALOG),
        (lambda: _step_tenant_category(db, tenant_id, name_key), VIA_TENANT_CATEGORY),
        (lambda: _step_recorded_name(name_key), VIA_RECORDED_NAME),
    ):
        found = step()
        if found is not None:
            return VaultForm(found, via)
    return UNKNOWN


def is_cremation(db: Session, *, tenant_id: str, vault: object) -> bool:
    """The one question most callers actually have."""
    return form_of(db, tenant_id=tenant_id, vault=vault).is_cremation
