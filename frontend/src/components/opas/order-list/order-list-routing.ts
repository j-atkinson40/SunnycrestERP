/**
 * Whether a typed line is about orders.
 *
 * ⚠️ A GATE, NOT A PARSER. The server owns the question. This only decides
 * whether the line is sent there, so a catalog phrase still reaches the catalog
 * and an order phrase does not.
 */
const MONTH =
  "january|february|march|april|may|june|july|august|september|october|november|december"

function cleaned(text: string): string {
  return text.toLowerCase().trim().replace(/[.!?,;:]+$/g, "").replace(/\s+/g, " ")
}

/**
 * An order number, mirroring `question._ORDER_NUMBER` on the server.
 *
 * ⚠️ A MIRROR, AND IT IS A GATE RATHER THAN A PARSER — same contract as the rest of this
 * file. The SERVER decides which order "0002" names; this only decides that the line is
 * about orders at all, because "0002" contains no word and every other test here looks
 * for one. Without it the bar sent "SO-2026-0002" to the catalog resolver, which matched
 * no product and opened an unfiltered catalog.
 *
 * ⚠️ 3-4 DIGITS FOR THE BARE FORM, matching the server's own bound. A 1-2 digit line is
 * what the bar's ⌘1..9 pick settles; routing "2" here would collide with answering
 * "which one?".
 */
export const ORDER_NUMBER =
  /^(?:open |show )?(?:so[\s\-_]?)?(?:\d{4}[\s\-_]\d{1,4}|\d{3,4})$/i

export function isOrderNumber(text: string): boolean {
  return ORDER_NUMBER.test(cleaned(text))
}

export function isOrderListPhrase(text: string): boolean {
  const t = cleaned(text)
  if (/\borders?\b/.test(t)) return true
  if (isOrderNumber(t)) return true
  if (/going out/.test(t)) return true
  if (/\binvoic/.test(t)) return true
  if (/\bdelivered\b/.test(t)) return true
  if (/\b(this|last) month\b/.test(t)) return true
  if (new RegExp(`\\bsince (${MONTH})\\b`).test(t)) return true
  if (/on the (lens|glasses)/.test(t)) return true
  if (/\bhow much\b/.test(t)) return true
  if (/what(?:'s| is) the total/.test(t)) return true
  return false
}

/** A follow-up that only means something while an order list is already open. */
export function isOrderRefinement(text: string): boolean {
  const t = cleaned(text)
  if (/^(only|just) /.test(t)) return true
  if (/^not invoiced\b/.test(t)) return true
  if (/^(this|last) month$/.test(t)) return true
  if (new RegExp(`^since (${MONTH})$`).test(t)) return true
  if (/ order$/.test(t)) return true
  if (/^how much\b/.test(t)) return true
  if (/^what(?:'s| is) the total/.test(t)) return true
  return false
}

/**
 * What opens the rulebook from the bar.
 *
 * ⚠️ MIRRORED FROM `order_list/rulebook.py`'s `_OPENERS`, AND THE MIRROR IS CHECKED.
 * `tests/test_rulebook.py::test_the_two_opener_lists_agree` reads THIS FILE and compares
 * the two sets, so a phrase added to one side and not the other turns the backend red.
 * That is the same arrangement `GENERIC_WORDS` has with `ghost.ts` and for the same
 * reason: a predicate the client needs locally cannot be a round trip, and two copies
 * that nothing compares will drift.
 *
 * ⚠️ WHY THE CLIENT NEEDS IT AT ALL, since `ask` already answers "rules" with
 * `open_rulebook`: the reason stage of Opas's "why?" has to tell a REASON from a NEW
 * REQUEST without asking the server, because the server has not been told there is a
 * question outstanding. Without this, typing "rules" at that moment would be recorded
 * as somebody's explanation.
 *
 * ⚠️ EXACT PHRASES, NOT A STEM. "ruled", "rule out" and "the rules of thumb" are not
 * requests for the rulebook.
 */
const RULEBOOK_OPENERS: readonly string[] = [
  "the rulebook",
  "rulebook",
  "rules",
  "the rules",
  "open the rulebook",
  "show the rulebook",
  "show me the rulebook",
  "open rules",
  "show rules",
]

export function opensRulebook(text: string): boolean {
  return RULEBOOK_OPENERS.includes(cleaned(text))
}
