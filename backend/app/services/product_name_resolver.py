"""Resolve a spoken product phrase to catalog variants.

⚠️ THIS RETURNS A CANDIDATE SET AND THE DISCRIMINATOR THAT WOULD NARROW IT. IT
NEVER PICKS. The reason is measured, not stylistic:

    "cream and gold" matches TWO variants — P300 (Regal) and P310 (Tribute urn).
    P300 sorts first. A best-match resolver sells the Regal, silently, every
    time, on a funeral order.

Eight of fifty-two variants cannot be reached uniquely by their own display name,
and fifteen surface forms are ambiguous (measured 2026-10-05,
`docs/investigations/2026-10-05-vault-resolver-scope.md`). Every one of those is a
place a best match would be quietly wrong, and a capture overlay is exactly the
surface that can ask instead: *"Bronze Triune — burial or urn vault?"* is one
question an operator puts to a caller who is still on the phone.

⚠️ AND THE RESOLVER DOES NOT APPLY CONTEXT EITHER. It reports that FORM would
narrow the set; it does not decide that a funeral order means burial. That is the
CALLER'S knowledge — a vault order implies a burial vault unless cremation came
up, and only the caller knows whether it did. Putting that here would bury a
guess in a lookup.

THE DISCRIMINATORS ARE DERIVED FROM WHAT THE CANDIDATES DIFFER BY, not from a
hardcoded list of cases. Three attributes distinguish variants, measured from the
catalog:

    form          burial_vault / urn_vault / urn / grave_liner / infant / equipment
    family_slug   the product line
    option_label  the variant within a product

⚠️ `SIZE` IS NOT A FOURTH ATTRIBUTE, AND MY OWN SCOPING NOTE HAD THIS WRONG. Size
lives in `option_label`: Continental's two variants are labelled `Standard` and
`34 inch`, Graveliner's are `34 inch` / `38 inch` / `Social Service` / `Standard`.
So SIZE is a SPECIALISATION of OPTION, reported when ANY differing label denotes a
size — because the question differs ("what size?" rather than "which finish?")
even though the column does not.

⚠️ `ANY`, NOT `EVERY`, and this sentence said `every` until the real data was run
against it. Continental's labels are `Standard` and `34 inch`: under `every` that
classified as a finish choice, when the question is plainly a size. `Standard` is
a size here — it just does not look like one.

PRECEDENCE, when candidates differ in more than one attribute:

    FORM > LINE > SIZE > OPTION

FORM first because burial-versus-urn is the largest distinction and the one a
caller's own words usually settle. LINE next because a product line is a
different conversation from a variant within one. SIZE before OPTION because it
is the narrower question. `discriminators` exposes every attribute that differs,
in that order, so a mixed case is not forced into one bucket; `discriminator`
returns the first.

⚠️ THE ALIAS TABLE IS A CORRECTNESS REQUIREMENT, NOT AN OPTIMISATION. `Veteran`,
`SST` and `Basic Gray` resolve ONLY through `platform_product_aliases` — nothing
in their variants' own names reaches them. This module is that table's first
reader; it has held five rows and had none since r189 created it.

⚠️ A PHRASE THE CATALOG'S OWN NAMES DO NOT COVER IS A `NO MATCH`, AND THE REMEDY
IS AN ALIAS ROW RATHER THAN A FUZZIER MATCHER. "Cemetery Tent" is the worked
example: the product tier is named `Tent` and the variants are
`Cemetery Tent - Single` / `- Double`, so no indexed form equals "cemetery tent" —
it is a PREFIX of two variant names.

Prefix or substring matching would fix that case and reintroduce exactly what this
module refuses: "Tent" would then match everything containing the word, and the
nearest hit would win. The alias table exists for precisely this — a human
confirms "Cemetery Tent" means one of them, once, and it resolves thereafter.
So a `NO MATCH` here is working as designed, and is recorded because a reader
will otherwise take it for a bug.

⚠️ COLD PATH. No caller yet — the vault phrase arrives from a call overlay with no
production entrance. These are constructed inputs against the real catalog, and
the tests are the whole of the claim.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text
from sqlalchemy.orm import Session

#: Suffixes dropped so a family phrase reaches its variants.
#:
#: ⚠️ THIS MAKES MORE FORMS AMBIGUOUS AND THAT IS THE CORRECT TRADE. Measured:
#: ambiguous surface forms rise 15 -> 31. Before the strip the common spoken
#: forms — "Bronze Triune", "Continental", "Monticello", "Copper Triune" — reached
#: NOTHING. After it they reach the right candidates. Two candidates is a question
#: an operator can ask; no match is a dead end, and the dead end is worse.
_SUFFIXES = (
    " burial vault",
    " urn vault",
    " burial liner",
    " vault",
)

#: `34 inch` / `34 in` / `34in` / `34 "` all become `34"`, which is how the
#: catalog spells it (`Continental 34"`). Without this, "Continental 34 inch"
#: matches nothing while `Continental 34"` resolves uniquely.
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:inches|inch|ins|in|\")")

#: An option label that denotes a size rather than a finish or a configuration.
_SIZE_LABEL_RE = re.compile(r'^\d+(?:\.\d+)?"$')


def normalize(s: str | None) -> str:
    """Fold a phrase to its comparable form.

    Case, trademark marks, smart quotes and size spellings. Ampersands and inch
    marks are KEPT because they distinguish real catalog entries (`Cream & Gold`,
    `Continental 34"`).
    """
    if not s:
        return ""
    # ⚠️ MARKS COME OFF *BEFORE* NFKD, AND THE ORDER IS A BUG I SHIPPED ONCE.
    # NFKD DECOMPOSES "™" INTO "TM", so stripping afterwards left
    # "Legacy Series™ Print" as "legacy seriestm print" — a form nothing matches
    # and which would have been silently indexed that way. Caught by a test
    # asserting the folded output rather than a round trip.
    s = s.replace("™", "").replace("®", "").replace("©", "").replace("℠", "")
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("”", '"').replace("“", '"')
    s = s.replace("’", "'").replace("‘", "'")
    s = s.lower()
    s = _SIZE_RE.sub(r'\1"', s)
    s = re.sub(r"[^a-z0-9\"&' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _strip_suffix(n: str) -> str:
    for suf in _SUFFIXES:
        if n.endswith(suf) and len(n) > len(suf):
            return n[: -len(suf)].strip()
    return n


class Discriminator(str, Enum):
    """What would narrow an ambiguous candidate set."""

    FORM = "form"
    LINE = "line"
    SIZE = "size"
    OPTION = "option"


#: Fixed precedence. See the module docstring for why this order.
_PRECEDENCE = (Discriminator.FORM, Discriminator.LINE,
               Discriminator.SIZE, Discriminator.OPTION)


@dataclass(frozen=True)
class Candidate:
    variant_template_id: str
    sku: str
    display_name: str
    form: str
    family_slug: str
    option_label: str | None

    @property
    def option_is_size(self) -> bool:
        return bool(_SIZE_LABEL_RE.match(normalize(self.option_label)))


@dataclass(frozen=True)
class Resolution:
    """What a phrase resolved to, and what would narrow it if it did not."""

    phrase: str
    normalized: str
    candidates: tuple[Candidate, ...]
    #: Every attribute the candidates differ by, in precedence order. Empty when
    #: there is nothing to narrow.
    discriminators: tuple[Discriminator, ...]

    @property
    def resolved(self) -> bool:
        return len(self.candidates) == 1

    @property
    def ambiguous(self) -> bool:
        return len(self.candidates) > 1

    @property
    def unmatched(self) -> bool:
        return not self.candidates

    @property
    def discriminator(self) -> Discriminator | None:
        """The question to ask first, or None when there is nothing to ask."""
        return self.discriminators[0] if self.discriminators else None

    @property
    def variant_template_id(self) -> str | None:
        """⚠️ ONLY when exactly one candidate. Returns None for an ambiguous set
        rather than the first — a caller reaching for an id must handle the set,
        and silently handing back a winner is the defect this module exists to
        avoid."""
        return self.candidates[0].variant_template_id if self.resolved else None


@dataclass(frozen=True)
class NameIndex:
    """Normalised surface form -> the variants it reaches."""

    by_form: dict[str, tuple[Candidate, ...]]
    #: How many alias rows contributed. ⚠️ Read this before trusting a resolution
    #: of `Veteran`, `SST` or `Basic Gray` — they are reachable only through them.
    alias_count: int


_INDEX_SQL = """
    SELECT v.id, v.sku, v.display_name, v.option_label,
           t.display_name AS product_name, t.family_slug, t.form
    FROM product_variant_templates v
    JOIN product_templates t ON t.id = v.product_template_id
