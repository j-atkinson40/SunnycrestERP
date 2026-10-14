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

export function isOrderListPhrase(text: string): boolean {
  const t = cleaned(text)
  if (/\borders?\b/.test(t)) return true
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
