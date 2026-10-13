/**
 * A plain number typed while a pick is showing selects that option.
 *
 * ⚠️ RULED 2026-10-13, AND IT SUPERSEDES "typed digits go into the text" from
 * 2026-10-12. The earlier ruling reserved bare digits for the order text, on the
 * grounds that "3" might be a grave depth or a vault size — true, and the reason the
 * rule below is narrow rather than absent. Pressing 1 to pick is what a person
 * expects of a numbered list; ⌘1 still works and is unchanged.
 *
 * ⚠️ IT OPERATES ON THE TEXT, NOT ON A KEYPRESS, because the number must be REMOVED
 * from the order. A key handler would select the option and leave the digit sitting
 * in the sentence, where the next extraction would read it as a size or a year.
 *
 * ⚠️ FIVE CONDITIONS, AND EVERY ONE OF THEM EXISTS TO PROTECT A REAL NUMBER a
 * director types. The ruling names the cases; these are them:
 *
 *     a WHOLE token at the END       "monticello 1" picks. Mid-sentence numbers are
 *                                    not the one just typed, and consuming them
 *                                    retroactively would change settled text.
 *     in RANGE 1..N                  "34" and "1948" are out of range for a 2- or
 *                                    3-option pick and survive untouched.
 *     DIGITS ONLY                    "10am" and "10:00" are not bare numbers.
 *     no LEADING ZERO                "01" is a code or a date part, not a choice.
 *     not after a NUMBER LABEL       "lot 2", "section 3", "space 1" are places.
 *                                    This one is a vocabulary and so is stated as
 *                                    one; the other four are structural.
 */

/**
 * Words that take a number after them, so the number is part of the ANSWER.
 *
 * ⚠️ A VOCABULARY, AND THEREFORE THE WEAKEST OF THE FIVE CONDITIONS — it protects
 * what it lists and nothing else. It is short on purpose: every entry is a word the
 * capture surface actually has a field for (`grave_location`), so it is derived from
 * the thing being protected rather than from imagination. A word nobody has a field
 * for would be guesswork.
 */
export const NUMBER_LABELS: readonly string[] = [
  "lot",
  "lots",
  "section",
  "space",
  "spaces",
  "grave",
  "graves",
  "plot",
  "block",
  "tier",
  "row",
  "unit",
  "no",
  "number",
  "#",
]

export interface DigitPick {
  /** 1-based, as the options are numbered. */
  readonly index: number
  /** The order text with the chosen number removed. */
  readonly text: string
}

/**
 * Does `text` end with a bare number that selects one of `optionCount` options?
 *
 * Returns the 1-based index and the text to keep, or `null` to leave the text alone.
 */
export function consumePickDigit(
  text: string,
  optionCount: number,
): DigitPick | null {
  if (optionCount < 1) return null

  // ⚠️ THE TRAILING TOKEN ONLY, AND TRAILING SPACE IS NOT STRIPPED FIRST. "1 " means
  // the director typed the number and moved on; the number is still the last token
  // and still a choice. What must NOT match is a number with more text after it.
  const m = /(^|\s)([0-9]+)\s*$/.exec(text)
  if (m === null) return null

  const token = m[2]
  // ⚠️ NO LEADING ZERO. "01" is a code or part of a date, never an option number,
  // and `Number("01")` would quietly accept it as 1.
  if (token.length > 1 && token.startsWith("0")) return null

  const index = Number(token)
  if (!Number.isInteger(index) || index < 1 || index > optionCount) return null

  const before = text.slice(0, m.index + m[1].length)
  // ⚠️ THE PRECEDING WORD DECIDES WHETHER THIS IS A PLACE. "lot 2" is a grave
  // location; the 2 belongs to the order.
  const prev = /([A-Za-z#]+)\s*$/.exec(before)
  if (prev !== null && NUMBER_LABELS.includes(prev[1].toLowerCase())) return null

  // ⚠️ THE TRAILING WHITESPACE GOES WITH THE NUMBER, so "monticello 1" becomes
  // "monticello" and not "monticello " — otherwise the next keystroke extends a
  // phrase that has a stray gap in it.
  return { index, text: text.slice(0, m.index).replace(/\s+$/, "") }
}
