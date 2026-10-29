"""Towns typed with a cemetery — ONE pattern, shared by both surfaces.

James's ruling of 2026-10-29: *"One town pattern shared by both surfaces, not a copy."*

⚠️ IT LIVES HERE BECAUSE A RATCHET FORBIDS THE OBVIOUS HOME.
`test_only_the_typed_path_imports_the_extractor` asserts that nothing imports
`typed_extraction` — the E6 guarantee that the mention policy stays isolated to the typed
path. So the capture bar and the cemetery pane cannot share these by one importing the
other; they share them by both importing a leaf module, which is exactly what
`prefix_resolve` already is for the prefix walk (`order_list/cemetery.py` and
`order_list/customer.py` both take `reaches` from it rather than copying it) and what
`noise.py` became earlier the same day.

⚠️ AND THE COST OF A COPY IS ON THE RECORD IN THIS CODEBASE, which is why the ruling says
"not a copy" rather than "preferably not". `CEM_TOWN` gained a period in its charset on
2026-10-12 for "St. Albans"; an inline duplicate in the record-lookup pass kept the old
30-character form, so the record path still could not read an abbreviated town and still
claimed mid-word. The fix landed and did not take.
`test_there_is_exactly_ONE_town_pattern_in_the_module` exists for that, and now counts
across the whole of `app/` rather than one file — because the pattern no longer lives in
one file.

⚠️ TWO STRICTNESSES, ONE REASON: how much the text itself tells you. `CEM_TOWN` wants the
word "in", so a town that conflicts with the record is taken at face value and raises the
pick (ruled 2026-10-12). `CEM_TOWN_BARE` has no such word, so a bare adjacent run is only
a town when a cemetery of that name is actually in it — see `towns_for_name`.
"""
from __future__ import annotations

import re

CEM_TOWN = re.compile(
    r"\s+in\s+([A-Za-z][A-Za-z'\-.]+(?:\s+[A-Za-z][A-Za-z'\-.]*){0,2})", re.I
)

#: The same town, with NO "in" — James's ruling of 2026-10-29.
#:
#: > towns typed with a cemetery are part of it, not held words. Sunnycrest serves
#: > several cemeteries that share a name, so people type the town.
#:
#: ⚠️ IDENTICAL BODY, DELIBERATELY SHARING THE CHARSET, because the charset is where
#: this family has failed before: `CEM_TOWN` gained the period on 2026-10-12 for
#: "St. Albans" and a duplicated copy did not, so a fix landed and did not take. The
#: only difference here is the missing `in\s+`.
#:
#: ⚠️ AND IT IS ONLY SAFE BECAUSE ITS CALLERS NARROW IT STRICTLY. Without the word "in"
#: there is nothing in the text saying a town follows — "st marys tent only" matches
#: this pattern just as well as "st marys skaneateles" does. What tells them apart is
#: `narrow_town(..., strict=True)`: a bare word is a town only if we hold a cemetery in
#: it. A caller that narrows forgivingly would claim "tent" and raise a spurious pick.
CEM_TOWN_BARE = re.compile(
    r"\s+([A-Za-z][A-Za-z'\-.]+(?:\s+[A-Za-z][A-Za-z'\-.]*){0,2})", re.I
)

