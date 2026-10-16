/**
 * The typed-capture endpoints. Four calls, no logic.
 *
 * ⚠️ INTERFACE ONLY, on purpose. The server decides what is answered and what is
 * missing — that is the standing ruling (`The model extracts; the server decides what is
 * missing`, DECISIONS 2026-09-22) and it is why `CaptureState`'s five sets arrive
 * computed rather than being derived here. A client that re-derived them would be the
 * second source of truth the capture engine was built to remove.
 *
 * ⚠️ `apiClient` DEFAULT-EXPORTS. Writing `import { apiClient }` type-checks against a
 * module that has no such named export in some editors and fails at `tsc`; it has bitten
 * this codebase before (CLAUDE.md §11, the fixtures-modelled-on-the-implementation
 * entry). Default import, deliberately.
 */
import apiClient from "@/lib/api-client"

/** One row as the capture surface renders it. Four states, from `rows.py::RowState`. */
export interface CaptureRow {
  readonly row_id: string
  readonly label: string
  /** `done` | `needed` | `not_mentioned` | `not_configured` */
  readonly state: string
  readonly value: string | null
  readonly secondary_value: string | null
  /** Template fields this row sources that are in the MISSING set.
   *
   *  ⚠️ THE PILL AND THE AMBER BOTH DERIVE FROM THIS, so "the pill count equals the
   *  number of amber-able rows" holds by construction rather than by two call sites
   *  happening to agree. The pill used to count missing FIELDS while the colour
   *  belonged to ROWS, and two missing fields can share one row — so "2 needed"
   *  could mean one amber row, which is what James read off the screen.
   *
   *  ⚠️ OPTIONAL, because a server older than this deploy does not send it. An
   *  absent list reads as "nothing missing on this row", which is the safe way to be
   *  wrong: no amber rather than a crash. */
  readonly missing_field_ids?: readonly string[]
  /** ⚠️ EVERY field this row sources, not just the missing ones — the handle for the
   *  row -> span link. Optional because an older server does not send it. */
  readonly field_ids?: readonly string[]
}

/** An ambiguous resolution awaiting a numbered pick. */
export interface CapturePick {
  readonly field_id: string
  readonly phrase: string
  /** `[value_to_store, label_to_show]` — the label carries the town for a party. */
  readonly options: readonly [string, string][]
  readonly discriminator: string | null
}

export interface VocabTerm {
  readonly text: string
  readonly kind: string
  readonly carried?: boolean
  readonly note?: string | null
  readonly form?: string | null
}

export interface CaptureSpan {
  readonly start: number
  readonly end: number
  readonly state: "captured" | "conflict" | "unrecognized"
  readonly field_ids: readonly string[]
}

