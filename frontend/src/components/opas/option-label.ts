/**
 * When the grey option label adds something, and when it just restates the name.
 *
 * ⚠️ A PRESENTATION RULE, FRONTEND ONLY. The API keeps sending `option_label` — a server
 * that withheld it would make the decision for every future surface, and the driver's
 * screen or a spec sheet may want it where a list row does not.
 *
 * THE RULE (James, 2026-10-06): hide the label when EVERY word in it already appears in
 * the product name, case-insensitive, treating `34"` and `34 inch` as equal.
 *
 * ⚠️ IT COMPARES AGAINST THE NAME THE ROW ACTUALLY SHOWS — the variant's `display_name`,
 * not the template's. Measured both ways over the real 52: against the variant name the
 * rule hides 50 and shows 2; against the template name it shows 35. The `34 inch` case
 * only comes out right against the variant name (`Continental 34"` contains the size;
 * `Continental Burial Vault` does not), and that case was explicit in the dispatch.
 *
 * ⚠️ AND IT DIVERGES FROM THE DISPATCH ON ONE ITEM, DELIBERATELY UNRESOLVED. The expected
 * list said `Social Service` would stay. It HIDES, because the variant is displayed as
 * `Graveliner (Social Service)` — the label is degenerate against the shown name by the
 * same test that hides `34 inch`. The two expectations cannot both hold under one
 * comparison target; the distinction being reached for is grade-vs-size, which this rule
 * cannot see. Reported for a ruling rather than papered over with an exception.
 *
 * The canonical justification is already on record — map §R7: "`Continental` as an option
 * label is DEGENERATE — it restates the product rather than naming a value on any axis."
 */

/**
 * Words of a string, with inch-marks folded to the word `inch`.
 *
 * ⚠️ `34"`, `34”` and `34 inch` are the same value. Without the fold, `Continental 34"`
 * would not contain the words of `34 inch` and the label would show — which is the case the
 * dispatch called out by name.
 */
export function labelWords(s: string): string[] {
  const folded = s
    .toLowerCase()
    .replace(/["”]/g, " inch ")
    .replace(/''/g, " inch ")
  return folded
    .replace(/[^a-z0-9]+/g, " ")
    .split(" ")
    .filter((w) => w !== "")
}

/**
 * True when the label should be hidden because the name already says it.
 *
 * ⚠️ AN EMPTY OR BLANK LABEL IS NOT "CONTAINED" — it is nothing to show, and reporting it
 * as hidden-because-redundant would be a different claim. Callers get `false` and the
 * absent-key check does the rest.
 */
export function labelIsRedundant(optionLabel: string | undefined, name: string): boolean {
  if (optionLabel === undefined) return false
  const words = labelWords(optionLabel)
  if (words.length === 0) return false
  const inName = new Set(labelWords(name))
  return words.every((w) => inName.has(w))
}


/** The minimum a row needs for label resolution. */
export interface LabelableRow {
  readonly variant_template_id: string
  readonly name: string
  readonly kind: string
  readonly option_label?: string
  /** The family/line name — `product_templates.display_name`. The disambiguator. */
  readonly product_name?: string
}

/**
 * The label each row should show, once collisions are accounted for.
 *
 * ⚠️ TWO RULES, IN ORDER, AND THE SECOND OVERRIDES THE FIRST:
 *
 *   1. hide a label whose every word is already in the name (`labelIsRedundant`)
 *   2. where two or more rows in the SAME GROUP would then render IDENTICALLY, show the
 *      LINE NAME on each instead
 *
 * ⚠️ RULE 2 IS GENERAL, NOT AN URN SPECIAL CASE. Measured 2026-10-07 across the 52: three
 * colliding sets, all in `urn`, six rows — `Cream & Gold`, `Pebble Dust` and `White & Silver`
 * each existing in both `Regal Line` (P300…) and `Tribute Line` (P310…). Keyed on the
 * RENDERED pair rather than on the kind, so a collision appearing in burial vaults tomorrow
 * is handled without an edit.
 *
 * ⚠️ IT IS KEYED ON WHAT RULE 1 LEAVES, NOT ON THE RAW LABEL — and the first version of
 * this comment justified that with a false claim. It said "checking raw labels would have
 * found no collision at all" for the measured urns. WRONG: both urns carry `option_label`
 * equal to their own name, so their RAW labels are identical too and raw-keying finds that
 * collision perfectly well. A break test keying on the raw label came back GREEN, which is
 * how the claim was caught.
 *
 * The distinction bites only where two rows share a name and carry DIFFERENT raw labels that
 * BOTH hide — `X` with labels `X` and `x`, say. Raw-keying sees two different labels and no
 * collision; keying on rule 1's result sees two blanks and one. That case now has a test
 * (`different raw labels that both hide ARE a collision`), so the break fires.
 *
 * Returns a map of variant id -> label to render, omitting ids that should show none.
 */
export function resolveRowLabels(
  rows: readonly LabelableRow[],
): Readonly<Record<string, string>> {
  // pass 1 — what rule 1 leaves
  const afterRule1 = new Map<string, string | undefined>()
  for (const r of rows) {
    afterRule1.set(
      r.variant_template_id,
      r.option_label !== undefined && !labelIsRedundant(r.option_label, r.name)
        ? r.option_label
        : undefined,
    )
  }

  // pass 2 — which rendered pairs are shared by more than one row in the same group
  const seen = new Map<string, LabelableRow[]>()
  for (const r of rows) {
    const key = `${r.kind}\u0000${r.name}\u0000${afterRule1.get(r.variant_template_id) ?? ""}`
    const bucket = seen.get(key)
    if (bucket === undefined) seen.set(key, [r])
    else bucket.push(r)
  }

  const out: Record<string, string> = {}
  for (const r of rows) {
    const label = afterRule1.get(r.variant_template_id)
    if (label !== undefined) out[r.variant_template_id] = label
  }
  for (const bucket of seen.values()) {
    if (bucket.length < 2) continue
    for (const r of bucket) {
      // ⚠️ NO FALLBACK TO THE id OR THE SKU. If the line name is missing there is nothing
      // honest to show, and an id would be noise rather than disambiguation — the rows stay
      // identical and that remains visibly true.
      if (r.product_name !== undefined && r.product_name !== "") {
        out[r.variant_template_id] = r.product_name
      }
    }
  }
  return out
}
