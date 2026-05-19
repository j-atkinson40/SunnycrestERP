/**
 * useFocusTemplateDraft — Tier 2 template draft lifecycle (sub-arc C-2.2b).
 *
 * Mirrors useFocusCoreDraft for the Tier 2 templates editor. Unlike
 * Tier 1 cores (which carry a single `chrome` blob), Tier 2 templates
 * carry THREE independent authoring blobs:
 *
 *   - chrome_overrides — cascaded on top of the inherited core's chrome
 *   - substrate        — Focus-level page-background atmospheric tier (B-4)
 *   - typography       — Focus-level heading/body weight + color (B-5)
 *
 * Each blob is independently subject to the C-2.1.4 stale-closure
 * race (rapid scrubs registering setTimeouts that close over stale
 * state). To prevent the bug across all three, the hook uses three
 * refs that the `save` callback reads from. The save callback's
 * useCallback deps deliberately EXCLUDE all three draft state
 * variables; only `templateId` + `editSessionId` are in the deps.
 *
 * Session-aware semantics: same as useFocusCoreDraft. A fresh UUID v4
 * is generated when `templateId` transitions null → real OR switches
 * between two real values. Sent with every PUT as `edit_session_id`.
 * On HTTP 410 Gone (caller's id stale), the hook swaps to the
 * `active_template_id` from the response body and retries once under
 * the same session token.
 *
 * Dirty state: derived from a three-blob OR over deepEqualBlob
 * comparisons. The same key-order-AND-key-set-tolerant helper used in
 * useFocusCoreDraft is mirrored here so substrate / typography
 * sparse-response shapes don't stick the indicator (defensive against
 * any future backend serializer drift).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import {
  focusTemplatesService,
  type TemplateRecord,
} from "@/bridgeable-admin/services/focus-templates-service"
import {
  backendToFrontendRows,
  frontendToBackendRows,
} from "./_placement-adapter"

export type ChromeOverridesBlob = Record<string, unknown>
export type SubstrateBlob = Record<string, unknown>
export type TypographyBlob = Record<string, unknown>

/**
 * F-3 — widget placement shape inside the `rows` JSONB blob.
 *
 * A row holds `placements`, each placement targets a widget by slug
 * and carries a chrome override blob. `column_start` / `column_span`
 * are 1-indexed against `column_count` (default 12).
 *
 * The on-the-wire shape stays `Array<Record<string, unknown>>` (the
 * existing TemplateRecord.rows contract); the interfaces below are
 * the hook's typed view of that shape. The hook coerces in/out at
 * the boundary so callers stay strongly typed without forcing a
 * backend schema change.
 */
export interface WidgetPlacement {
  id: string
  widget_slug: string
  column_start: number
  column_span: number
  chrome: Record<string, unknown>
}

export interface FocusRow {
  row_index: number
  column_count: number
  placements: WidgetPlacement[]
}

export type RowsBlob = FocusRow[]

export interface UseFocusTemplateDraftResult {
  template: TemplateRecord | null
  chromeOverridesDraft: ChromeOverridesBlob
  substrateDraft: SubstrateBlob
  typographyDraft: TypographyBlob
  rowsDraft: RowsBlob
  updateChromeOverrides: (partial: ChromeOverridesBlob) => void
  updateSubstrate: (partial: SubstrateBlob) => void
  updateTypography: (partial: TypographyBlob) => void
  /**
   * F-3 — widget placement mutators. Each reads-modifies-writes the
   * rowsRef (NOT closure) and triggers the existing debounced save.
   */
  addWidget: (
    widgetSlug: string,
    position?: { rowIndex?: number; columnStart?: number; columnSpan?: number },
  ) => string
  updateWidget: (widgetId: string, partialChrome: Record<string, unknown>) => void
  removeWidget: (widgetId: string) => void
  moveWidget: (
    widgetId: string,
    next: { rowIndex: number; columnStart: number; columnSpan?: number },
  ) => void
  /**
   * Sub-arc C-2.3 — per-field reset to inherited. Removes the named
   * field from the override blob and triggers a debounced save. The
   * canonical "no override" representation is field absence (see
   * C-2.1.3 full-shape contract); the resolver re-cascades from the
   * parent tier at next resolve.
   */
  resetChromeOverridesField: (fieldName: string) => void
  resetSubstrateField: (fieldName: string) => void
  resetTypographyField: (fieldName: string) => void
  save: () => Promise<void>
  discard: () => void
  isDirty: boolean
  isSaving: boolean
  lastSavedAt: Date | null
  error: string | null
  isLoading: boolean
  editSessionId: string | null
}