export interface CaptureState {
  readonly session_id: string
  /** ⚠️ THE WHOLE TYPED TEXT, AND IN THE TYPED PANE IT IS THE SOURCE. `null` means the
   *  session has no whole-text record — it was captured line-by-line — which is a
   *  DIFFERENT FACT from `""`, the director having cleared the bar. The pane restores
   *  the bar from this on mount, so `?? ""` at the point of use is correct and
   *  `|| ""` at the point of reading would destroy the distinction. */
  readonly full_text: string | null
  /** field_id -> the value the director CHOSE. Returned so a reload restores settled
   *  picks instead of re-asking every question. */
  readonly resolutions: Readonly<Record<string, unknown>>
  /** The prospective order lines. ⚠️ `null` UNTIL REVIEW, AND `null` IS NOT `[]`.
   *  An empty array says "this order has nothing to bill", which is a blocker;
   *  `null` says the question has not been asked yet. */
  readonly lines?: readonly {
    readonly kind: string
    readonly description: string
    readonly product_id: string | null
    /** A decimal STRING, not a number — the server speaks money in strings and
     *  `parseFloat` at the edge is where cents go missing. Rendered as given. */
    readonly unit_price: string | null
    readonly quantity: string
    readonly line_total: string
  }[] | null
  /** The order total as a decimal string, or `null` outside review. */
  readonly total?: string | null
  /** Every reason Approve cannot run, in the office's words. `null` outside review. */
  readonly blockers?: readonly string[] | null
  readonly can_approve?: boolean
  /**
   * What pressing Approve will set in motion, in the server's words, from the real
   * data — e.g. "Confirms the order · Delivered Tue Oct 20 · Invoiced at month end
   * (Hopkins)". Null when the order is not approvable.
   *
   * ⚠️ THE SERVER COMPOSES IT, DELIBERATELY. It depends on the customer's billing
   * preference AND the tenant's invoice-email switch, neither of which the pane has;
   * rebuilding the sentence here would be a second answer to "what will happen" that
   * could disagree with the one the press obeys.
   */
  readonly approve_effect?: string | null
  /** The missing fields in the office's words, for the bar's own sentence. */
  readonly missing_labels?: readonly string[]
  /** ⚠️ TRANSIENT: somebody just tried to finish this order, so the rows go amber.
   *  Not a property of the order — a plain read returns `false`. A typed completion
   *  phrase is detected on the SERVER, which is why this has to come back in the
   *  response rather than being tracked only by the client. */
  readonly completion_attempt?: boolean
  /** Set once approved. ⚠️ THESE TWO ARE HOW THE PANE KNOWS IT IS DONE — the status
   *  says `approved` and these name what was created. */
  readonly sales_order_id?: string | null
  readonly sales_order_number?: string | null
  /** ⚠️ OPTIONAL BECAUSE AN OLDER SERVER DOES NOT SEND IT. The 2026-10-12 blank-pane
   *  defect was a required key an older server omitted; every field added since is
   *  optional at the type level for that reason. */
  readonly next_question?: string | null
  /** Claimed spans over `spans_for_text`, in whole-text coordinates. */
  readonly spans?: readonly CaptureSpan[]
  /** ⚠️ THE TEXT THE SPANS WERE COMPUTED FOR. James: "Spans apply only to the exact
   *  text they were computed for... While typing, stale spans are hidden, never
   *  misplaced." Comparing text beats a shared counter, which can get out of step. */
  readonly spans_for_text?: string | null
  /** ⚠️ ECHOED BACK FROM THE REQUEST, UNINTERPRETED BY THE SERVER. Present only on a
   *  `setCaptureText` response. The CLIENT drops a response whose `seq` is not higher
   *  than the highest it has applied — see `capture-sequence.ts` for why the client
   *  and not the server. */
  readonly seq?: number
  readonly status: "capturing" | "review" | "abandoned" | "approved"
  readonly object_type: string
  readonly typed_lines: readonly string[]
  readonly values: Readonly<Record<string, unknown>>
  /** ⚠️ ALL FIVE SETS. `not_applicable` and `indeterminate` are different states and the
   *  pane renders them differently; collapsing them here would lose the distinction the
   *  engine exists to keep. */
  readonly answered: readonly string[]
  readonly missing: readonly string[]
  readonly unanswered_optional: readonly string[]
  readonly not_applicable: readonly string[]
  readonly indeterminate: readonly string[]
  readonly is_complete: boolean
  /** ⚠️ Text the extractor could not place. Shown, never dropped. */
  readonly unrecognized: readonly string[]
  /** ⚠️ A COMBINATION THE VAULT DOES NOT ALLOW — AND NOT THE SAME THING AS
   *  `unrecognized`. The extractor understood both phrases; they contradict each
   *  other ("Continental 34" offers only `nameplate_only`; "nameplate and vinyl"
   *  asks for something else). Filing these under "not understood" would send the
   *  director back to retype words that were read correctly.
   *
   *  ⚠️ `permitted` IS WHAT MAKES THE MESSAGE ACTIONABLE. "That is not available"
   *  with no alternatives is a dead end. */
  /** ⚠️ A VALUE CHOSEN FOR THE DIRECTOR, WITH ITS ONE ALTERNATIVE — NOT A PICK.
   *  The field is CAPTURED and the order can be completed without touching it. Ruled
   *  2026-10-13: a vault ambiguous only by form takes the burial vault and offers the
   *  urn vault, because a pick there asks a question the office already knows. */
  /**
   * ⚠️ OPTIONAL BECAUSE THE SERVER MAY NOT SEND IT, not because it is unimportant.
   * `switches` and `conflicts` arrived in later deploys (r209 and the gated pass).
   * A browser talking to an instance that predates them gets a response with the
   * key ABSENT — and a component that read `.length` off it rendered a BLANK PANE,
   * which is indistinguishable from "no pane appeared". Optional here forces every
   * read site to default.
   */
  readonly switches?: readonly {
    readonly field_id: string
    readonly from_label: string
    readonly to_value: string
    readonly to_label: string
  }[]
  readonly conflicts?: readonly {
    readonly field_id: string
    readonly value: unknown
    readonly permitted: readonly string[]
    readonly message: string
  }[]
  readonly pending_picks: readonly CapturePick[]
  readonly vault_resolution: {
    readonly resolved: boolean
    readonly candidates: readonly string[]
    readonly discriminators: readonly string[]
  }
  readonly surface: {
    readonly id: string
    readonly rows: readonly CaptureRow[]
    /** The subject block above the grid — the decedent, over their dates.
     *
     *  ⚠️ IT WAS COMPUTED SERVER-SIDE AND NEVER SENT, which is why the Review showed
     *  no deceased name. `deceased_name` is only ever in the summary surface's
     *  `SubjectSlot`, so no amount of row rendering could have shown it. */
    readonly subject_primary?: string | null
    readonly subject_secondary?: string | null
  }
}

