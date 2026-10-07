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