const AUTO_SAVE_DEBOUNCE_MS = 300

function generateSessionToken(): string {
  const cryptoObj =
    typeof globalThis !== "undefined"
      ? (globalThis as { crypto?: { randomUUID?: () => string } }).crypto
      : undefined
  if (cryptoObj?.randomUUID) {
    return cryptoObj.randomUUID()
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === "x" ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/**
 * Key-order-AND-key-set-tolerant deep equality.
 *
 * Mirrors `deepEqualChrome` in useFocusCoreDraft.ts. Treats missing
 * key and explicit-null/undefined value as semantically equivalent so
 * sparse backend responses don't stick the dirty indicator.
 */
function deepEqualBlob(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (a == null && b == null) return true
  if (a == null || b == null) return false
  if (typeof a !== typeof b) return false
  if (typeof a !== "object") return false
  if (Array.isArray(a)) {
    if (!Array.isArray(b)) return false
    if (a.length !== b.length) return false
    for (let i = 0; i < a.length; i += 1) {
      if (!deepEqualBlob(a[i], b[i])) return false
    }
    return true
  }
  if (Array.isArray(b)) return false
  const aObj = a as Record<string, unknown>
  const bObj = b as Record<string, unknown>
  const allKeys = new Set([...Object.keys(aObj), ...Object.keys(bObj)])
  for (const k of allKeys) {
    const av = Object.prototype.hasOwnProperty.call(aObj, k)
      ? aObj[k]
      : undefined
    const bv = Object.prototype.hasOwnProperty.call(bObj, k)
      ? bObj[k]
      : undefined
    if (!deepEqualBlob(av, bv)) return false
  }
  return true
}

interface StaleTemplateErrorBody {
  message?: string
  inactive_template_id?: string
  active_template_id?: string | null
  slug?: string
  scope?: string
  vertical?: string | null
}

function extractStaleActiveTemplateId(err: unknown): string | null {
  if (!err || typeof err !== "object") return null
  const e = err as {
    response?: {
      status?: number
      data?: { detail?: StaleTemplateErrorBody }
    }
  }
  if (e.response?.status !== 410) return null
  const detail = e.response?.data?.detail
  if (!detail || typeof detail !== "object") return null
  return typeof detail.active_template_id === "string"
    ? detail.active_template_id
    : null
}

/**
 * F-3.1a.2 — URL recovery on 410-retry.
 *
 * When a session's first save against the URL-bound `templateId`
 * 410s, the hook swaps `activeTemplateIdRef.current` to the
 * `active_template_id` returned in the response body and retries
 * the PUT. If the consumer provides `onActiveTemplateIdChange`,
 * the hook fires it with the new id so the URL can be rewritten
 * (`?subject=template:<new-id>`) before the next refresh — without
 * this, refresh re-GETs the now-deactivated id and surfaces an
 * inactive snapshot that predates the operator's saves.
 *
 * Fires ONLY when the active id actually changes from its prior
 * value. A retry that lands on the same id (or a primary save that
 * succeeds without retry) does NOT fire the callback.
 */
export interface UseFocusTemplateDraftOptions {
  onActiveTemplateIdChange?: (newId: string) => void
}

export function useFocusTemplateDraft(
  templateId: string | null,
  options?: UseFocusTemplateDraftOptions,
): UseFocusTemplateDraftResult {
  const [template, setTemplate] = useState<TemplateRecord | null>(null)

  const [chromeOverridesDraft, setChromeOverridesDraft] =
    useState<ChromeOverridesBlob>({})
  const [substrateDraft, setSubstrateDraft] = useState<SubstrateBlob>({})
  const [typographyDraft, setTypographyDraft] = useState<TypographyBlob>({})
  // F-3 — rows blob (4th independently-tracked draft slot).
  const [rowsDraft, setRowsDraft] = useState<RowsBlob>([])

  const [chromeOverridesSnapshot, setChromeOverridesSnapshot] =
    useState<ChromeOverridesBlob>({})
  const [substrateSnapshot, setSubstrateSnapshot] = useState<SubstrateBlob>({})
  const [typographySnapshot, setTypographySnapshot] = useState<TypographyBlob>(
    {},
  )
  const [rowsSnapshot, setRowsSnapshot] = useState<RowsBlob>([])

  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)
  const [editSessionId, setEditSessionId] = useState<string | null>(null)

  // Active id may diverge from `templateId` after a 410-Gone retry.
  const activeTemplateIdRef = useRef<string | null>(null)

  // F-3.1a.2 — callback ref so deps stay minimal and the latest
  // consumer-supplied callback is always called (no closure capture).
  const onActiveTemplateIdChangeRef = useRef<
    ((newId: string) => void) | undefined
  >(options?.onActiveTemplateIdChange)
  useEffect(() => {
    onActiveTemplateIdChangeRef.current = options?.onActiveTemplateIdChange
  }, [options?.onActiveTemplateIdChange])

  // Three draft refs — `save` reads from these, NOT from the closure-
  // captured draft state. This is the C-2.1.4 discipline applied to
  // every blob: without refs, rapid scrubs to substrate or typography
  // would queue saves that read a value one event behind the actual
  // committed draft, and the save payload would persist stale data,
  // leaving isDirty stuck.
  const chromeOverridesRef = useRef<ChromeOverridesBlob>({})
  const substrateRef = useRef<SubstrateBlob>({})
  const typographyRef = useRef<TypographyBlob>({})
  // F-3 — rows ref (4th draftRef per C-2.1.4 + multi-hook-mount canon).
  const rowsRef = useRef<RowsBlob>([])

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Keep refs in sync with state.
  useEffect(() => {
    chromeOverridesRef.current = chromeOverridesDraft
  }, [chromeOverridesDraft])
  useEffect(() => {
    substrateRef.current = substrateDraft
  }, [substrateDraft])
  useEffect(() => {
    typographyRef.current = typographyDraft
  }, [typographyDraft])
  useEffect(() => {
    rowsRef.current = rowsDraft
  }, [rowsDraft])

  // Load on templateId change.
  useEffect(() => {
    if (!templateId) {
      setTemplate(null)
      setChromeOverridesDraft({})
      setSubstrateDraft({})
      setTypographyDraft({})
      setRowsDraft([])
      setChromeOverridesSnapshot({})
      setSubstrateSnapshot({})
      setTypographySnapshot({})
      setRowsSnapshot([])
      setError(null)
      setEditSessionId(null)
      activeTemplateIdRef.current = null
      return
    }
    let cancelled = false
    setIsLoading(true)
    setError(null)
    activeTemplateIdRef.current = templateId
    setEditSessionId(generateSessionToken())
    focusTemplatesService
      .get(templateId)
      .then((rec) => {
        if (cancelled) return
        const chromeOv = (rec.chrome_overrides ?? {}) as ChromeOverridesBlob
        const sub = (rec.substrate ?? {}) as SubstrateBlob
        const typ = (rec.typography ?? {}) as TypographyBlob
        // F-3.1a — adapt backend canonical placement shape to the
        // hook's frontend-typed view. Backend stores `placement_id`/
        // `component_name`/`starting_column`/`prop_overrides`;
        // frontend uses `id`/`widget_slug`/`column_start` (1-indexed)/
        // `chrome`. The adapter is tolerant of either-shape input so
        // legacy frontend-shaped JSONB still in the DB round-trips
        // without loss.
        const rows = backendToFrontendRows(rec.rows ?? [])
        setTemplate(rec)
        setChromeOverridesDraft({ ...chromeOv })
        setSubstrateDraft({ ...sub })
        setTypographyDraft({ ...typ })
        setRowsDraft(rows.map((r) => ({ ...r, placements: r.placements?.map((p) => ({ ...p })) ?? [] })))
        setChromeOverridesSnapshot({ ...chromeOv })
        setSubstrateSnapshot({ ...sub })
        setTypographySnapshot({ ...typ })
        setRowsSnapshot(rows.map((r) => ({ ...r, placements: r.placements?.map((p) => ({ ...p })) ?? [] })))
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : "Failed to load template")
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [templateId])

  // Dirty = ANY of the four drafts disagrees with its snapshot.
  // (F-3 extends from OR-of-3 to OR-of-4 — rows blob added.)
  const isDirty = useMemo(
    () =>
      !deepEqualBlob(chromeOverridesDraft, chromeOverridesSnapshot) ||
      !deepEqualBlob(substrateDraft, substrateSnapshot) ||
      !deepEqualBlob(typographyDraft, typographySnapshot) ||
      !deepEqualBlob(rowsDraft, rowsSnapshot),
    [
      chromeOverridesDraft,
      chromeOverridesSnapshot,
      substrateDraft,
      substrateSnapshot,
      typographyDraft,
      typographySnapshot,
      rowsDraft,
      rowsSnapshot,
    ],
  )

  const save = useCallback(async () => {
    const targetId = activeTemplateIdRef.current ?? templateId
    if (!targetId) return
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
      debounceTimer.current = null
    }
    setIsSaving(true)
    setError(null)

    // CRITICAL (C-2.1.4 discipline applied to all three blobs): read
    // every draft via ref, NOT closure. Rapid updateSubstrate /
    // updateTypography / updateChromeOverrides calls advance the React
    // state but the queued save would otherwise send whatever values
    // were captured when the save callback was created. The refs are
    // always up-to-date with the latest committed draft state.
    const latestChromeOverrides = chromeOverridesRef.current
    const latestSubstrate = substrateRef.current
    const latestTypography = typographyRef.current
    // F-3.1a — adapt frontend-typed rows to backend canonical shape
    // before sending. Without this translation, `_validate_placement`
    // on the backend rejects the payload (missing `placement_id` /
    // `component_kind` / `starting_column` keys) and the save is a
    // silent no-op.
    const latestRows = frontendToBackendRows(rowsRef.current)

    const payloadBase = editSessionId
      ? {
          chrome_overrides: latestChromeOverrides,
          substrate: latestSubstrate,
          typography: latestTypography,
          rows: latestRows,
          edit_session_id: editSessionId,
        }
      : {
          chrome_overrides: latestChromeOverrides,
          substrate: latestSubstrate,
          typography: latestTypography,
          rows: latestRows,
        }
    // The service contract types rows as `Array<Record<string, unknown>>`
    // (the on-the-wire JSONB shape). RowsBlob is a structurally
    // compatible refinement — every FocusRow IS a record-with-string-
    // keys-and-unknown-values when serialized — but TypeScript can't
    // see through the named-interface vs index-signature distinction.
    // Cast through `unknown` per project convention.
    const payload = payloadBase as unknown as Parameters<
      typeof focusTemplatesService.update
    >[1]

    try {
      const updated = await focusTemplatesService.update(targetId, payload)
      activeTemplateIdRef.current = updated.id
      const chromeOv = (updated.chrome_overrides ?? {}) as ChromeOverridesBlob
      const sub = (updated.substrate ?? {}) as SubstrateBlob
      const typ = (updated.typography ?? {}) as TypographyBlob
      // F-3.1a — backend echoes the canonical shape it persisted;
      // adapt back to frontend-typed view for snapshot equality with
      // the draft state.
      const rows = backendToFrontendRows(updated.rows ?? [])
      setTemplate(updated)
      setChromeOverridesSnapshot({ ...chromeOv })
      setSubstrateSnapshot({ ...sub })
      setTypographySnapshot({ ...typ })
      setRowsSnapshot(rows.map((r) => ({ ...r, placements: r.placements?.map((p) => ({ ...p })) ?? [] })))
      setLastSavedAt(new Date())
    } catch (err) {
      // 410 Gone retry — mirror C-2.1.1 cores path.
      const activeId = extractStaleActiveTemplateId(err)
      if (activeId && activeId !== targetId) {
        activeTemplateIdRef.current = activeId
        try {
          const updated = await focusTemplatesService.update(activeId, payload)
          activeTemplateIdRef.current = updated.id
          // F-3.1a.2 — fire URL-recovery callback once the retry has
          // actually persisted. We only fire when the resolved id
          // differs from the consumer's bound `templateId` AND a
          // callback is wired. Subsequent saves within this session
          // PUT against `updated.id` directly (no further retry,
          // session-aware fast path on the backend), so the callback
          // fires at most once per id transition.
          if (updated.id !== templateId) {
            onActiveTemplateIdChangeRef.current?.(updated.id)
          }
          const chromeOv = (updated.chrome_overrides ??
            {}) as ChromeOverridesBlob
          const sub = (updated.substrate ?? {}) as SubstrateBlob
          const typ = (updated.typography ?? {}) as TypographyBlob
          // F-3.1a — adapt the 410-retry response echo same as the
          // primary save success path.
          const rows = backendToFrontendRows(updated.rows ?? [])
          setTemplate(updated)
          setChromeOverridesSnapshot({ ...chromeOv })
          setSubstrateSnapshot({ ...sub })
          setTypographySnapshot({ ...typ })
          setRowsSnapshot(rows.map((r) => ({ ...r, placements: r.placements?.map((p) => ({ ...p })) ?? [] })))
          setLastSavedAt(new Date())
          return
        } catch (retryErr) {
          setError(
            retryErr instanceof Error ? retryErr.message : "Save failed",
          )
          return
        } finally {
          setIsSaving(false)
        }
      }
      setError(err instanceof Error ? err.message : "Save failed")
    } finally {
      setIsSaving(false)
    }
    // CRITICAL: deps EXCLUDE all three draft state variables. The
    // save callback reads them via refs; including them would
    // re-create the callback every keystroke, registering a new
    // debounced setTimeout each time and re-introducing the C-2.1.4
    // stale-closure race the refs were designed to prevent.
  }, [templateId, editSessionId])

  const queueSave = useCallback(() => {
    if (!templateId) return
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      void save()
    }, AUTO_SAVE_DEBOUNCE_MS)
  }, [templateId, save])

  const updateChromeOverrides = useCallback(
    (partial: ChromeOverridesBlob) => {
      setChromeOverridesDraft((prev) => ({ ...prev, ...partial }))
      queueSave()
    },
    [queueSave],
  )

  const updateSubstrate = useCallback(
    (partial: SubstrateBlob) => {
      setSubstrateDraft((prev) => ({ ...prev, ...partial }))
      queueSave()
    },
    [queueSave],
  )

  const updateTypography = useCallback(
    (partial: TypographyBlob) => {
      setTypographyDraft((prev) => ({ ...prev, ...partial }))
      queueSave()
    },
    [queueSave],
  )

  // Sub-arc C-2.3 — per-field reset helpers. Each removes the named
  // field from its blob and triggers the same debounced save path as
  // updateXxx. Field absence is the canonical "no override" state per
  // C-2.1.3; the next resolve re-cascades the parent value into the
  // resolved view. Mirrors the updateXxx pattern (setState + queueSave).
  const resetChromeOverridesField = useCallback(
    (fieldName: string) => {
      setChromeOverridesDraft((prev) => {
        if (!(fieldName in prev)) return prev
        const next = { ...prev }
        delete next[fieldName]
        return next
      })
      queueSave()
    },
    [queueSave],
  )

  const resetSubstrateField = useCallback(
    (fieldName: string) => {
      setSubstrateDraft((prev) => {
        if (!(fieldName in prev)) return prev
        const next = { ...prev }
        delete next[fieldName]
        return next
      })
      queueSave()
    },
    [queueSave],
  )

  const resetTypographyField = useCallback(
    (fieldName: string) => {
      setTypographyDraft((prev) => {
        if (!(fieldName in prev)) return prev
        const next = { ...prev }
        delete next[fieldName]
        return next
      })
      queueSave()
    },
    [queueSave],
  )

  const discard = useCallback(() => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
      debounceTimer.current = null
    }
    setChromeOverridesDraft({ ...chromeOverridesSnapshot })
    setSubstrateDraft({ ...substrateSnapshot })
    setTypographyDraft({ ...typographySnapshot })
    setRowsDraft(
      rowsSnapshot.map((r) => ({
        ...r,
        placements: r.placements?.map((p) => ({ ...p })) ?? [],
      })),
    )
  }, [chromeOverridesSnapshot, substrateSnapshot, typographySnapshot, rowsSnapshot])

  // ── F-3 widget mutators ─────────────────────────────────────────────
  //
  // Each method reads from rowsRef.current (NOT closure-captured
  // `rowsDraft`) per C-2.1.4 + multi-hook-mount canon. Mutators
  // commit to React state via `setRowsDraft` and queueSave fires the
  // existing debounced save pipeline. The save callback's deps
  // deliberately EXCLUDE `rowsDraft` — the save reads via ref.
  const generateWidgetId = useCallback(() => generateSessionToken(), [])

  const addWidget = useCallback(
    (
      widgetSlug: string,
      position?: {
        rowIndex?: number
        columnStart?: number
        columnSpan?: number
      },
    ): string => {
      const newId = generateWidgetId()
      const columnSpan = position?.columnSpan ?? 4
      const columnStart = position?.columnStart ?? 1
      const targetRowIndex = position?.rowIndex
      const current = rowsRef.current
      const next: RowsBlob = current.map((r) => ({
        ...r,
        placements: r.placements?.map((p) => ({ ...p })) ?? [],
      }))
      const placement: WidgetPlacement = {
        id: newId,
        widget_slug: widgetSlug,
        column_start: columnStart,
        column_span: columnSpan,
        chrome: {},
      }
      let row: FocusRow | undefined
      if (typeof targetRowIndex === "number") {
        row = next.find((r) => r.row_index === targetRowIndex)
      }
      if (!row) {
        const nextIndex =
          next.reduce(
            (m, r) => (r.row_index > m ? r.row_index : m),
            -1,
          ) + 1
        row = { row_index: nextIndex, column_count: 12, placements: [] }
        next.push(row)
      }
      row.placements.push(placement)
      setRowsDraft(next)
      queueSave()
      return newId
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- queueSave stable
    [generateWidgetId, queueSave],
  )

  const updateWidget = useCallback(
    (widgetId: string, partialChrome: Record<string, unknown>) => {
      const current = rowsRef.current
      let found = false
      const next: RowsBlob = current.map((r) => ({
        ...r,
        placements:
          r.placements?.map((p) => {
            if (p.id === widgetId) {
              found = true
              return { ...p, chrome: { ...p.chrome, ...partialChrome } }
            }
            return { ...p }
          }) ?? [],
      }))
      if (!found) return
      setRowsDraft(next)
      queueSave()
    },
    [queueSave],
  )

  const removeWidget = useCallback(
    (widgetId: string) => {
      const current = rowsRef.current
      let found = false
      const next: RowsBlob = current
        .map((r) => {
          const before = r.placements?.length ?? 0
          const placements =
            r.placements?.filter((p) => {
              if (p.id === widgetId) {
                found = true
                return false
              }
              return true
            }) ?? []
          if (placements.length === before) return { ...r, placements: r.placements?.map((p) => ({ ...p })) ?? [] }
          return { ...r, placements }
        })
        // Drop empty rows so the layout doesn't accumulate ghosts.
        .filter((r) => r.placements.length > 0)
      if (!found) return
      setRowsDraft(next)
      queueSave()
    },
    [queueSave],
  )

  const moveWidget = useCallback(
    (
      widgetId: string,
      target: { rowIndex: number; columnStart: number; columnSpan?: number },
    ) => {
      const current = rowsRef.current
      let placement: WidgetPlacement | null = null
      const stripped: RowsBlob = current
        .map((r) => {
          const remaining =
            r.placements?.filter((p) => {
              if (p.id === widgetId) {
                placement = { ...p }
                return false
              }
              return true
            }) ?? []
          return { ...r, placements: remaining }
        })
        .filter((r) => r.placements.length > 0)
      if (!placement) return
      const updated: WidgetPlacement = {
        ...(placement as WidgetPlacement),
        column_start: target.columnStart,
        column_span: target.columnSpan ?? (placement as WidgetPlacement).column_span,
      }
      let row = stripped.find((r) => r.row_index === target.rowIndex)
      if (!row) {
        row = {
          row_index: target.rowIndex,
          column_count: 12,
          placements: [],
        }
        stripped.push(row)
      }
      row.placements.push(updated)
      setRowsDraft(stripped)
      queueSave()
    },
    [queueSave],
  )

  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
    }
  }, [])

  return {
    template,
    chromeOverridesDraft,
    substrateDraft,
    typographyDraft,
    rowsDraft,
    updateChromeOverrides,
    updateSubstrate,
    updateTypography,
    addWidget,
    updateWidget,
    removeWidget,
    moveWidget,
    resetChromeOverridesField,
    resetSubstrateField,
    resetTypographyField,
    save,
    discard,
    isDirty,
    isSaving,
    lastSavedAt,
    error,
    isLoading,
    editSessionId,
  }
}

export default useFocusTemplateDraft