const BASE = "/capture/sessions"

/**
 * The tenant's completable vocabulary, fetched ONCE when capture opens.
 *
 * ⚠️ ONE FETCH, NOT ONE PER KEYSTROKE, BY RULING. Matching happens client-side so
 * keystroke latency never touches the network. A failure resolves to an EMPTY list
 * rather than throwing: a bar that cannot complete is a bar; a bar that throws is a
 * pane that does not render.
 */
export async function fetchVocabulary(): Promise<readonly VocabTerm[]> {
  try {
    const r = await apiClient.get<{ terms: VocabTerm[] }>("/capture/vocabulary")
    return r.data?.terms ?? []
  } catch {
    return []
  }
}

export async function startCapture(openingLine?: string): Promise<CaptureState> {
  const r = await apiClient.post<CaptureState>(BASE, {
    opening_line: openingLine ?? null,
  })
  return r.data
}

export async function addLine(
  sessionId: string,
  line: string,
): Promise<CaptureState> {
  const r = await apiClient.post<CaptureState>(`${BASE}/${sessionId}/lines`, { line })
  return r.data
}

/**
 * Re-read the WHOLE typed text. The hot path — one call per pause while typing.
 *
 * ⚠️ `PUT`, AND THAT IS THE CONTRACT NOT A PREFERENCE. It SETS the text to a value, so
 * sending the same text twice leaves the session identical. `addLine` is a `POST`
 * because it ADDS; the two must not be confused, and the method is the only thing in
 * the request that says which one you meant.
 *
 * ⚠️ EMPTY TEXT IS LEGAL AND MUST BE SENT. The director clearing the bar is a real
 * edit that un-captures everything, so a guard like `if (!text) return` here would
 * leave the pane showing values for words that are no longer on screen.
 *
 * ⚠️ `seq` IS THE CALLER'S, and the caller is the only party that can use it. See
 * `capture-sequence.ts`.
 */
