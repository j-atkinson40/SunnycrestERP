/**
 * QuoteFocusWithAccessories — S-3b editable quote core (replaces the
 * S-3a display-only core).
 *
 * The Act→Decide crossing made concrete AND editable. When the user
 * escalates a quote from the command bar ("Build this out →"), the bar
 * CLOSES (§5.15 mutual-exclusivity) and this Focus opens. S-3a proved the
 * crossing with a read-only re-host; S-3b makes the core the real
 * edit canvas — add / remove / reprice / reorder(*) line items with the
 * total moving live.  (*reorder deferred per the S-3b ruling.)
 *
 * OWNERSHIP (ruled decision 1): the draft is a LOCAL `useReducer` owned
 * here — NOT an app-level externalized QuoteFocusContext. It's seeded
 * from `currentFocus.params.extraction` (the S-3a handoff) on a fresh
 * escalation and hydrated from the persisted `focus_sessions.draft_state`
 * on reload (the URL carries only `?focus=`, so params are dropped).
 *
 * PERSISTENCE (ruled option b): the draft persists to
 * `focus_sessions.draft_state` on a debounce so an edit session survives
 * reload. THE HARD INVARIANT — it materializes NO quote. A Quote row is
 * written ONLY at an explicit save (deferred to a follow-on; see the
 * footer note). There is no path from this draft to the quotes domain.
 *
 * RE-PRICING (ruled): every edit reprices through the SAME S-2 endpoint +
 * `render_preview_html` path the display preview uses — so the drift
 * guard holds and refusal-under-ambiguity fires for an EDITED ambiguous
 * line, no second renderer.
 *
 * SPATIAL: this host owns layout — the edit core (centered) + the live
 * price-list accessory PIN (re-hosted S-2 `surface.price-list-reference`,
 * its products derived from the LIVE draft, not the frozen extraction).
 */

import { useEffect, useMemo, useReducer, useRef, useState } from "react"

import { useFocus } from "@/contexts/focus-context"
import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import type { FocusConfig } from "@/contexts/focus-registry"
import type { ExtractionContext } from "@/components/command-bar-surfaces/types"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { saveFocusDraft } from "@/services/focus-service"
import {
  fetchQuotePreview,
  type QuotePreviewResponse,
} from "@/services/quote-preview-service"

import { QUOTE_FOCUS_ID } from "./register"
import { QuoteEditCanvasCore } from "./QuoteEditCanvasCore"
import {
  draftFromPersisted,
  draftReducer,
  seedFromExtraction,
  type QuoteDraft,
} from "./draft-reducer"

export interface QuoteFocusWithAccessoriesProps {
  focusId: string
  config: FocusConfig
}

/** 300ms — matches the arc's saved-view / draft write debounces. Wide
 *  enough to amortize rapid typing into one persist. */
const DRAFT_PERSIST_DEBOUNCE_MS = 300
/** 200ms — matches the S-2 QuotePreviewWidget reprice debounce. */
const REPRICE_DEBOUNCE_MS = 200

