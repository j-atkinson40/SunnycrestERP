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
  readonly field_ids?: readonly string[]  /** Which FIELD a click on this row should re-ask.
   *
   *  ⚠️ THE SERVER NAMES IT, and that is why the pane does not derive it from
   *  `field_ids[0]`. The Cemetery row sources the name, the town and the ETA; its
   *  `edit_target` is `cemetery`, so clicking it asks "Which cemetery?" rather than
   *  "Which town is the cemetery in?". */
  readonly edit_target?: string | null
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
  /** WHICH field the question is about. Guided capture, slice 1.
   *
   *  ⚠️ THE SERVER'S ANSWER, NOT DERIVED FROM `next_question`. Two fields can share a
   *  phrasing, so reading the field back out of the sentence would be a reverse
   *  lookup that breaks silently. `null` means nothing is missing. */
  readonly question_field_id?: string | null
  /** The question again, from the same walk as `question_field_id` — and the one that
   *  carries the cremation wording. ⚠️ `next_question` STAYS because every existing
   *  caller reads it and it is the same sentence for every non-cremation field; this
   *  is the one the guided pane renders. */
  readonly question?: string | null
  /** The one line under the question. Absent when there is nothing worth saying,
   *  which is normal — see `CALL_HINTS` in `schema.py`. */
  readonly question_hint?: string | null
  /** The three or four answers to offer. Empty for a free-text question, which is a
   *  real state and means "type it", not "the server forgot". */
  readonly pills?: readonly {
    readonly value: string
    readonly label: string
    /** The one thing that tells this answer from another: a town, a date, or the
     *  word "cremation". ⚠️ NEVER A PRICE — by ruling, and `Pill` has no price field. */
    readonly sub?: string
  }[]
  /** Present only once the vault has made this order a cremation.
   *
   *  ⚠️ `via` IS HOW THE CREMATION WAS ESTABLISHED, and the four ways are not equally
   *  strong — on sunnycrest today it is the product's own NAME, because
   *  `products.variant_template_id` is populated on 0 of 39 rows. The pane shows the
   *  chip; a reader who needs the provenance can have it. */
  readonly cremation?: { readonly label: string; readonly via: string | null }
  /** Why something was just cleared, in one line. Present only on the response to the
   *  answer that caused it.
   *
   *  ⚠️ TRANSIENT AND NOT STORED, the same as `completion_attempt`. It answers "what
   *  just happened", not "what is this order" — a column for it would leave a stale
   *  sentence explaining a change made yesterday. */
  readonly cleared_note?: string | null
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
  /** The one question Opas asks after an approve, or absent.
   *
   *  ⚠️ ABSENT UNTIL THE ORDER EXISTS, which is what "after you approve" is in data.
   *  "once, right after you approve, and only if you changed something Opas had filled
   *  in. It never asks while you're typing" (James, 2026-10-26).
   *
   *  ⚠️ AND ABSENT AGAIN ONCE ANSWERED OR SKIPPED. It is recomputed on every read, so a
   *  reload after an approve still shows it; the decision row's `reason_scope` is what
   *  stops it coming back. "never asks twice for one order." */
  readonly ask_why?: {
    readonly field: string
    /** "Vault" — the capture template's own label. */
    readonly label: string
    readonly was: string
    readonly now: string
    /** `extraction` | `prefill` | `default` — how Opas came to the value it had. */
    readonly source: string
    /** "You changed the vault from Monticello to Continental. Why?" */
    readonly prompt: string
  }
}

//: ⚠️ THE ROOT IS SEPARATE BECAUSE `preferences` IS NOT A SESSION. Hanging it off
//: `BASE` would address `/capture/sessions/preferences`, which the session routes
//: would try to read as a session id.
const BASE_ROOT = "/capture"
const BASE = `${BASE_ROOT}/sessions`

/**
 * The tenant's completable vocabulary, fetched ONCE when capture opens.
 *
 * ⚠️ ONE FETCH, NOT ONE PER KEYSTROKE, BY RULING. Matching happens client-side so
 * keystroke latency never touches the network. A failure resolves to an EMPTY list
 * rather than throwing: a bar that cannot complete is a bar; a bar that throws is a
 * pane that does not render.
 */
/** The user's pill-pick modifier, as the server reports it. */
export interface CapturePreferences {
  readonly pick_modifier: "option" | "control" | "command"
  readonly pick_modifier_glyph: string
  readonly pick_modifier_event_flag: "altKey" | "ctrlKey" | "metaKey"
}

/**
 * Read the caller's own pick modifier. `null` means it could not be read.
 *
 * ⚠️ `null` RATHER THAN A DEFAULT, AND THAT ONE WORD WAS THE BUG. This function used to
 * `catch` and return the Option default — so a refused request was indistinguishable
 * from a user who had never chosen, and the caller had no way to know it should try
 * again. James walked it on 2026-10-29: his stored preference was `control`, the pills
 * read ⌥1, and a plain digit worked.
 *
 * The chain: `OpasHost` mounts at `App.tsx:519` OUTSIDE `<Routes>`, so it mounts before
 * any token exists; the request answered **403** (measured live — a bogus path answers
 * 404, which is the control); the `catch` turned that into "the user chose Option"; and
 * the effect's `[]` dep array meant it never asked again. Three things composing, and
 * the swallow is the one that made it silent.
 *
 * ⚠️ IT IS THE FOURTH INSTANCE OF THE CLASS JAMES HAD ALREADY QUEUED A SWEEP FOR — an
 * error hidden behind a plausible "nothing to do" — and it was written the day after
 * that sweep was queued. The sweep now runs straight after slice 2 and covers this
 * shape wherever it appears.
 *
 * ⚠️ IT STILL DOES NOT THROW, because a failed preference read must not stop the bar
 * working. The difference is that the caller can now TELL, so it can keep the default
 * for display AND retry — rather than recording a guess as an answer.
 */
