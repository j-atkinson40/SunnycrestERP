"""Resolve a spoken funeral-home or cemetery name to candidates — never a pick.

⚠️ E3 (2026-10-07). THE THIRD AND FOURTH RESOLVER IN THIS FAMILY, AND THE FIRST TWO
PARTY RESOLVERS THAT ASK RATHER THAN GUESS. `product_name_resolver` returns a
candidate set plus a `Discriminator` for vaults; `legacy_print_resolver` does the same
for prints. Funeral homes and cemeteries did not, and there were THREE separate top-1
implementations:

    call_extraction_service._fuzzy_match_company       exact, then LIKE, .first()
    command_bar_extract_service._fuzzy_match_company   its own, returns a dict
    nl_creation.entity_resolver.resolve_company_entity pg_trgm, documented "top-1"

All three pick. ⚠️ A cemetery named "St. Mary's" in two towns resolved to whichever
row Postgres returned first, silently — which is precisely why `cemetery_city` was
ruled into the capture template, and that field was captured and then **not used in
resolution at all**.

⚠️ THE CITY IS THE DISCRIMINATOR, NOT A FILTER APPLIED FIRST. Narrowing by city before
matching the name would hide the collision: a director who says "St. Mary's" with no
town would get one silent answer again, just filtered differently. The name matches
first, and the town is what the question is ABOUT when more than one survives.

⚠️ THIS MODULE DOES NOT REPLACE THE THREE ABOVE. It is additive: the typed-capture
path uses it, and repointing the other three is separate work with its own callers to
check. `call_extraction_service` is repointed; `command_bar_extract_service` and
`nl_creation` are NOT, and that is recorded rather than done quietly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import text
from sqlalchemy.orm import Session


class PartyDiscriminator(str, Enum):
    """What separates the candidates when more than one matched."""

    #: Same name, different town — the case `cemetery_city` exists for.
    CITY = "city"
    #: Same name, same town. Nothing in the data tells them apart.
    INDISTINGUISHABLE = "indistinguishable"
    #: Different names that merely share the matched words.
    UNRELATED = "unrelated"


@dataclass(frozen=True)
class PartyCandidate:
    party_id: str
    name: str
    city: str | None

    @property
    def label(self) -> str:
        """⚠️ THE TOWN IS IN THE LABEL WHENEVER IT IS KNOWN, because the label is what
        a numbered pick renders and "St. Mary's / St. Mary's" is not a choice."""
        return f"{self.name} — {self.city}" if self.city else self.name


@dataclass(frozen=True)
class PartyResolution:
    phrase: str
    normalized: str
    candidates: tuple[PartyCandidate, ...]
    discriminators: tuple[PartyDiscriminator, ...]
    #: The town the director said, if they said one. Used to narrow, never to filter
    #: before matching.
    city_hint: str | None = None
    #: ⚠️ THE DIRECTOR NAMED A TOWN THAT NO CANDIDATE IS IN. Not a no-match and not a
    #: clean hit — a disagreement between what was said and what the table holds. The
    #: caller must ASK; storing either value picks a side nobody measured.
    city_conflict: bool = False

    @property
    def matched(self) -> bool:
        return bool(self.candidates)

    @property
    def party_id(self) -> str | None:
        """The one id, or None for zero, several, OR a city conflict.

        ⚠️ A CITY CONFLICT READS AS UNRESOLVED even with exactly one candidate, because
        resolving it would record a town the director did not say.

        ⚠️ NONE FOR AMBIGUOUS AND NONE FOR NO-MATCH, the same value deliberately —
        the same contract `product_name_resolver.Resolution.variant_template_id` has,
        so a caller cannot accidentally read "two matches" as "nothing found".
        """
        if self.city_conflict:
            return None
        return self.candidates[0].party_id if len(self.candidates) == 1 else None


def normalize(s: str | None) -> str:
    """Casefold, expand `&`, strip punctuation, collapse whitespace.

    ⚠️ TRIM FIRST. Stripping punctuation before trimming leaves a separator behind on
    trailing whitespace — the `normalizeRequest` defect of 2026-10-03. Apostrophes
    matter here: "St. Mary's" and "St Marys" must normalize together.
    """
    if not s:
        return ""
    out = s.strip().casefold()
    out = out.replace("&", " and ")
    out = re.sub(r"[^a-z0-9]+", " ", out)
    return re.sub(r"\s+", " ", out).strip()


#: Words that carry no identity and would otherwise make every name match every other.
#: ⚠️ `cemetery` and `funeral home` are IN here because a director says them as part of
#: the phrase ("St. Mary's cemetery"), and matching on them alone would return the
#: whole table.
_NOISE: frozenset = frozenset({
    "cemetery", "cemeteries", "funeral", "home", "homes", "and", "sons", "son",
    "the", "of", "inc", "llc", "co", "company", "memorial", "gardens", "park",
    # ⚠️ PREPOSITIONS ADDED 2026-10-07 AFTER A CALLER LEAKED ONE. A caller's regex
    # took "cemetery in" into the name it passed here, and `in` became a significant
    # token no candidate carries, so a name that matches exactly one row matched none.
    # The caller was fixed; these are here so the next leak degrades instead of
    # failing — a stray preposition should widen the candidate set, never empty it.
    "in", "on", "at", "to", "for", "with", "near",
})


def _significant(norm: str) -> list[str]:
    words = [w for w in norm.split() if w not in _NOISE]
    # ⚠️ FALL BACK TO EVERY WORD rather than to nothing. A party genuinely called
    # "Memorial Gardens" is all noise by the list above, and returning no candidates
    # for a real name is worse than returning a wide set the director can pick from.
    return words or norm.split()


def _classify(
    cands: tuple[PartyCandidate, ...], norm: str
) -> tuple[PartyDiscriminator, ...]:
    if len(cands) < 2:
        return ()
    names = {normalize(c.name) for c in cands}
    if len(names) > 1:
        return (PartyDiscriminator.UNRELATED,)
    cities = [c.city for c in cands]
    if len({(c or "").casefold() for c in cities}) > 1:
        return (PartyDiscriminator.CITY,)
    return (PartyDiscriminator.INDISTINGUISHABLE,)


def _resolve(
    rows: list[tuple[str, str, str | None]], phrase: str | None, city_hint: str | None
) -> PartyResolution:
    """Shared matching over (id, name, city) rows. Pure — no database."""
    norm = normalize(phrase)
    if not norm:
        return PartyResolution(phrase or "", "", (), (), city_hint)

    words = _significant(norm)
    hits: list[PartyCandidate] = []
    for pid, name, city in rows:
        nname = normalize(name)
        if nname == norm or all(w in nname.split() for w in words):
            hits.append(PartyCandidate(pid, name, city))

    # ⚠️ THE CITY NARROWS AFTER MATCHING, AND ONLY IF IT LEAVES SOMETHING. A town the
    # director named that matches none of the candidates is more likely a mis-heard
    # town than proof the cemetery is wrong, so narrowing to zero is refused and the
    # full set is returned for a pick.
    city_conflict = False
    if city_hint and hits:
        ch = normalize(city_hint)
        narrowed = [c for c in hits if ch and normalize(c.city or "") == ch]
        if narrowed:
            hits = narrowed
        elif any(c.city for c in hits):
            # ⚠️ THE DIRECTOR NAMED A TOWN AND NO CANDIDATE IS IN IT. This is a
            # CONFLICT, not a near miss, and the first version resolved it silently —
            # "St Mary's cemetery in Auburn" matched the one St. Mary's (Skaneateles)
            # and then wrote `cemetery_city='Skaneateles'`, overwriting what the
            # director said with what the table says. That asserts the director was
            # wrong about the town, which is the one thing nobody measured.
            #
            # Either they misremembered, or there is a second St. Mary's the table does
            # not have. Both are questions. So the hit is kept but marked conflicted,
            # and the caller must ask rather than store.
            city_conflict = True

    hits.sort(key=lambda c: (normalize(c.name), (c.city or "").casefold()))
    discs = _classify(tuple(hits), norm)
    if city_conflict and not discs:
        discs = (PartyDiscriminator.CITY,)
    return PartyResolution(
        phrase=phrase or "",
        normalized=norm,
        candidates=tuple(hits),
        discriminators=discs,
        city_hint=city_hint,
        city_conflict=city_conflict,
    )


def resolve_funeral_home(
    db: Session, tenant_id: str, phrase: str | None, *, city_hint: str | None = None
) -> PartyResolution:
    """Candidates for a funeral-home phrase, scoped to the tenant.

    ⚠️ `is_funeral_home` IS NOT REQUIRED. Measured on dev 2026-10-07: of 18
    `company_entities`, the flag is a role marker that seed data does not set
    uniformly, so requiring it would return nothing for real rows. The caller asked
    for a funeral home by name; filtering on a flag nobody populated would answer
    "no such funeral home" about an entity that is one.
    """
    rows = [
        (r[0], r[1], r[2])
        for r in db.execute(text(
            "SELECT id, name, city FROM company_entities WHERE company_id = :t"
        ), {"t": tenant_id})
    ]
    return _resolve(rows, phrase, city_hint)


def resolve_cemetery(
    db: Session, tenant_id: str, phrase: str | None, *, city_hint: str | None = None
) -> PartyResolution:
    """Candidates for a cemetery phrase, scoped to the tenant.

    `city_hint` is `cemetery_city` from the capture — the field ruled in precisely so
    that two St. Mary's can be told apart.
    """
    rows = [
        (r[0], r[1], r[2])
        for r in db.execute(text(
            "SELECT id, name, city FROM cemeteries WHERE company_id = :t"
        ), {"t": tenant_id})
    ]
    return _resolve(rows, phrase, city_hint)


def party_counts(db: Session, tenant_id: str) -> tuple[int, int]:
    """(company_entities, cemeteries) for this tenant.

    ⚠️ EXISTS SO A TEST CAN PROVE THE INSTRUMENT SEES SOMETHING. A resolver over an
    empty table returns "no match" for every phrase, which is indistinguishable from
    a phrase the table does not contain.
    """
    ce = db.execute(text(
        "SELECT count(*) FROM company_entities WHERE company_id = :t"
    ), {"t": tenant_id}).scalar()
    cem = db.execute(text(
        "SELECT count(*) FROM cemeteries WHERE company_id = :t"
    ), {"t": tenant_id}).scalar()
    return int(ce or 0), int(cem or 0)
