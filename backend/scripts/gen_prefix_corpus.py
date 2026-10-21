"""Generate the cross-language corpus that holds the ghost to the extractor's rule.

⚠️ WHY THIS EXISTS. James ruled that extraction must accept abbreviations "using
exactly the ghost's vocabulary and tie-break rules (one source of truth, not a copy)".
The vocabulary genuinely is one source — `build_vocabulary` produces it and the ghost is
served those same rows. The RULE cannot be: `prefix_resolve` is Python and runs on the
server, `ghost.ts` is TypeScript and must stay client-side, because James ruled on
2026-10-16 that "matching is client-side only... keystroke latency must not depend on
the network". Neither can call the other.

⚠️ SO THE PAIR IS HELD BY A GENERATED ARTEFACT RATHER THAN BY CARE, which is the same
device the canvas validators use (CLAUDE.md: "Both validators MUST agree on schema
rules... tested cross-reference"). This script asks the PYTHON rule for its answer on
every case and writes it down; `ghost-agrees.test.ts` replays the same cases through the
TypeScript rule and fails if any answer differs. A rule changed on one side and not the
other turns a suite red instead of drifting quietly.

⚠️ THE VOCABULARY IN THE CORPUS IS SYNTHETIC AND THAT IS DELIBERATE. Generating it from
a live tenant would make the corpus depend on seed data, so a reseed would look like a
rule change. The terms here are shaped to exercise the tie-breaks — a carried/uncarried
pair, a form-only pair, a size-differing trio, a same-text duplicate, a punctuated name.

Run:  PYTHONPATH=. .venv/bin/python scripts/gen_prefix_corpus.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.services.capture.prefix_resolve import (  # noqa: E402
    FIRST_WORD_ALWAYS_MATCHES,
    GENERIC_WORDS,
    INTERIOR_KINDS,
    MIN_PREFIX,
    match_points,
    reaches,
    resolve_prefix,
)
from app.services.capture.vocabulary import Term  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = _ROOT / "backend/tests/data/opas_prefix_corpus.json"

#: ⚠️ A SECOND COPY, INSIDE THE FRONTEND, AND IT IS NOT A SECOND SOURCE.
#: My first version had the TypeScript suite import the backend path directly
#: (`../../../../backend/tests/data/...`). It typechecked and built locally and FROZE THE
#: FRONTEND DEPLOY: the Docker build copies only `frontend/`, `tsconfig.app.json`
#: includes `src`, so `tsc -b` resolved an import to a file that does not exist in the
#: container — and `npm run build` is `tsc -b && vite build`, so vite never ran and no
#: new bundle was ever emitted. Exactly the class CLAUDE.md records under
#: "Two failures that look unrelated can be one".
#:
#: ⚠️ THE GENERATOR WRITES BOTH, AND A TEST ASSERTS THEY ARE BYTE-IDENTICAL, so this is
#: one artefact at two paths rather than two artefacts free to drift. Without that
#: assertion it would be the two-lists defect wearing a new hat.
OUT_FE = _ROOT / "frontend/src/components/opas/__fixtures__/opas_prefix_corpus.json"

#: (text, kind, carried, form)
VOCAB_SPEC = [
    ("Hopkins Funeral Home", "funeral_home", True, None),
    ("Hopewell Memorial", "funeral_home", True, None),
    ("Riverside Memorial Chapel", "funeral_home", True, None),
    ("St. Mary's Cemetery", "funeral_home", True, None),
    ("St. Mary's Cemetery", "cemetery", True, None),
    ("St. Michael's Cemetery", "cemetery", True, None),
    # a form-only pair, one carried — exercises both step 4 and step 6
    ("Monticello Burial Vault", "vault", True, "burial_vault"),
    ("Monticello Urn Vault", "vault", False, "urn_vault"),
    # a form-only pair with NEITHER carried, so the form default must decide
    ("Cameo Rose Burial Vault", "vault", False, "burial_vault"),
    ("Cameo Rose Urn Vault", "vault", False, "urn_vault"),
    # differing by SIZE as well as form — must ask
    ('Continental 34"', "vault", False, "burial_vault"),
    ("Continental Burial Vault", "vault", False, "burial_vault"),
    ("Continental Urn Vault", "vault", False, "urn_vault"),
    # one name present as both a variant and a confirmed alias
    ("Graveliner 38\"", "vault", True, "burial_vault"),
    ("Graveliner 38\"", "vault_alias", True, None),
    # ── tenant product names, ruled in 2026-10-21 ──
    # ⚠️ THE VENETIAN SHAPE: every variant begins with a colour the director does not
    # say, so the PRODUCT name is the only reachable route for "venet".
    ("White Venetian Burial Vault", "vault", True, "burial_vault"),
    ("Gold Venetian Burial Vault", "vault", True, "burial_vault"),
    ("Venetian", "product", True, None),
    # ⚠️ THE MONTICELLO SHAPE: a product name that COMPETES with a reachable variant and
    # must therefore lose. Without `_rank_down_products` this pair turns "monti" from an
    # answer into a question.
    ("Monticello", "product", True, None),
    # ⚠️ AND A PRODUCT-ONLY AMBIGUITY, so the step cannot be mistaken for "products
    # never win": two products, no variant, must still ask.
    ("Tent Only (with)", "product", True, None),
    ("Tent Only (without)", "product", True, None),
    # ── word-initial matching, ruled 2026-10-21 ──
    # ⚠️ THE SALUTE SHAPE: the distinctive word is LAST, so the prefix reaches the end
    # of the term — legal from an interior match point, illegal from position 0.
    ("Veteran Salute Burial Vault", "vault", True, "burial_vault"),
    # ⚠️ EVERY WORD GENERIC: reachable only because position 0 stays a match point.
    ("Memorial Chapel", "funeral_home", True, None),
    # ⚠️ A GENERIC FIRST WORD WITH A DISTINCTIVE INTERIOR ONE.
    ("Urn Vault Standard", "vault", True, "urn_vault"),
]

PREFIXES = [
    "h", "ho", "hop", "hopk", "hope", "hopkins", "hopkins funeral home",
    "riv", "rivers", "r",
    "st", "st m", "st. m", "stm", "st mary", "st mi",
    "monti", "mont", "monticello", "m",
    "cam", "cameo", "cameo rose",
    "conti", "cont", "continental", 'continental 34"',
    "grav", "graveliner",
    "venet", "venetian", "white venet", "tent", "tent only",
    # the ruling's own examples, plus the generic words it forbids as match points
    "salute", "salu", "vet", "veteran", "standard", "stand",
    "bur", "buri", "burial", "vaul", "chapel", "memorial", "urn",
    "blargle", "zzz", "", " ",
]

KIND_SETS = {
    "funeral_home": ("funeral_home",),
    "cemetery": ("cemetery",),
    "vault": ("vault", "vault_alias", "product"),
    "variants_only": ("vault", "vault_alias"),
    "any": None,
}


def main() -> int:
    vocab = tuple(
        Term(text=t, kind=k, carried=c, form=f) for t, k, c, f in VOCAB_SPEC
    )
    cases = []
    for label, kinds in KIND_SETS.items():
        for p in PREFIXES:
            r = resolve_prefix(p, vocab, kinds)
            cases.append({
                "prefix": p,
                "kinds": list(kinds) if kinds else None,
                "kind_set": label,
                # ⚠️ THREE OUTCOMES, NAMED, because "null" would conflate "reaches
                # nothing" with "reaches several and must ask" — and those two are the
                # whole difference between a miss and a question.
                "outcome": (
                    "none" if r is None
                    else "chosen" if r.chosen is not None
                    else "ambiguous"
                ),
                "chosen": (r.chosen.text if r and r.chosen else None),
                "chosen_kind": (r.chosen.kind if r and r.chosen else None),
                "matches": sorted(m.text for m in r.matches) if r else [],
            })

    # ⚠️ THE WALK IS CORPUS'D SEPARATELY FROM THE RESOLUTION, because a port can agree
    # on every final answer while differing on the walk — and the walk is what produces
    # the ghost's visible SUFFIX. "stm" vs "st m" is exactly that case.
    #
    # ⚠️ IT RECORDS `reaches`, NOT `consume_loose`, SINCE 2026-10-21: the match point is
    # now part of the answer, and a port that agreed on every consumed length while
    # choosing a different match point would draw a suffix from the wrong place.
    # ⚠️ KEYED ON THE KIND'S INTERIOR SETTING, since 2026-10-21: a party name matches
    # from position 0 only, so the same (term, prefix) pair has two right answers and a
    # corpus recording one would hold the ports to the wrong one for half the vocabulary.
    terms = sorted({x[0] for x in VOCAB_SPEC})
    walks = [
        {"term": t, "prefix": p, "interior": inter, "at": reaches(t, p, interior=inter)}
        for t in terms
        for p in PREFIXES
        for inter in (True, False)
    ]

    # ⚠️ THE MATCH POINTS THEMSELVES, SO THE STOPLIST CANNOT DRIFT. Two ports can agree
    # on every resolution over THIS vocabulary while disagreeing about which words are
    # generic — the disagreement would only surface on a name neither corpus contains.
    # Comparing the points per term compares the stoplist directly.
    points = [
        {"term": t, "interior": inter, "points": list(match_points(t, interior=inter))}
        for t in terms for inter in (True, False)
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT_FE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({
        "generated_by": "backend/scripts/gen_prefix_corpus.py",
        "rule_source": "backend/app/services/capture/prefix_resolve.py",
        "min_prefix": MIN_PREFIX,
        "vocab": [
            {"text": t, "kind": k, "carried": c, "form": f} for t, k, c, f in VOCAB_SPEC
        ],
        "generic_words": sorted(GENERIC_WORDS),
        "interior_kinds": sorted(INTERIOR_KINDS),
        "first_word_always_matches": FIRST_WORD_ALWAYS_MATCHES,
        "cases": cases,
        "walks": walks,
        "match_points": points,
    }, indent=2) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    OUT_FE.write_text(payload, encoding="utf-8")
    chosen = sum(1 for c in cases if c["outcome"] == "chosen")
    amb = sum(1 for c in cases if c["outcome"] == "ambiguous")
    none = sum(1 for c in cases if c["outcome"] == "none")
    print(f"{len(cases)} cases ({chosen} chosen / {amb} ambiguous / {none} none), "
          f"{len(walks)} walks, {len(points)} match-point rows "
          f"-> {OUT.relative_to(_ROOT)} + {OUT_FE.relative_to(_ROOT)}")
    # ⚠️ AN INTERIOR MATCH MUST ACTUALLY OCCUR IN THE CORPUS, or the ruling it encodes
    # is untested and every port agrees trivially.
    interior = sum(1 for r in points if r["interior"] and len(r["points"]) > 1)
    assert interior >= 3, f"only {interior} terms have an interior match point"
    # ⚠️ A CORPUS OF ALL-ONE-OUTCOME WOULD BE SATISFIED BY A RULE THAT ALWAYS RETURNS
    # THAT OUTCOME. Every branch must be represented or the corpus is not discriminating.
    assert chosen and amb and none, "the corpus does not exercise all three outcomes"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