export async function fetchCapturePreferences(): Promise<CapturePreferences | null> {
  try {
    const r = await apiClient.get<CapturePreferences>(`${BASE_ROOT}/preferences`)
    return r.data
  } catch (err) {
    // ⚠️ IT LOGS. A silent null is the same defect one layer up: the caller would retry
    // forever and nobody would know why the first attempt failed.
    console.warn("[opas] could not read the pick-modifier preference", err)
    return null
  }
}

/**
 * Set the caller's own pick modifier.
 *
 * ⚠️ THIS ONE DOES NOT SWALLOW. A read that fails can degrade silently; a WRITE the
 * person asked for must report whether it happened, or "set my shortcut to control"
 * would answer "done" and change nothing.
 */
export async function setCapturePickModifier(
  modifier: string,
): Promise<CapturePreferences> {
  const r = await apiClient.patch<CapturePreferences>(`${BASE_ROOT}/preferences`, {
    pick_modifier: modifier,
  })
  return r.data
}

export async function fetchVocabulary(): Promise<readonly VocabTerm[]> {
  try {
    const r = await apiClient.get<{ terms: VocabTerm[] }>("/capture/vocabulary")
    return r.data?.terms ?? []
  } catch {
    return []
  }
}

export async function startCapture(
  openingLine?: string,
  prefill?: Readonly<Record<string, string>>,
): Promise<CaptureState> {
  const r = await apiClient.post<CaptureState>(BASE, {
    opening_line: openingLine ?? null,
    // ⚠️ OMITTED WHEN ABSENT rather than sent as null, so a typed capture's request is
    // byte-for-byte what it was before this change.
    ...(prefill !== undefined ? { prefill } : {}),
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
  asking?: string | null,
): Promise<CaptureState> {
  const r = await apiClient.put<CaptureState>(
    `${BASE}/${sessionId}/text`,
    { text, seq },
    // ⚠️ THE FOCUS RIDES THE EXTRACTION TOO, not only the plain read. A director who
    // clicks a row and then TYPES the answer gets a `setCaptureText` response, and
    // without this that response would compose the question for the server's next
    // field and the clicked row would lose its outline mid-answer.
    { ...(asking ? { params: { asking } } : {}) },
  )
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
 * Answer the question Opas is asking — by pill, by ⌥-digit, or by click.
 *
 * ⚠️ IT SENDS THE VALUE, NOT AN INDEX, AND THAT IS THE DIFFERENCE FROM `choosePick`.
 * A numbered pick indexes into options the SERVER stored on the session, so an index
 * is unambiguous. Pills are recomputed on every read — they are ranked from live
 * order history — so an index into a list the next response may have reordered would
 * settle whichever answer happened to be third.
 *
 * ⚠️ IT WRITES A RESOLUTION, which is what makes the pick survive the next keystroke.
 * "A pick is a durable answer like today's click-made picks" (James, 2026-10-27), and
 * a plain value would be erased when the whole text is re-read ~350 ms later.
 */
export async function answerCapture(
  sessionId: string,
  fieldId: string,
  value: string,
): Promise<CaptureState> {
  const r = await apiClient.post<CaptureState>(`${BASE}/${sessionId}/answer`, {
    field_id: fieldId,
    value,
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
/**
 * Re-read a session.
 *
 * ⚠️ `asking` IS THE OFFICE HAVING CLICKED A ROW. "Clicking a row asks that question
 * again" — and the question, its hint and its pills are composed on the SERVER, so the
 * field has to go back there. My first version changed only which row was outlined
 * while Opas went on asking the previous question.
 *
 * ⚠️ IT IS A QUERY PARAMETER AND NOT STORED. Nothing about the order changes when a
 * row is clicked, so there is nothing to persist — and stored focus would survive a
 * reload and hold the pane on a question the office had moved past.
 */
export async function readCapture(
  sessionId: string,
  asking?: string | null,
): Promise<CaptureState> {
  const r = await apiClient.get<CaptureState>(`${BASE}/${sessionId}`, {
    // ⚠️ OMITTED WHEN ABSENT rather than sent as an empty string, because the server
    // validates `asking` against the fields it is actually asking about and an empty
    // string would be a value it has to reject rather than a question it was not asked.
    ...(asking ? { params: { asking } } : {}),
  })
  return r.data
}

/**
 * Answer Opas's "why?". Two steps, one endpoint.
 *
 *   {scope: "skipped"}                      Esc, or a phrase that was really a request
 *   {reason, scope: "today"}                stored, and that is all
 *   {reason, scope: "always"}               stored, and a rule sentence comes back
 *   {reason, scope: "always", rule_text}    that sentence becomes a rule
 *
 * ⚠️ THE REASON AND THE SCOPE TRAVEL TOGETHER because the server's CHECK constraint
 * forbids a reason with no scope — a row holding one without the other would read as a
 * deliberate record of a half-answered question. So the bar holds the typed reason until
 * ⌘1 or ⌘2 and sends both.
 */
export async function answerWhy(
  sessionId: string,
  body: { reason?: string; scope: "today" | "always" | "skipped"; rule_text?: string },
): Promise<{ stored: boolean; scope?: string; draft?: string; rule_id?: string | null }> {
  const r = await apiClient.post<{
    stored: boolean
    scope?: string
    draft?: string
    rule_id?: string | null
  }>(`${BASE}/${sessionId}/why`, body)
  return r.data
}
