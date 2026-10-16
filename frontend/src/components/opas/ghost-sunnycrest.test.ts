/**
 * James's walk, against HIS tenant's real vocabulary.
 *
 * ⚠️ THE FIXTURE IS A DUMP OF THE LIVE `sunnycrest` VOCABULARY, not a hand-written
 * one. `ghost.test.ts` pins the RULE with small invented fixtures, which is right for
 * a rule — but a hand-made fixture only ever contains the cases its author thought
 * of, and James walks a tenant with 101 terms in it. This file exists because my own
 * browser walk ran against TESTCO, whose catalog differs from his in exactly the ways
 * that decide these answers:
 *
 *   testco      carries NEITHER Monticello -> the FORM rule delivers "monti"
 *   sunnycrest  carries the burial vault   -> TENANT SCOPE delivers it
 *
 *   testco      has St. Mary's Cemetery AND St. Mary's Church -> "st m" stops at "C"
 *   sunnycrest  has only the cemetery                         -> full completion
 *
 * A green walk on testco therefore says less about his screen than it appears to.
 *
 * ⚠️ REGENERATE THE FIXTURE, DO NOT EDIT IT. It is produced by `build_vocabulary` on
 * the real tenant; hand-editing would make it a fixture modelled on what the test
 * wants rather than on what the tenant has.
 */
import { describe, expect, it } from "vitest"

import { acceptGhost, completionFor, type VocabTerm } from "./ghost"
import FIXTURE from "./__fixtures__/sunnycrest-vocabulary.json"

const VOCAB = FIXTURE as VocabTerm[]
const end = (s: string) => s.length

describe("the fixture itself", () => {
  it("is the real tenant's vocabulary, not a stub", () => {
    // ⚠️ THE CONTROL. Every assertion below is satisfiable by an empty list in the
    // wrong direction (null everywhere), so the shape is asserted first.
    expect(VOCAB.length).toBeGreaterThan(50)
    expect(VOCAB.some((t) => t.kind === "vault" && t.form)).toBe(true)
    expect(VOCAB.some((t) => t.carried)).toBe(true)
  })
})

describe("James's walk on sunnycrest", () => {
  it('"order for hop" offers "kins Funeral Home"', () => {
    const g = completionFor("order for hop", end("order for hop"), VOCAB)
    expect(g?.suffix).toBe("kins Funeral Home")
    expect(acceptGhost("order for hop", g!)).toBe("order for hopkins Funeral Home ")
  })

  it('"monti" offers "cello Burial Vault" — here by TENANT SCOPE', () => {
    // sunnycrest carries the burial vault and not the urn vault, so step 5 resolves
    // it before the form rule is reached. On testco it is the other way round.
    const monti = VOCAB.filter((t) => t.text.toLowerCase().startsWith("monticello"))
    expect(monti.filter((t) => t.carried).map((t) => t.text)).toEqual([
      "Monticello Burial Vault",
    ])
    expect(completionFor("monti", end("monti"), VOCAB)?.suffix).toBe("cello Burial Vault")
  })

  it('"st m" offers the WHOLE cemetery name here', () => {
    /**
     * ⚠️ AND THE NEAR-MISSES ARE THE INTERESTING PART. sunnycrest also stocks
     * `Stainless Steel Triune Burial Vault` and `...Urn Vault`, which begin "St".
     * They do not match because a SPACE in the prefix forces a word boundary in the
     * term: after "st" the walk skips to the next word, and "Steel" does not start
     * with "m". Without that boundary rule "st m" would be ambiguous on his tenant
     * and offer only "ainless " — the opposite of what he asked for.
     */
    expect(VOCAB.filter((t) => t.text.toLowerCase().startsWith("st")).length)
      .toBeGreaterThan(1)
    expect(completionFor("st m", end("st m"), VOCAB)?.suffix).toBe("ary's Cemetery")
  })

  it('"hopkins fu" offers "neral Home"', () => {
    expect(completionFor("hopkins fu", end("hopkins fu"), VOCAB)?.suffix)
      .toBe("neral Home")
  })

  it("offers nothing for a word his catalog does not contain", () => {
    expect(completionFor("blargl", end("blargl"), VOCAB)).toBeNull()
  })
})