export async function setCaptureText(
  sessionId: string,
  text: string,
  seq: number,
): Promise<CaptureState> {
  const r = await apiClient.put<CaptureState>(`${BASE}/${sessionId}/text`, { text, seq })
  return r.data
}

/** ⚠️ `index` IS ONE-BASED, matching the prototype's digit-key handler
 *  (`2026-10-01-opas-overlay.html:622`: `/^[1-9]$/` then `choose(+e.key-1)`). The server
 *  validates the range; zero-basing here would disagree with the only UI that drives it. */
export async function choosePick(
  sessionId: string,
  fieldId: string,
  index: number,
): Promise<CaptureState> {
  const r = await apiClient.post<CaptureState>(`${BASE}/${sessionId}/choose`, {
    field_id: fieldId,
    index,
  })
  return r.data
}

/**
 * Take the one alternative a switch offered.
 *
 * ⚠️ THE SERVER VALIDATES `to_value` AGAINST ITS OWN OFFER, so this cannot be used
 * to set an arbitrary value — and it writes a RESOLUTION, which is what makes the
 * click survive the next keystroke. A plain value would be erased ~350 ms later when
 * the text is re-read and the burial vault would come back.
 */
export async function takeSwitch(
  sessionId: string,
  fieldId: string,
  toValue: string,
): Promise<CaptureState> {
  const r = await apiClient.post<CaptureState>(`${BASE}/${sessionId}/switch`, {
    field_id: fieldId,
    to_value: toValue,
  })
  return r.data
}

/**
 * Closing Opas ends the capture: the server row is MARKED abandoned, never deleted.
 *
 * ⚠️ FIRE-AND-FORGET BY DESIGN. It runs while the pane is being torn down, so there
 * is nothing left to show an error to and nothing a retry could achieve. The row is
 * a recovery path, not state the client depends on.
 *
 * ⚠️ RULED FOR A SHARED OFFICE COMPUTER, not tidiness: the next person at that
 * machine must never see someone else's half-typed order.
 */
export async function abandonCapture(sessionId: string): Promise<void> {
  try {
    await apiClient.post(`${BASE}/${sessionId}/abandon`, {})
  } catch {
    /* see above — nothing to tell and nothing to retry */
  }
}

/** Finish the order: the summary, or what is still missing.
 *
 * ⚠️ THE SAME CALL THE BUTTON, ⌘ENTER AND THE TYPED PHRASES ALL MAKE. One action
 * behind three entrances, by ruling — three code paths for one intention is how
 * "approve" came to work only after a separate "that's everything".
 *
 * ⚠️ IT DOES NOT THROW ON AN INCOMPLETE ORDER. "Not finished yet" comes back as a
 * 200 with `missing_labels`; the pane turns those rows amber and the bar names them.
 */
export async function completeCapture(sessionId: string): Promise<CaptureState> {
  const r = await apiClient.post<CaptureState>(`${BASE}/${sessionId}/complete`, {})
  return r.data
}

/** Approve the capture into a sales order.
 *
 * ⚠️ IT RETURNS THE FULL STATE, NOT JUST AN ID, so the pane renders the approved
 * order from the same shape it was already rendering. A bespoke response would be a
 * second shape to keep in step with the first.
 *
 * ⚠️ IT DOES NOT SWALLOW ITS ERROR, unlike `abandonCapture`. A 409 carries the
 * blockers and the office needs to see them; a failure here is the difference
 * between an order existing and not.
 */
export async function approveCapture(sessionId: string): Promise<CaptureState> {
  const r = await apiClient.post<CaptureState>(`${BASE}/${sessionId}/approve`, {})
  return r.data
}

/** ⚠️ THE TUCK-SURVIVAL CALL. A tucked pane is re-read from the server rather than kept
 *  in client memory, so reopening cannot lose a half-typed order. */
export async function readCapture(sessionId: string): Promise<CaptureState> {
  const r = await apiClient.get<CaptureState>(`${BASE}/${sessionId}`)
  return r.data
}
