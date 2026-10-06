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