"""


def build_index(db: Session) -> NameIndex:
    """Read the catalog and the alias table into a lookup.

    ⚠️ INCLUDES `platform_product_aliases`, WHICH IS WHY THIS FUNCTION EXISTS AT
    ALL RATHER THAN A DICT COMPREHENSION OVER VARIANTS. Three confirmed aliases
    are the only route to their variants.
    """
    index: dict[str, set[Candidate]] = defaultdict(set)
    by_id: dict[str, Candidate] = {}

    for r in db.execute(text(_INDEX_SQL)):
        c = Candidate(
            variant_template_id=r.id, sku=r.sku, display_name=r.display_name,
            form=r.form, family_slug=r.family_slug, option_label=r.option_label,
        )
        by_id[r.id] = c
        forms = [r.display_name, r.sku, r.product_name]
        if r.option_label:
            forms.append(f"{r.option_label} {r.product_name}")
        for f in forms:
            n = normalize(f)
            if n:
                index[n].add(c)
                stripped = _strip_suffix(n)
                if stripped and stripped != n:
                    index[stripped].add(c)

    alias_rows = list(db.execute(text(
        "SELECT alias_text, variant_template_id FROM platform_product_aliases "
        "WHERE is_confirmed IS TRUE"
    )))
    for a in alias_rows:
        c = by_id.get(a.variant_template_id)
        if c is None:
            # An alias pointing at a variant that no longer exists. Skipped
            # rather than raising: the catalog is reshaped by migrations and a
            # stale alias row must not take the whole index down.
            continue
        n = normalize(a.alias_text)
        if n:
            index[n].add(c)

    return NameIndex(
        by_form={k: tuple(sorted(v, key=lambda c: c.sku)) for k, v in index.items()},
        alias_count=len(alias_rows),
    )


def _classify(candidates: tuple[Candidate, ...]) -> tuple[Discriminator, ...]:
    """Which attributes differ across the candidates, in precedence order."""
    if len(candidates) < 2:
        return ()
    found: set[Discriminator] = set()
    if len({c.form for c in candidates}) > 1:
        found.add(Discriminator.FORM)
    if len({c.family_slug for c in candidates}) > 1:
        found.add(Discriminator.LINE)
    if len({c.option_label for c in candidates}) > 1:
        # SIZE is a specialisation of OPTION — reported instead of it when ANY
        # differing label denotes a size.
        #
        # ⚠️ `any`, NOT `all`, AND THE REAL DATA IS WHY. Continental's two
        # variants are labelled `Standard` and `34 inch`. `all` reported OPTION
        # there — "which finish?" — when the question is plainly "what size?".
        # `Standard` IS a size in this domain (standard adult); it simply does not
        # look like one, and requiring every label to match a numeric pattern made
        # the one real size pair in the catalog classify as a finish choice.
        #
        # Checked against the alternatives rather than assumed safe: Triune
        # (Bronze/Copper/SST/Cream & Rose/Veteran) and Tent (Single/Double) have
        # no size-shaped label, so `any` leaves both as OPTION.
        if any(c.option_is_size for c in candidates):
            found.add(Discriminator.SIZE)
        else:
            found.add(Discriminator.OPTION)
    return tuple(d for d in _PRECEDENCE if d in found)


def resolve(index: NameIndex, phrase: str | None) -> Resolution:
    """Resolve one phrase. Never picks; see the module docstring."""
    n = normalize(phrase)
    candidates = index.by_form.get(n, ()) if n else ()
    if not candidates and n:
        candidates = index.by_form.get(_strip_suffix(n), ())
    return Resolution(
        phrase=phrase or "", normalized=n,
        candidates=tuple(candidates), discriminators=_classify(tuple(candidates)),
    )