export function QuoteFocusWithAccessories({
  focusId,
  config,
}: QuoteFocusWithAccessoriesProps) {
  void focusId
  void config
  const { currentFocus } = useFocus()
  const extraction =
    (currentFocus?.params["extraction"] as ExtractionContext | undefined) ??
    null

  // LOCAL draft, seeded from the extraction handoff. seedFromExtraction
  // runs once (useReducer init) — a null/empty extraction yields an empty
  // editable canvas.
  const [draft, dispatch] = useReducer(
    draftReducer,
    extraction,
    seedFromExtraction,
  )

  // Hydrate-from-persisted (reload path). Only ever hydrate into an EMPTY
  // canvas — a fresh escalation already seeded content from params, and a
  // late draftState must never clobber in-progress edits.
  const hydratedRef = useRef(false)
  const persistedDraft = currentFocus?.draftState ?? null
  useEffect(() => {
    if (hydratedRef.current) return
    if (draft.customer !== null || draft.lines.length > 0) {
      hydratedRef.current = true
      return
    }
    const persisted = draftFromPersisted(persistedDraft)
    if (persisted && (persisted.customer || persisted.lines.length > 0)) {
      dispatch({ type: "hydrate", draft: persisted })
      hydratedRef.current = true
    }
  }, [persistedDraft, draft.customer, draft.lines.length])

  // ── Persistence — debounced PATCH /focus/{type}/draft ────────────────
  // Gated on sessionId: don't persist until the server has told us the
  // current draft (via POST /open). This closes the reload race where an
  // empty initial draft would otherwise overwrite the persisted one
  // before hydration.
  const sessionId = currentFocus?.sessionId ?? null
  const draftKey = useMemo(() => JSON.stringify(draft), [draft])
  const debouncedDraftKey = useDebouncedValue(
    draftKey,
    DRAFT_PERSIST_DEBOUNCE_MS,
  )
  useEffect(() => {
    if (sessionId === null) return
    // Fire-and-forget; persistence never blocks the edit UX.
    void saveFocusDraft(
      QUOTE_FOCUS_ID,
      JSON.parse(debouncedDraftKey) as QuoteDraft as unknown as Record<
        string,
        unknown
      >,
    ).catch((err) => {
      // eslint-disable-next-line no-console
      console.warn("[quote-focus] saveFocusDraft failed", err)
    })
  }, [debouncedDraftKey, sessionId])

  // ── Live repricing — SAME S-2 endpoint the display preview uses ──────
  const [price, setPrice] = useState<QuotePreviewResponse | null>(null)
  const [pricing, setPricing] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const repriceKey = useDebouncedValue(draftKey, REPRICE_DEBOUNCE_MS)
  useEffect(() => {
    const d = JSON.parse(repriceKey) as QuoteDraft
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setPricing(true)
    fetchQuotePreview(
      {
        customer_id: d.customer?.id ?? null,
        customer_name: d.customer?.name ?? null,
        lines: d.lines.map((l) => ({
          product_ref: l.productRef,
          product_id: l.productId,
          quantity: l.quantity,
          unit_price_override:
            l.unitPriceOverride && l.unitPriceOverride.trim() !== ""
              ? Number(l.unitPriceOverride)
              : undefined,
        })),
      },
      ctrl.signal,
    )
      .then((res) => {
        setPrice(res)
        setPricing(false)
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return
        if ((e as { code?: string })?.code === "ERR_CANCELED") return
        setPricing(false)
      })
    return () => ctrl.abort()
  }, [repriceKey])

  const PriceList = getWidgetRenderer("surface.price-list-reference")
  const hasLines = draft.lines.length > 0

  return (
    <div
      className="flex h-full w-full gap-4"
      data-slot="quote-focus"
      data-quote-focus-state="active"
    >
      {/* Editable CORE — the S-3b edit canvas. */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <QuoteEditCanvasCore
          draft={draft}
          dispatch={dispatch}
          price={price}
          pricing={pricing}
        />
        {/* Save — the one chrome primary. DEFERRED: materialization to the
            quotes hub lands in a follow-on. The draft is already durably
            saved (option b); this button does NOT create a quote yet, so
            it's disabled + honest about the state per the ruling. */}
        <div className="mx-auto mt-3 flex w-full max-w-[560px] items-center justify-end gap-3">
          <span className="text-caption text-content-subtle">
            Saved as a draft — sending to the quotes hub is coming next.
          </span>
          <button
            type="button"
            disabled
            title="Saving to the quotes hub lands in a follow-on. Your edits are already saved as a draft."
            className="inline-flex h-10 items-center rounded bg-accent px-5 text-body-sm font-semibold text-content-on-accent opacity-50"
            data-testid="quote-save"
          >
            Save quote
          </button>
        </div>
      </div>

      {/* Live-config accessory PIN — the re-hosted S-2 price-list, its
          products derived from the LIVE draft (updates as lines change). */}
      {hasLines && (
        <aside
          className="w-72 flex-shrink-0 overflow-y-auto"
          data-slot="quote-focus-accessory-rail"
          aria-label="Price list reference"
        >
          <PriceList
            widgetId="quote-focus:price-list"
            variant_id="brief"
            surface="focus_canvas"
            config={{
              products: draft.lines.map((l) => l.productRef),
              customerId: draft.customer?.id ?? null,
            }}
          />
        </aside>
      )}
    </div>
  )
}
