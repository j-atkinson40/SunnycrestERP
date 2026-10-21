"""An unambiguous prefix of a known term IS that term.

⚠️ THE RULE JAMES RULED (walk 2026-10-20): "Extraction accepts an unambiguous prefix of
a known term, using exactly the ghost's vocabulary and tie-break rules." The ghost
already knew that "hopk" can only mean Hopkins; the extractor did not, so a director
who typed the abbreviation and kept going — without pressing Tab — got a funeral home
and a vault marked as not understood while the bar had been offering the completion a
moment earlier. The bar knew and the engine did not.

⚠️ IT EXPANDS, IT DOES NOT RESOLVE. This module turns "hopk" into "Hopkins Funeral
Home" and then stops. The expanded name goes back through `resolve_funeral_home` or
`product_name_resolver` exactly as a fully typed name does, which is what keeps
`typed_extraction`'s own standing claim true — "IT RESOLVES NOTHING ITSELF". A second
resolver living here would be the two-lists defect wearing a new hat.

⚠️ ONE SOURCE OF TRUTH FOR THE VOCABULARY, AND A CROSS-CHECKED PAIR FOR THE RULE —
stated plainly because the two are not the same guarantee and the difference is
load-bearing.

    the vocabulary   `build_vocabulary` is the single producer. The ghost is served
                     the same rows from `/capture/vocabulary` that this module reads
                     in-process. There is no second list.

    the tie-break    implemented HERE, in Python, and mirrored by `ghost.ts`. It cannot
                     literally be one implementation: James ruled on 2026-10-16 that
                     "matching is client-side only... keystroke latency must not depend
                     on the network", so the ghost cannot call this and this cannot
                     call the ghost.

                     ⚠️ SO THE PAIR IS HELD BY A SHARED CORPUS, NOT BY CARE.
                     `tests/data/opas_prefix_corpus.json` is GENERATED FROM THIS
                     MODULE and asserted by `ghost-agrees.test.ts` on the other side.
                     A rule changed here and not there turns the TypeScript suite red.
                     That is the same device the canvas validators use (CLAUDE.md:
                     "Both validators MUST agree on schema rules... tested
                     cross-reference").

⚠️ AN AMBIGUOUS PREFIX IS A QUESTION, NEVER A GUESS. Two terms that share a prefix and
differ by anything other than form produce the ordinary choice list. The one tie-break
that resolves without asking is the form default, and it is the one the office already
made nine times in ten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.capture.vocabulary import Term

#: ⚠️ THE SAME FLOOR AS THE GHOST'S `MIN_PREFIX`, AND THE CORPUS PROVES IT STILL IS.
#: One letter matches most of the vocabulary, so a one-character "abbreviation" would
#: resolve to whatever happened to sort first.
MIN_PREFIX = 2

#: ⚠️ THE SAME DEFAULT THE CAPTURE AND THE GHOST BOTH ALREADY APPLY (James,
#: 2026-10-13, extended to the ghost 2026-10-16). A vault phrase ambiguous ONLY by
#: form is a burial vault.
BURIAL = "burial_vault"

#: Which vocabulary kinds can fill which field. Vault aliases are included because
#: `build_vocabulary` says in terms that they are the only route to some variants.
KINDS_FUNERAL_HOME = ("funeral_home",)

#: ⚠️ `product` IS IN HERE AND IS RANKED BELOW THE OTHER TWO. See `_rank_down_products`.
KINDS_VAULT = ("vault", "vault_alias", "product")

#: Vocabulary kinds that name a catalog VARIANT rather than a tenant's own product.
_VARIANT_KINDS = frozenset({"vault", "vault_alias"})


#: ⚠️ THE GENERIC WORDS, IN ONE PLACE, BY RULING (James, 2026-10-21): "Generic words
#: never count as a match point: burial, vault, urn, funeral, home, cemetery, memorial,
#: chapel, st, the, of, and (list them in one place)."
#:
#: His reason, and it is the whole reason the list exists: "people name vaults by their
#: distinctive word, not the first one" — but without a stoplist "bur" would match every
#: burial vault in the catalog, which is a choice list nobody can use.
#:
#: ⚠️ MIRRORED IN `ghost.ts` AND COMPARED BY THE GENERATED CORPUS, which carries this
#: set so a word added to one side and not the other turns the other side red. A
#: stoplist that drifted would make the two disagree about which names are reachable.
GENERIC_WORDS = frozenset({
    "burial", "vault", "urn", "funeral", "home", "cemetery",
    "memorial", "chapel", "st", "the", "of", "and",
})

#: ⚠️ POSITION 0 IS ALWAYS A MATCH POINT, EVEN WHEN THE FIRST WORD IS GENERIC, AND THAT
#: IS A READING OF THE RULING RATHER THAN A LITERAL TRANSCRIPTION OF IT. Flagged here
#: because flipping this one name is how it gets reversed.
#:
#: The ruling says a prefix may match "at the start of any word inside a known name, not
#: only the first word" — additive language — and separately that generic words never
#: count as a match point. Read as excluding position 0 too, measured on testco:
#:
#:     8 terms begin with a generic word and stop being reachable from it, including
#:     "St. Mary's Cemetery" (st) and "Memorial Chapel", whose EVERY word is generic
#:     and which would have no match point at all.
#:
#: That is a loss of reach the ruling did not ask for, and the stoplist's stated purpose
#: — stopping "bur" from matching the whole catalog — is about INTERIOR matches: nothing
#: in either catalogue begins with "Burial", so allowing position 0 does not reinstate
#: it. So the generic list governs the NEW interior match points and today's behaviour
#: is preserved exactly.
FIRST_WORD_ALWAYS_MATCHES = True

#: ⚠️ ONLY CATALOG NAMES GET INTERIOR MATCH POINTS, AND A TEST FOUND THIS THE HARD WAY.
#: `test_a_LOWERCASE_DECEDENT_is_still_not_recognised` went red the moment word-initial
#: matching landed: "mary smith" came back with only "smith" unplaced, because **"mary"
#: reached `St. Mary's Cemetery` at its interior word** and was claimed as a party.
#:
#: ⚠️ THE DECEDENT IS THE ONE FIELD WHERE HUMAN GIVEN NAMES APPEAR, AND PLACE NAMES ARE
#: FULL OF THEM — St. Mary's, St. Joseph's, Mount Olivet. Interior matching on party
#: names turns every such first name into a cemetery, and the decedent pass works BY
#: ELIMINATION over what nothing else claimed, so the name does not merely compete — it
#: is consumed before the decedent pass can see it.
#:
#: Both of James's examples are catalog names ("venetian" for White Venetian, "salute"
#: for Veteran Salute), and the reason he gave is about how people name VAULTS. Parties
#: keep matching from position 0, exactly as before.
INTERIOR_KINDS = frozenset({"vault", "vault_alias", "product"})


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _word_key(word: str) -> str:
    """A term word reduced to the thing the stoplist is written in.

    ⚠️ PUNCTUATION IS STRIPPED FROM BOTH ENDS BECAUSE THE CATALOGUE CARRIES IT. "St."
    must match the stoplist entry "st", and `(Cream` — a real word in `Universal Urn
    Vault (Cream & Gold)` — must reduce to "cream" or the bracketed variants would be
    unreachable by their own distinctive word.
    """
    return word.strip("().,'\"-&\u2019").lower()


def match_points(term: str, *, interior: bool = True) -> tuple[int, ...]:
    """Every character position in `term` at which a typed prefix may begin.

    ⚠️ RULED 2026-10-21. Before this, a prefix had to match from character 0, so
    `White Venetian Burial Vault` was unreachable by "venet" — and a director names a
    vault by its distinctive word, not by the colour that happens to come first.

    Position 0, plus the start of every later word that is not generic AND begins with a
    letter — a bare number is not a distinctive word. Returned in
    ascending order so a caller preferring the earliest match gets the one that matches
    from the start of the name.
    """
    points: list[int] = [0] if FIRST_WORD_ALWAYS_MATCHES else []
    if not interior:
        # ⚠️ PARTY NAMES MATCH FROM THE START ONLY. See `INTERIOR_KINDS`.
        return tuple(points)
    for m in re.finditer(r"\S+", term):
        if m.start() == 0:
            if not FIRST_WORD_ALWAYS_MATCHES and _word_key(m.group(0)) not in GENERIC_WORDS:
                points.append(0)
            continue
        key = _word_key(m.group(0))
        if key in GENERIC_WORDS:
            continue
        # ⚠️ AN INTERIOR MATCH POINT MUST BEGIN WITH A LETTER, AND A TEST FOUND THIS THE
        # HARD WAY. The ruling says "any DISTINCTIVE WORD"; a bare number is not one.
        # Measured 2026-10-21 the moment word-initial matching landed:
        #
        #     "34" reached 'Continental 34"'          "24" reached 'Loved & Cherished 24"'
        #     "30" reached 'Late Arrival per 30 min'
        #
        # So `34 inch Contin` resolved a vault from the SIZE alone — and an order
        # sentence is full of bare numbers: a time, a date, a quantity. A director
        # typing "thursday 10 am" must not have "10" read as a product. It also drops
        # `&` and other symbol-only tokens, which are not words either.
        if not key[:1].isalpha():
            continue
        points.append(m.start())
    return tuple(dict.fromkeys(points))


def reaches(term: str, prefix: str, *, interior: bool = True) -> int | None:
    """How far into `term` this prefix reaches from its best match point, or None.

    ⚠️ THE EARLIEST VALID MATCH POINT WINS, so a prefix that matches from the start of
    the name is read that way rather than as an interior match.

    ⚠️ AND A WHOLE TERM IS STILL NOT AN ABBREVIATION OF ITSELF — but only from position
    0. "salute" consumes the LAST word of `Veteran Salute` and reaches the end of the
    term, which is a perfectly good abbreviation of it; the exact scans own only the
    case where the director typed the whole name from its first character.
    """
    for p in match_points(term, interior=interior):
        at = consume_loose(term, prefix, p)
        if at <= p:
            continue
        if p == 0 and at >= len(term):
            continue
        return at
    return None


def consume_loose(term: str, prefix: str, start: int = 0) -> int:
    """How far into `term` the typed `prefix` reaches, or -1.

    ⚠️ A CHARACTER-WALK, NOT `startswith`, AND PUNCTUATION IS WHY. A director types
    "st m"; the record is `St. Mary's Cemetery`. A lowercased `startswith` fails on the
    PERIOD. This is a port of `ghost.ts::consumeLoose` and the corpus holds it to that.

    ⚠️ A SPACE IN THE PREFIX FORCES A WORD BOUNDARY IN THE TERM, so "st m" cannot match
    "stm..." inside a single word.
    """
    skippable = lambda ch: re.match(r"[^a-z0-9]", ch, re.I) is not None
    ti, pi = start, 0
    while pi < len(prefix):
        if skippable(prefix[pi]):
            if prefix[pi].isspace():
                while ti < len(term) and not term[ti].isspace():
                    ti += 1
                while ti < len(term) and term[ti].isspace():
                    ti += 1
            pi += 1
            continue
        while ti < len(term) and skippable(term[ti]) and not term[ti].isspace():
            ti += 1
        if ti >= len(term):
            return -1
        if term[ti].lower() != prefix[pi].lower():
            return -1
        ti += 1
        pi += 1
    return ti


def differ_only_by_form(matches: tuple[Term, ...]) -> bool:
    """Do these differ ONLY by their catalog form?

    ⚠️ THE TEST IS WHETHER REMOVING EACH TERM'S OWN FORM WORD LEAVES THEM IDENTICAL —
    which is the capture's `discriminators == ("form",)` condition expressed over
    names. `Continental Burial Vault` and `Continental 34"` differ by SIZE as well, and
    the capture refuses to guess there; so does this.
    """
    if len(matches) < 2:
        return False
    if not all(m.form for m in matches):
        return False
    if len({m.form for m in matches}) < 2:
        return False
    stems = set()
    for m in matches:
        word = (m.form or "").split("_")[0]  # burial_vault -> "burial"
        stems.add(
            re.sub(r"\s+", " ", re.sub(rf"\b{re.escape(word)}\b", "", _norm(m.text))).strip()
        )
    return len(stems) == 1


def _rank_down_products(matches: tuple[Term, ...]) -> tuple[Term, ...]:
    """Drop tenant product names when a catalog VARIANT already matches.

    ⚠️ THIS IS WHAT LETS PRODUCT NAMES BE ADDED WITHOUT A REGRESSION, AND THE
    REGRESSION IS MEASURED RATHER THAN IMAGINED. James ruled on 2026-10-21 that
    product names join the vocabulary so "venet" can reach Venetian. On sunnycrest the
    `products` table also holds `Monticello Burial Vault` and `Continental Burial
    Vault` — so without this step "monti" would match a variant AND a product, two
    terms, and a prefix that RESOLVED today would start ASKING. That is the phrasing
    James had just confirmed working.

    ⚠️ A PRODUCT NAME IS A ROUTE OF LAST RESORT, NOT A COMPETITOR. It adds reach where
    the variants' own spellings cannot be prefixed — which is exactly the Venetian
    case, where every variant begins with a colour the director does not say. Where a
    variant is already reachable, the tenant's name for it says nothing new.

    ⚠️ AND IT IS THE SAME SHAPE `build_vocabulary` ALREADY USES FOR TENANT-VS-PLATFORM
    terms ("PLATFORM TERMS ARE STILL INCLUDED, RANKED BELOW"), one layer along: include
    everything, let the more specific kind win a tie.
    """
    # ⚠️ IT DROPS PRODUCTS, IT DOES NOT KEEP ONLY VARIANTS, AND A TEST CAUGHT ME
    # GETTING THAT WRONG. My first version returned `[t for t in matches if t.kind in
    # _VARIANT_KINDS]` whenever any variant matched — which on an UNSCOPED resolve
    # (`kinds=None`) also discarded every funeral home and cemetery, because they are
    # not variants either. The step is about ranking products below variants, not about
    # preferring variants over the rest of the vocabulary.
    if not any(t.kind in _VARIANT_KINDS for t in matches):
        return matches
    return tuple(t for t in matches if t.kind != "product")


@dataclass(frozen=True)
class PrefixResolution:
    """What a prefix reached."""

    #: The prefix as typed.
    prefix: str
    #: Every term still in play after the tie-breaks.
    matches: tuple[Term, ...]
    #: The single term this prefix means, or None when it is a question.
    chosen: Term | None

    @property
    def ambiguous(self) -> bool:
        """⚠️ NOT `len(matches) > 1` — a form tie resolves and still has two matches."""
        return self.chosen is None and len(self.matches) > 1


def resolve_prefix(
    prefix: str, vocab: tuple[Term, ...], kinds: tuple[str, ...] | None = None
) -> PrefixResolution | None:
    """The term an abbreviation means, by the ghost's rule. None when it reaches nothing.

    THE RULE, IN ORDER — the same seven steps as `ghost.ts::completionFor`, minus the
    caret handling, which is a property of a text box and not of a vocabulary:

      1. shorter than `MIN_PREFIX` -> nothing.
      2. matches are terms this prefix REACHES — from position 0, or from the start of
         any later non-generic word (ruled 2026-10-21, see `match_points`). A prefix
         equal to the whole term FROM POSITION 0 is not an abbreviation; the exact scans
         already own that, and claiming it here would put two writers on one span.
      3. restricted to `kinds`, so a prefix resolving for the vault cannot fill the
         funeral home. ⚠️ MEASURED ON PRODUCTION: a `company_entities` row is named
         "St. Mary's Cemetery", so "st m" reaches a funeral home AND a cemetery. Kind
         scoping is what keeps that from being an ambiguity it is not.
      4. if ANY match is carried by this tenant, only carried matches count.
      4a. if any match is a catalog VARIANT, tenant product names drop out. A product
         name reaches a family the variants' own spellings cannot be prefixed to
         ("venet" -> Venetian); where a variant is already reachable it adds nothing,
         and letting it compete would turn today's answers into questions.
      5. exactly one -> that is what it means.
      6. several differing only by form -> the burial vault.
      7. otherwise -> a question. ⚠️ IT DOES NOT FALL BACK TO A SHORTER PREFIX.
         Ambiguous at this length means ambiguous; the director typed the longer thing.
    """
    p = _norm(prefix)
    if len(p) < MIN_PREFIX:
        return None

    pool = [t for t in vocab if kinds is None or t.kind in kinds]
    matches = tuple(
        t for t in pool
        if reaches(t.text, prefix, interior=t.kind in INTERIOR_KINDS) is not None
    )
    if not matches:
        return None

    carried = tuple(t for t in matches if t.carried)
    if carried:
        matches = carried

    matches = _rank_down_products(matches)

    if len(matches) == 1:
        return PrefixResolution(prefix, matches, matches[0])

    if differ_only_by_form(matches):
        burial = next((m for m in matches if m.form == BURIAL), None)
        if burial is not None:
            return PrefixResolution(prefix, matches, burial)

    # ⚠️ SEVERAL TERMS WITH THE SAME TEXT ARE ONE ANSWER, NOT A QUESTION. The vocabulary
    # is keyed on (kind, text), so one name carried as both a variant and a confirmed
    # alias appears twice. Asking "did you mean Monticello Burial Vault or Monticello
    # Burial Vault?" is not a question anybody can answer.
    if len({_norm(m.text) for m in matches}) == 1:
        return PrefixResolution(prefix, matches, matches[0])

    return PrefixResolution(prefix, matches, None)
