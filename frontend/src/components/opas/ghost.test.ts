/**
 * The ghost's tie-break rule. James 2026-10-16, step 3.
 *
 * ⚠️ THE RULE IS THE FEATURE. Rendering faint text after a caret is easy; deciding
 * WHEN there is one honest answer is the whole of it. A completion that fires on an
 * ambiguous prefix inserts a word the director did not choose, into a sentence that
 * becomes an order.
 */
import { describe, expect, it } from "vitest"

import { acceptGhost, completionFor, type VocabTerm } from "./ghost"

const t = (
  text: string, kind = "vault", carried = false, form: string | null = null,
): VocabTerm => ({ text, kind, carried, form })

const SUNNYCREST: VocabTerm[] = [
  t("Hopkins Funeral Home", "funeral_home", true),
  t("St. Mary's Cemetery", "cemetery", true),
  t("Monticello Burial Vault", "vault", true, "burial_vault"),
  t("Monticello Urn Vault", "vault", false, "urn_vault"),
  t("Continental Burial Vault", "vault", true, "burial_vault"),
  t("Continental 34\"", "vault", false, "burial_vault"),
]

/**
 * ⚠️ A TENANT THAT STOCKS BOTH MONTICELLO FORMS — the fixture James's 2026-10-16
 * ruling asks for by name. Tenant scoping alone cannot save this case: BOTH are
 * carried, so step 5 leaves two matches and the common prefix would offer only
 * "cello ". The form default is what makes it one answer.
 */
const STOCKS_BOTH: VocabTerm[] = [
  t("Monticello Burial Vault", "vault", true, "burial_vault"),
  t("Monticello Urn Vault", "vault", true, "urn_vault"),
  t("Continental Burial Vault", "vault", true, "burial_vault"),
  t("Continental 34\"", "vault", true, "burial_vault"),
]

const end = (s: string) => s.length

describe("James's own verify lines", () => {
  it('"order for hop" offers "kins Funeral Home"', () => {
    const g = completionFor("order for hop", end("order for hop"), SUNNYCREST)
    expect(g?.suffix).toBe("kins Funeral Home")
    expect(g?.term.text).toBe("Hopkins Funeral Home")
  })

  it('"monti" offers "cello Burial Vault" — via tenant precedence', () => {
    /**
     * ⚠️ THIS IS THE CASE THAT FORCED STEP 5 OF THE RULE. The platform catalog holds
     * BOTH `Monticello Burial Vault` and `Monticello Urn Vault`, measured 2026-10-16.
     * Across the whole catalog "monti" is ambiguous and the dispatch's own tie-break
     * would offer nothing — contradicting this very verify line. Sunnycrest carries
     * only the burial vault, so scoping to what the tenant stocks leaves one answer.
     */
    const g = completionFor("monti", end("monti"), SUNNYCREST)
    expect(g?.suffix).toBe("cello Burial Vault")
  })

  it('"hopkins fu" offers "neral Home" — a multi-word prefix', () => {
    const g = completionFor("hopkins fu", end("hopkins fu"), SUNNYCREST)
    expect(g?.suffix).toBe("neral Home")
  })

  it('"st m" offers "ary\'s Cemetery" when unambiguous', () => {
    const g = completionFor("st m", end("st m"), SUNNYCREST)
    expect(g?.suffix).toBe("ary's Cemetery")
  })
})

describe("when it must stay silent", () => {
  it("offers nothing below 2 characters", () => {
    expect(completionFor("m", 1, SUNNYCREST)).toBeNull()
  })

  it("offers nothing when the caret is not at the end", () => {
    // ⚠️ A COMPLETION INSERTED WHERE THE DIRECTOR IS NOT LOOKING is worse than none.
    expect(completionFor("hopkins fu", 3, SUNNYCREST)).toBeNull()
  })

  it("offers nothing after a trailing space", () => {
    expect(completionFor("hopkins ", end("hopkins "), SUNNYCREST)).toBeNull()
  })

  it("offers nothing for a word in no term", () => {
    expect(completionFor("blargle", end("blargle"), SUNNYCREST)).toBeNull()
  })

  it("never completes from a SHORTER prefix than the one typed", () => {
    /**
     * ⚠️ MY FIRST VERSION OF THIS TEST EXPECTED `null` AND WAS WRONG ABOUT THE RULE I
     * HAD JUST WRITTEN. "st m" matches `St. Mary's Cemetery` and `St. Mark's Chapel`;
     * those two agree as far as "St. Mar", so step 7 offers "ar" — that is the
     * common-prefix rule working, not a fallback.
     *
     * ⚠️ WHAT THE TEST IS ACTUALLY FOR is the thing that would be dangerous: an
     * ambiguous two-word prefix must not silently degrade into a confident completion
     * of something that only matches ONE word of it. "st m" must never offer
     * "onticello Burial Vault".
     */
    const vocab = [
      t("St. Mary's Cemetery", "cemetery", true),
      t("St. Mark's Chapel", "service_location", true),
      t("Monticello Burial Vault", "vault", true),
    ]
    const g = completionFor("st m", end("st m"), vocab)
    expect(g?.suffix).toBe("ar")
    expect(g?.term.text).not.toContain("Monticello")

    // and when the two share nothing beyond what was typed, it stays silent
    const noShare = [
      t("St. Mary's Cemetery", "cemetery", true),
      t("St. Peter's Chapel", "service_location", true),
    ]
    expect(completionFor("st ", end("st "), noShare)).toBeNull()
  })})

