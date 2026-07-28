/**
 * S-3b — the editable quote draft: a LOCAL reducer, colocated with the
 * quote Focus core (ruled decision 1). NOT an app-level externalized
 * QuoteFocusContext — the parked-for-S-5 thing is the DISPLAY preview
 * (already host-agnostic), so the editor owning its own local state
 * loses nothing.
 *
 * THE HARD INVARIANT (backend-enforced, mirrored in intent here): this
 * draft is Focus session state. It persists to focus_sessions.draft_state
 * on a debounce and materializes NO quote until an explicit save. Nothing
 * in this reducer writes to the quotes domain.
 *
 * Seeded from `currentFocus.params.extraction` (the S-3a handoff) on a
 * fresh escalation; hydrated from the persisted draft on reload (params
 * are dropped by the URL, which carries only `?focus=`).
 */

import type { ExtractionContext } from "@/components/command-bar-surfaces/types"

/** One editable quote line. `lineId` is a stable client key (persisted,
 *  so React keys + row identity survive reload). `unitPriceOverride` is a
 *  decimal STRING for the controlled input; undefined/"" means "use the
 *  price the order resolver returns". */
export interface DraftLine {
  lineId: string
  productRef: string
  productId?: string
  quantity: number
  unitPriceOverride?: string
}

export interface QuoteDraft {
  customer: { id?: string; name: string } | null
  lines: DraftLine[]
}

export type DraftAction =
  | { type: "hydrate"; draft: QuoteDraft }
  | {
      type: "addLine"
      productRef: string
      productId?: string
      quantity?: number
    }
  | { type: "removeLine"; lineId: string }
  | { type: "setQuantity"; lineId: string; quantity: number }
  | { type: "setOverride"; lineId: string; value: string }

// Monotonic client-side id source. Module-scoped counter, not
// crypto.randomUUID — jsdom/vitest don't reliably expose it, and a
// per-session counter is sufficient for React keys + persisted identity.
let _seq = 0
export function nextLineId(): string {
  _seq += 1
  return `l${_seq}`
}

/** Build the initial draft from the overlay extraction (fresh
 *  escalation). Empty extraction → an empty editable canvas.
 *
 *  Defensive against a PARTIAL extraction (missing `lines`/`customer`) —
 *  an escalation may hand off a still-seeding or minimal draft (e.g. park's
 *  start-quote tablet before its async customer-seed lands). A Focus must
 *  never crash on a malformed handoff; missing fields degrade to an empty
 *  canvas rather than throwing on `undefined.map`. */
export function seedFromExtraction(
  extraction: ExtractionContext | null | undefined,
): QuoteDraft {
  if (!extraction) return { customer: null, lines: [] }
  return {
    customer: extraction.customer ?? null,
    lines: (extraction.lines ?? []).map((l) => ({
      lineId: nextLineId(),
      productRef: l.productRef,
      productId: l.productId,
      quantity: l.quantity,
    })),
  }
}

export function draftReducer(
  state: QuoteDraft,
  action: DraftAction,
): QuoteDraft {
  switch (action.type) {
    case "hydrate":
      return action.draft
    case "addLine":
      return {
        ...state,
        lines: [
          ...state.lines,
          {
            lineId: nextLineId(),
            productRef: action.productRef,
            productId: action.productId,
            quantity: action.quantity ?? 1,
          },
        ],
      }
    case "removeLine":
      return {
        ...state,
        lines: state.lines.filter((l) => l.lineId !== action.lineId),
      }
    case "setQuantity":
      return {
        ...state,
        lines: state.lines.map((l) =>
          l.lineId === action.lineId
            ? { ...l, quantity: Math.max(1, action.quantity) }
            : l,
        ),
      }
    case "setOverride":
      return {
        ...state,
        lines: state.lines.map((l) =>
          l.lineId === action.lineId
            ? {
                ...l,
                unitPriceOverride:
                  action.value.trim() === "" ? undefined : action.value,
              }
            : l,
        ),
      }
    default:
      return state
  }
}

/** Narrow the persisted JSONB blob back into a QuoteDraft. Tolerant of a
 *  missing/legacy shape — returns null so the caller keeps its seed. */
export function draftFromPersisted(
  raw: Record<string, unknown> | null | undefined,
): QuoteDraft | null {
  if (!raw || typeof raw !== "object") return null
  const lines = (raw as { lines?: unknown }).lines
  if (!Array.isArray(lines)) return null
  const customer =
    (raw as { customer?: QuoteDraft["customer"] }).customer ?? null
  const parsed: DraftLine[] = []
  for (const l of lines) {
    if (!l || typeof l !== "object") continue
    const rec = l as Record<string, unknown>
    if (typeof rec.productRef !== "string") continue
    parsed.push({
      lineId:
        typeof rec.lineId === "string" && rec.lineId ? rec.lineId : nextLineId(),
      productRef: rec.productRef,
      productId:
        typeof rec.productId === "string" ? rec.productId : undefined,
      quantity:
        typeof rec.quantity === "number" && rec.quantity > 0
          ? rec.quantity
          : 1,
      unitPriceOverride:
        typeof rec.unitPriceOverride === "string"
          ? rec.unitPriceOverride
          : undefined,
    })
  }
  return { customer, lines: parsed }
}
