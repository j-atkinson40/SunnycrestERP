/**
 * The ghost and the extractor mean the same thing by an abbreviation.
 *
 * ⚠️ WHY THIS FILE EXISTS. James ruled on his 2026-10-20 walk that extraction must
 * accept abbreviations "using exactly the ghost's vocabulary and tie-break rules (one
 * source of truth, not a copy)". Two of those three are achievable literally and one
 * is not, and the distinction is worth stating because it decides what this test buys:
 *
 *   the vocabulary   ONE SOURCE, literally. `build_vocabulary` is the only producer;
 *                    the ghost is served those rows from `/capture/vocabulary` and the
 *                    extractor reads the same function in-process.
 *
 *   the tie-break    TWO IMPLEMENTATIONS, HELD TOGETHER. `prefix_resolve.py` runs on
 *                    the server; `resolvePrefix` here must stay client-side because
 *                    James ruled on 2026-10-16 that "matching is client-side only...
 *                    keystroke latency must not depend on the network". Neither can
 *                    call the other, so a copy is forced.
 *
 * ⚠️ SO THE COPY IS HELD BY A GENERATED ARTEFACT RATHER THAN BY CARE. The corpus is
 * produced FROM the Python rule by `backend/scripts/gen_prefix_corpus.py`; this replays
 * every case through the TypeScript rule. Change one side only and this goes red. It is
 * the same device the canvas validators use (CLAUDE.md: "Both validators MUST agree on
 * schema rules... The validators are tested cross-reference").
 *
 * ⚠️ IT COMPARES MEANING, NOT SUFFIXES, AND THAT BOUNDARY IS DELIBERATE. `completionFor`
 * additionally decides HOW MUCH to draw — on several matches it offers their longest
 * common prefix, which is a property of a text box and has no server equivalent.
 * `resolvePrefix` is the part that has one, so it is the part compared.
 */
import { describe, expect, it } from "vitest"

import corpus from "../../../../backend/tests/data/opas_prefix_corpus.json"
import { MIN_PREFIX, consumeLoose, resolvePrefix, type VocabTerm } from "./ghost"

interface Case {
  prefix: string
  kinds: string[] | null
  kind_set: string
  outcome: "none" | "chosen" | "ambiguous"
  chosen: string | null
  chosen_kind: string | null
  matches: string[]
}

const VOCAB: VocabTerm[] = corpus.vocab.map((t) => ({
  text: t.text,
  kind: t.kind,
  carried: t.carried,
  form: t.form,
}))

const CASES = corpus.cases as Case[]
const WALKS = corpus.walks as { term: string; prefix: string; at: number }[]

describe("the corpus itself", () => {
  it("⚠️ IS NON-EMPTY AND EXERCISES ALL THREE OUTCOMES", () => {
    // ⚠️ THE POSITIVE CONTROL, AND IT IS THE WHOLE DIFFERENCE BETWEEN THIS FILE AND A
    // FILE THAT PASSES BECAUSE IT CHECKS NOTHING. A corpus of all-"none" cases is
    // satisfied by a rule that always returns null, and an EMPTY corpus is satisfied
    // by anything at all — `[].forEach` runs no assertions and reports green.
    // CLAUDE.md §11: "require the control to be NON-ZERO, and read that number before
    // the result it is vouching for."
    expect(CASES.length).toBeGreaterThan(50)
    expect(WALKS.length).toBeGreaterThan(50)
    const kinds = new Set(CASES.map((c) => c.outcome))
    expect([...kinds].sort()).toEqual(["ambiguous", "chosen", "none"])
  })

  it("agrees with the ghost about the minimum prefix length", () => {
    // ⚠️ A FLOOR THAT DIFFERED WOULD MAKE THE TWO SIDES DISAGREE ON ONE-CHARACTER
    // INPUT ONLY — the narrowest possible divergence, and the easiest to never notice.
    expect(corpus.min_prefix).toBe(MIN_PREFIX)
  })

  it("names the rule it was generated from, so a reader can find the other side", () => {
    expect(corpus.rule_source).toContain("prefix_resolve.py")
    expect(corpus.generated_by).toContain("gen_prefix_corpus.py")
  })
})

describe("every case resolves the same on both sides", () => {
  it.each(CASES.map((c) => [`${c.kind_set}: ${JSON.stringify(c.prefix)}`, c] as const))(
    "%s",
    (_label, c) => {
      const got = resolvePrefix(c.prefix, VOCAB, c.kinds ?? undefined)
      if (c.outcome === "none") {
        expect(got).toBeNull()
        return
      }
      expect(got).not.toBeNull()
      if (got === null) return
      // ⚠️ THE MATCH SET IS COMPARED TOO, NOT ONLY THE CHOICE. Two rules can agree on
      // every final answer while disagreeing about what was in play — and the match set
      // is what the extractor turns into a choice list, so a divergence there is a
      // divergence in the question the director is asked.
      expect([...got.matches].map((m) => m.text).sort()).toEqual(c.matches)
      if (c.outcome === "chosen") {
        expect(got.chosen).not.toBeNull()
        expect(got.chosen?.text).toBe(c.chosen)
        expect(got.chosen?.kind).toBe(c.chosen_kind)
      } else {
        expect(got.chosen).toBeNull()
      }
    },
  )
})

describe("the character walk agrees too", () => {
  it("⚠️ EVERY TERM x EVERY PREFIX, because a port can agree on answers and differ on the walk", () => {
    // The walk produces the ghost's visible SUFFIX, so an off-by-one here draws "ry's
    // Cemetery" where it meant "ary's Cemetery" while every resolution still matches.
    // "stm" vs "st m" is exactly that case: punctuation is skipped, a space is a
    // boundary, and only the walk distinguishes them.
    const bad: string[] = []
    for (const w of WALKS) {
      const at = consumeLoose(w.term, w.prefix)
      if (at !== w.at) bad.push(`${w.term} / ${JSON.stringify(w.prefix)}: ts=${at} py=${w.at}`)
    }
    expect(bad).toEqual([])
  })

  it("⚠️ AND THE WALK CORPUS CONTAINS BOTH HITS AND MISSES", () => {
    // Without this, a walk corpus of all -1 would be satisfied by a function that
    // always returns -1.
    expect(WALKS.some((w) => w.at > 0)).toBe(true)
    expect(WALKS.some((w) => w.at === -1)).toBe(true)
  })
})