describe("the form default (James, 2026-10-16)", () => {
  it('offers "cello Burial Vault" on a tenant stocking BOTH forms', () => {
    const g = completionFor("monti", end("monti"), STOCKS_BOTH)
    expect(g?.suffix).toBe("cello Burial Vault")
    expect(g?.term.form).toBe("burial_vault")
  })

  it("is what saves the case once tenant scoping cannot", () => {
    // ⚠️ THE CONTROL FOR THE RULING'S OWN REASONING. Without the form rule these two
    // carried terms would fall to the common prefix and offer only "cello ".
    const withoutForms = STOCKS_BOTH.map((x) => ({ ...x, form: null }))
    expect(completionFor("monti", end("monti"), withoutForms)?.suffix).toBe("cello ")
  })

  it("does NOT fire when the matches differ by more than form", () => {
    /**
     * ⚠️ IT MIRRORS THE CAPTURE'S CONDITION EXACTLY — `discriminators === ("form",)`,
     * not "form is among them". `Continental Burial Vault` and `Continental 34"` are
     * both burial vaults differing by SIZE; the capture refuses to guess there and so
     * does this. A looser rule would pick a size for the office.
     *
     * ⚠️ AND A BREAK TEST SHOWED WHICH GUARD ACTUALLY DOES THE WORK HERE. Patching the
     * stem comparison changes nothing for this case: both matches share
     * `burial_vault`, so the DISTINCT-FORMS guard returns false before the stems are
     * compared. The stem check protects a different case — two different forms whose
     * names differ by more than the form word. Breaking the whole predicate is what
     * turns this red.
     */
    const g = completionFor("contin", end("contin"), STOCKS_BOTH)
    expect(g?.suffix).toBe("ental ")
  })

  it("does not fire when every match shares one form", () => {
    const sameForm = [
      t("Monticello Burial Vault", "vault", true, "burial_vault"),
      t("Monticello Deluxe Vault", "vault", true, "burial_vault"),
    ]
    expect(completionFor("monti", end("monti"), sameForm)?.suffix).toBe("cello ")
  })
})

describe("several matches", () => {
  it("completes as far as they AGREE and stops", () => {
    // Neither is carried, so both count; they share "Monticello ".
    const both = [t("Monticello Burial Vault"), t("Monticello Urn Vault")]
    const g = completionFor("monti", end("monti"), both)
    expect(g?.suffix).toBe("cello ")
  })

  it("offers nothing when they share no more than what was typed", () => {
    const g = completionFor("c", end("c"), [t("Cat"), t("Cow")])
    expect(g).toBeNull() // also below MIN_PREFIX
    const g2 = completionFor("co", end("co"), [t("Cost"), t("Cow")])
    expect(g2).toBeNull()
  })

  it("prefers what the tenant carries over what it does not", () => {
    const g = completionFor("contin", end("contin"), SUNNYCREST)
    expect(g?.term.text).toBe("Continental Burial Vault")
  })
})

describe("accepting it", () => {
  it("inserts the remainder AND a space", () => {
    // ⚠️ THE SPACE IS PART OF THE RULING — "inserts the remainder plus a space" — so
    // the next word can start without the director reaching for the spacebar.
    const g = completionFor("order for hop", end("order for hop"), SUNNYCREST)!
    expect(acceptGhost("order for hop", g)).toBe("order for hopkins Funeral Home ")
  })

  it("APPENDS, leaving what the director typed alone", () => {
    /**
     * ⚠️ MY FIRST VERSION OF THIS TEST ASSERTED THE NICER BEHAVIOUR AND WAS WRONG
     * ABOUT THE RULING. James: "Tab accepts (inserts the remainder plus a space)" —
     * the remainder, not a replacement. So "hop" + Tab gives "hopkins Funeral Home",
     * keeping the director's lowercase h rather than rewriting it to the record's
     * capitalisation.
     *
     * ⚠️ IT COSTS NOTHING DOWNSTREAM: every resolver here is case-insensitive, and
     * the typed casing is what `deceased_name` is stored as anyway. Replacing the
     * typed text would be a second ruling, not an implementation detail — flagged.
     */
    const g = completionFor("monti", end("monti"), SUNNYCREST)!
    expect(acceptGhost("monti", g)).toBe("monticello Burial Vault ")
  })
})

describe("an empty vocabulary", () => {
  it("offers nothing rather than throwing", () => {
    // ⚠️ THE FETCH CAN FAIL OR BE IN FLIGHT. The bar must type normally meanwhile.
    expect(completionFor("hop", 3, [])).toBeNull()
  })
})