def narrow_town(raw: str, known: frozenset[str], *, strict: bool = False) -> str:
    """The longest word-prefix of `raw` that is a town we have a record of.

    ⚠️ THIS IS THE FUNERAL-HOME RULE APPLIED TO TOWNS, by the same ruling: a
    marker-led span must not swallow following words, and what bounds it is a
    record rather than a word count. "in Skaneateles tent only" gives
    "Skaneateles" because that is a city we hold and "Skaneateles tent" is not.

    ⚠️ AN UNKNOWN TOWN IS STILL READ, because a typed town that CONFLICTS with the
    record is supposed to raise the pick (ruled 2026-10-12) — it is the signal, so
    dropping it would lose the conflict. It is truncated at the first LABEL word
    after the first, which is what actually separates a place from the clause behind
    it: "Auburn service at" -> "Auburn".

    ⚠️ THE FIRST WORD IS NEVER DROPPED, and that exemption is load-bearing. A
    one-word fallback was tried and truncated two real towns — "New Hartford" became
    "New" and "St. Albans" became "St." — because `NOISE_WORDS` contains "new" (for
    "new order") and the bare fallback took a single word. Towns are named after
    anything, including words this module treats as noise elsewhere, so the first
    word of a town span is exempt by construction rather than by a longer list.

    ⚠️ RESIDUAL, STATED RATHER THAN HIDDEN: an UNKNOWN town followed by a label that
    is not in `NOISE_WORDS` still over-reaches by those words — "Xville tent only"
    reads "Xville tent". Every town in the seeded data takes the record path above,
    so this is reachable only for a town we hold no record of, and it is bounded at
    three words rather than the 30 CHARACTERS that produced 'ursday'.
    """
    # ⚠️ IMPORTED HERE, NOT AT MODULE LEVEL, BECAUSE THAT IS WHERE IT LIVES. The
    # name `_party_norm` is an alias created INSIDE `extract_line`
    # (`normalize as _party_norm`), so a module-level reference to it compiles,
    # imports, and raises `NameError` at call time. It did — caught by running the
    # function, not by reading it (CLAUDE.md §11: the check that catches this is
    # importing, or better, calling).
    from app.services.party_resolver import normalize as _norm

    words = raw.split()
    for n in range(len(words), 0, -1):
        if _norm(" ".join(words[:n])) in known:
            return " ".join(words[:n])
    # ⚠️ STRICT MODE STOPS HERE, AND IT EXISTS FOR THE BARE-TOWN FORM. Everything below
    # is the FORGIVING fallback, which returns a town we hold no record of — deliberately,
    # so a typed town that CONFLICTS raises the pick (ruled 2026-10-12). That is right
    # when the director wrote "in <town>", because the word "in" says a town follows.
    #
    # ⚠️ IT IS WRONG FOR A BARE ADJACENT WORD, AND THAT WOULD HAVE BEEN A REGRESSION.
    # Under James's ruling of 2026-10-29 a town may follow a cemetery with no "in" —
    # "st marys skaneateles". Run through the fallback, "st marys tent only" would
    # return "tent" (the first word, kept because the exemption never drops it, with
    # "only" stopping the run), that unknown town would conflict with the record, and
    # the pane would raise a spurious "which St Mary's?" while eating the equipment.
    # So a bare town must BE a town we hold, or it is not a town at all.
    if strict:
        return ""
    if not words:
        return ""
    keep = [words[0]]
    for w in words[1:]:
        if w.casefold().strip(".,'") in NOISE_WORDS:
            break
        keep.append(w)
    return " ".join(keep)

def towns_for_name(rows, name: str) -> frozenset[str]:
    """The towns a cemetery of this name actually sits in.

    ⚠️ THIS NARROWING IS WHAT KEEPS JAMES'S RULING FROM BREAKING A PROPERTY HE ASKED
    FOR, and it is worth stating because the two really do collide.

    His ruling of 2026-10-29 has three cases: a MATCHING town is absorbed, a SHARED name
    is disambiguated, and a town where that cemetery ISN'T makes Opas ask. The third is
    the problem. `resolve_from_rows` turns a city conflict into a PICK — correctly, by
    the ruling of 2026-10-12 — and a pick REPLACES the value, so the cemetery row goes
    from filled to a question as the director types the next word. That is precisely what
    `test_NO_PREFIX_EVER_LOSES_A_FIELD_IT_HAD` exists to catch: *"A field that appears and
    then vanishes is the defect he watched happen on screen — Hopkins captured, then gone
    when the next word landed."*

    Measured on James's own sentence, "st marys auburn tent only": on **testco** Oakwood
    is in Auburn, so "auburn" is a known town, the conflict fires and the cemetery
    vanishes at word 13. On **production** Sunnycrest has one cemetery and "auburn" is
    not a town it holds, so nothing changes there at all.

    ⚠️ SO THE BARE FORM IS NARROWED TO TOWNS CONSISTENT WITH THE NAME, which implements
    cases 1 and 2 exactly and leaves case 3 to behave as it does today — the town stays
    unclaimed rather than raising a question that un-answers the row. The explicit
    "in <town>" form is UNTOUCHED and still raises the conflict, because there the
    director wrote a word that says a town follows and meant it.

    ⚠️ AND CASE 3 BECOMES SAFE ONCE CLAUSE 1 LANDS. Under James's other ruling of the
    same day, a term that leaves the bar becomes a durable resolution, and resolutions
    outrank the text — so "st marys" would already be settled before "auburn" is typed
    and could not be un-answered by it. The deferral is until then, not forever.
    """
    from app.services.party_resolver import normalize as _pn

    want = _pn(name)
    out = set()
    for _id, _name, _city in rows:
        if not _city:
            continue
        n = _pn(_name)
        names = {n}
        for suf in (" cemetery", " cemeteries"):
            if n.endswith(suf):
                names.add(n[: -len(suf)].strip())
        if want in names:
            out.add(_pn(_city))
    return frozenset(out)

