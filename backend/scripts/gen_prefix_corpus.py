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
    MIN_PREFIX,
    consume_loose,
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
]

PREFIXES = [
    "h", "ho", "hop", "hopk", "hope", "hopkins", "hopkins funeral home",
    "riv", "rivers", "r",
    "st", "st m", "st. m", "stm", "st mary", "st mi",
    "monti", "mont", "monticello", "m",
    "cam", "cameo", "cameo rose",
    "conti", "cont", "continental", 'continental 34"',
    "grav", "graveliner",
    "blargle", "zzz", "", " ",
]

KIND_SETS = {
    "funeral_home": ("funeral_home",),
    "cemetery": ("cemetery",),
    "vault": ("vault", "vault_alias"),
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

    # ⚠️ `consume_loose` IS CORPUS'D SEPARATELY FROM THE RESOLUTION, because a port can
    # agree on every final answer while differing on the walk — and the walk is what
    # produces the ghost's visible SUFFIX. "stm" vs "st m" is exactly that case.
    walks = [
        {"term": t, "prefix": p, "at": consume_loose(t, p)}
        for t in sorted({x[0] for x in VOCAB_SPEC})
        for p in PREFIXES
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
        "cases": cases,
        "walks": walks,
    }, indent=2) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    OUT_FE.write_text(payload, encoding="utf-8")
    chosen = sum(1 for c in cases if c["outcome"] == "chosen")
    amb = sum(1 for c in cases if c["outcome"] == "ambiguous")
    none = sum(1 for c in cases if c["outcome"] == "none")
    print(f"{len(cases)} cases ({chosen} chosen / {amb} ambiguous / {none} none), "
          f"{len(walks)} walks -> {OUT.relative_to(_ROOT)} + {OUT_FE.relative_to(_ROOT)}")
    # ⚠️ A CORPUS OF ALL-ONE-OUTCOME WOULD BE SATISFIED BY A RULE THAT ALWAYS RETURNS
    # THAT OUTCOME. Every branch must be represented or the corpus is not discriminating.
    assert chosen and amb and none, "the corpus does not exercise all three outcomes"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
