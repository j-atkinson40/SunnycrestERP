/**
 * What "the vault" means when an order is in front.
 *
 * ⚠️ JAMES'S RULING, 2026-10-20: "It remembers what you're looking at. With an order in
 * front, 'the vault', 'the funeral home', 'when's the service?' and 'undo confirm' all
 * mean *that* order. ... Context is what makes it feel like a conversation instead of one
 * command at a time."
 *
 * ⚠️ TWO KINDS, AND THE DIFFERENCE IS WHETHER ANYTHING OPENS. The dispatch separates
 * them: "the vault" / "the cemetery" / "undo confirm" ACT; "when's the service" /
 * "what's the total" / "who's it for" are "answered in the reply line without opening
 * anything". A question that opened a pane would be a worse answer than a sentence.
 *
 * ⚠️ AN EXACT PHRASE TABLE, NOT A KEYWORD SCAN, and the dispatch asks for the list for
 * exactly this reason: "List the exact phrasings supported, so James knows the edge." A
 * `\bvault\b` rule would swallow "monticello vault" — a catalog request — and
 * "order for hopkins monticello vault", which starts a capture. The edge of a table is
 * readable; the edge of a keyword scan is not.
 *
 * ⚠️ FOUR OF THESE PHRASES ARE ALSO ORDER-LIST PHRASES, AND THAT OVERLAP IS LIVE RATHER
 * THAN THEORETICAL. `order-list-routing.isOrderListPhrase` matches `/\bhow much\b/` and
 * `/what(?:'s| is) the total/`, so "how much", "how much is it", "what's the total" and
 * "what is the total" have two meanings:
 *
 *     an ORDER in front   -> that order's total, from here
 *     anything else        -> the order list's own total question, unchanged
 *
 * ⚠️ AND ONE EDGE TURNS ON AN APOSTROPHE, stated because a reader will hit it. With NO
 * order in front, `"what's the total"` matches the order-list regex and goes to the list;
 * `"whats the total"` does not match it (the regex wants an apostrophe or " is") and so
 * gets "No order is open" from here instead. Two spellings, two messages. Left as it is:
 * the alternative was editing `isOrderListPhrase`, a shipped rule with its own tests, to
 * buy a better sentence in a state where neither answer is wrong.
 *
 * ⚠️ AND IT IS ONLY CONSULTED WITH AN ORDER PANE IN FRONT. `OpasHost` checks the front
 * pane before calling in here, so none of these phrases shadows anything while the
 * director is looking at a catalog or typing an order. With no order in front the host
 * asks "Which order?" rather than guessing — which is the dispatch's own instruction.
 */

/** Something to do to the order in front. */
export type ContextAction =
  /** Open the order's vault in the Product Pane. */
  | "vault"
  /** The Customer Pane does not exist yet — the host says so rather than nothing. */
  | "customer"
  /** The Cemetery Pane does not exist yet — same. */
  | "cemetery"
  /** Run the existing confirmed -> draft transition. */
  | "undo-confirm"

/** Something to answer about the order in front, in the reply line. */
export type ContextQuestion = "service" | "total" | "who" | "where" | "status"

export type ContextIntent =
  | { readonly kind: "act"; readonly action: ContextAction }
  | { readonly kind: "answer"; readonly question: ContextQuestion }

/**
 * Every phrasing supported, exactly. This table IS the documentation the dispatch asks
 * for; there is no second list.
 *
 * ⚠️ NORMALISED BEFORE COMPARISON — lower-cased, punctuation stripped, whitespace
 * collapsed — so "When's the service?" and "whens the service" are the same key and only
 * one spelling of each is listed. That is why no entry carries an apostrophe.
 */
export const CONTEXT_PHRASES: Readonly<Record<string, ContextIntent>> = {
  // ── act ───────────────────────────────────────────────────────────────
  "the vault": { kind: "act", action: "vault" },
  "vault": { kind: "act", action: "vault" },
  "open the vault": { kind: "act", action: "vault" },
  "show the vault": { kind: "act", action: "vault" },

  "the funeral home": { kind: "act", action: "customer" },
  "the customer": { kind: "act", action: "customer" },
  "open the funeral home": { kind: "act", action: "customer" },
  "open the customer": { kind: "act", action: "customer" },

  "the cemetery": { kind: "act", action: "cemetery" },
  "open the cemetery": { kind: "act", action: "cemetery" },

  "undo confirm": { kind: "act", action: "undo-confirm" },
  "undo the confirm": { kind: "act", action: "undo-confirm" },
  "unconfirm": { kind: "act", action: "undo-confirm" },
  "make it a draft": { kind: "act", action: "undo-confirm" },

  // ── answer, in the reply line, opening nothing ────────────────────────
  "whens the service": { kind: "answer", question: "service" },
  "when is the service": { kind: "answer", question: "service" },
  "when": { kind: "answer", question: "service" },
  "the service": { kind: "answer", question: "service" },
  "service": { kind: "answer", question: "service" },
  "whats the service": { kind: "answer", question: "service" },

  "whats the total": { kind: "answer", question: "total" },
  "what is the total": { kind: "answer", question: "total" },
  "the total": { kind: "answer", question: "total" },
  "total": { kind: "answer", question: "total" },
  "how much": { kind: "answer", question: "total" },
  "how much is it": { kind: "answer", question: "total" },

  "whos it for": { kind: "answer", question: "who" },
  "who is it for": { kind: "answer", question: "who" },
  "who is it": { kind: "answer", question: "who" },

  "where is it going": { kind: "answer", question: "where" },
  "wheres it going": { kind: "answer", question: "where" },

  "where is it": { kind: "answer", question: "status" },
  "wheres it at": { kind: "answer", question: "status" },
  "what stage": { kind: "answer", question: "status" },
  "whats the status": { kind: "answer", question: "status" },
}

/**
 * Lower-case, drop apostrophes, turn every other non-alphanumeric run into one space.
 *
 * ⚠️ APOSTROPHES ARE DROPPED, NOT REPLACED WITH A SPACE, AND A TEST CAUGHT THE
 * DIFFERENCE. Written as one `[^a-z0-9]+ -> " "` pass, `"when's the service"` becomes
 * `"when s the service"` — four tokens, no table key, and `contextIntent` returned null
 * for the dispatch's own example phrase. The same would hit `"St. Mary's"` and
 * `"who's it for"`. Both the straight and the curly apostrophe are dropped, because a
 * browser's smart quotes produce the curly one.
 */
export function normalizePhrase(text: string): string {
  return text
    .toLowerCase()
    .replace(/['\u2019]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ")
}

/** The intent this phrase names about the order in front, or `null`. */
export function contextIntent(text: string): ContextIntent | null {
  return CONTEXT_PHRASES[normalizePhrase(text)] ?? null
}

/**
 * ⚠️ TRUE FOR A PHRASE THE TABLE KNOWS, WHATEVER IS IN FRONT — which is what lets the
 * host answer "Which order?" instead of sending "the vault" to the catalog resolver,
 * where it would match nothing and open an unfiltered catalog. The dispatch: "With no
 * order in front, the same phrases ask: 'Which order?'"
 */
export function isContextPhrase(text: string): boolean {
  return contextIntent(text) !== null
}
