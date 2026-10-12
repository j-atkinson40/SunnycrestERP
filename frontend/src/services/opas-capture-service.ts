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
}

/** An ambiguous resolution awaiting a numbered pick. */
export interface CapturePick {
  readonly field_id: string
  readonly phrase: string
  /** `[value_to_store, label_to_show]` — the label carries the town for a party. */
  readonly options: readonly [string, string][]
  readonly discriminator: string | null
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
  /** ⚠️ ECHOED BACK FROM THE REQUEST, UNINTERPRETED BY THE SERVER. Present only on a
   *  `setCaptureText` response. The CLIENT drops a response whose `seq` is not higher
   *  than the highest it has applied — see `capture-sequence.ts` for why the client
   *  and not the server. */
  readonly seq?: number
  readonly status: "capturing" | "review" | "abandoned"
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
  readonly conflicts: readonly {
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
  }
}

const BASE = "/capture/sessions"

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

/** ⚠️ THE TUCK-SURVIVAL CALL. A tucked pane is re-read from the server rather than kept
 *  in client memory, so reopening cannot lose a half-typed order. */
export async function readCapture(sessionId: string): Promise<CaptureState> {
  const r = await apiClient.get<CaptureState>(`${BASE}/${sessionId}`)
  return r.data
}