def town_after(
    text: str, known: frozenset[str], *, bare_known: frozenset[str] | None = None
) -> tuple[str, int] | None:
    """A town immediately after `text[0:]`, as `(town, chars_consumed)`, or None.

    Tries the explicit `in <town>` form first — forgiving, so a conflicting town still
    raises the pick — and falls back to a bare adjacent town narrowed STRICTLY.

    ⚠️ `bare_known` IS A DIFFERENT, NARROWER SET FOR THE BARE FORM, and the difference is
    the whole safety argument. `known` is every town the tenant holds a cemetery in;
    `bare_known` is every town a cemetery OF THIS NAME is in. See `towns_for_name`.
    Defaults to `known` so a caller without the name's towns gets the old behaviour
    rather than a surprise.
    """
    m = CEM_TOWN.match(text)
    if m:
        town = narrow_town(m.group(1), known)
        if town:
            return town, m.start(1) - m.start() + len(town)
    m = CEM_TOWN_BARE.match(text)
    if m:
        town = narrow_town(
            m.group(1), bare_known if bare_known is not None else known, strict=True
        )
        if town:
            return town, m.start(1) - m.start() + len(town)
    return None

def town_before(text: str, known: frozenset[str]) -> tuple[str, int] | None:
    """A town at the very END of `text`, as `(town, start_offset)`, or None.

    James's ruling of 2026-10-29 names both orderings: *"A town word … typed right after
    a cemetery term, or right before it ("skaneateles st marys"), belongs to that
    cemetery answer."*

    ⚠️ STRICT BY CONSTRUCTION — the whole trailing run must BE a town we hold records
    for. There is no "in" to lean on and no cemetery name after it yet, so a forgiving
    read here would claim the last word of whatever preceded: "order for hopkins st
    marys" would take "hopkins" as the town.

    ⚠️ AND THE LONGEST TRAILING RUN WINS, so a two-word town is not read as its second
    word. "new hartford st marys" must give "new hartford", not "hartford" with "new"
    orphaned.
    """
    from app.services.party_resolver import normalize as _pn

    runs = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    if not runs:
        return None
    for i in range(len(runs)):
        start = runs[i][0]
        if _pn(text[start:].strip()) in known:
            return text[start:].strip(), start
    return None


def town_leading(text: str, known: frozenset[str]) -> tuple[str, int] | None:
    """A town at the very START of `text`, as `(town, end_offset)`, or None.

    ⚠️ THE MIRROR OF `town_before`, AND IT EXISTS BECAUSE THE TWO SURFACES READ THE SAME
    SENTENCE FROM DIFFERENT ENDS. The extractor has already found the cemetery term and
    asks what sits before it, so the town is at the END of the text it hands over.
    The cemetery pane is handed the WHOLE typed string, so for "skaneateles st marys"
    the town is at the START and `town_before` cannot see it. Same ruling, same
    discipline, opposite edge — not a second pattern.

    ⚠️ STRICT BY CONSTRUCTION, for the same reason `town_before` is: the leading run must
    BE a town we hold records for. A forgiving read would take the first word of any
    query as a town.

    ⚠️ AND THE LONGEST LEADING RUN WINS, so "new hartford st marys" gives "new hartford"
    rather than "new" with "hartford" orphaned. The loop walks runs from the END of the
    candidate window inward, which is what makes the longest match the first hit.
    """
    from app.services.party_resolver import normalize as _pn

    runs = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    if not runs:
        return None
    for i in range(len(runs) - 1, -1, -1):
        end = runs[i][1]
        if _pn(text[:end].strip()) in known:
            return text[:end].strip(), end
    return None
