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

export type ChromeOverridesBlob = Record<string, unknown>
export type SubstrateBlob = Record<string, unknown>
export type TypographyBlob = Record<string, unknown>

export interface UseFocusTemplateDraftResult {
  template: TemplateRecord | null
  chromeOverridesDraft: ChromeOverridesBlob
  substrateDraft: SubstrateBlob
  typographyDraft: TypographyBlob
  updateChromeOverrides: (partial: ChromeOverridesBlob) => void
  updateSubstrate: (partial: SubstrateBlob) => void
  updateTypography: (partial: TypographyBlob) => void
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

export function useFocusTemplateDraft(
  templateId: string | null,
): UseFocusTemplateDraftResult {
  const [template, setTemplate] = useState<TemplateRecord | null>(null)

  const [chromeOverridesDraft, setChromeOverridesDraft] =
    useState<ChromeOverridesBlob>({})
  const [substrateDraft, setSubstrateDraft] = useState<SubstrateBlob>({})
  const [typographyDraft, setTypographyDraft] = useState<TypographyBlob>({})

  const [chromeOverridesSnapshot, setChromeOverridesSnapshot] =
    useState<ChromeOverridesBlob>({})
  const [substrateSnapshot, setSubstrateSnapshot] = useState<SubstrateBlob>({})
  const [typographySnapshot, setTypographySnapshot] = useState<TypographyBlob>(
    {},
  )

  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)
  const [editSessionId, setEditSessionId] = useState<string | null>(null)

  // Active id may diverge from `templateId` after a 410-Gone retry.
  const activeTemplateIdRef = useRef<string | null>(null)

  // Three draft refs — `save` reads from these, NOT from the closure-
  // captured draft state. This is the C-2.1.4 discipline applied to
  // every blob: without refs, rapid scrubs to substrate or typography
  // would queue saves that read a value one event behind the actual
  // committed draft, and the save payload would persist stale data,
  // leaving isDirty stuck.
  const chromeOverridesRef = useRef<ChromeOverridesBlob>({})
  const substrateRef = useRef<SubstrateBlob>({})
  const typographyRef = useRef<TypographyBlob>({})

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

  // Load on templateId change.
  useEffect(() => {
    if (!templateId) {
      setTemplate(null)
      setChromeOverridesDraft({})
      setSubstrateDraft({})
      setTypographyDraft({})
      setChromeOverridesSnapshot({})
      setSubstrateSnapshot({})
      setTypographySnapshot({})
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
        setTemplate(rec)
        setChromeOverridesDraft({ ...chromeOv })
        setSubstrateDraft({ ...sub })
        setTypographyDraft({ ...typ })
        setChromeOverridesSnapshot({ ...chromeOv })
        setSubstrateSnapshot({ ...sub })
        setTypographySnapshot({ ...typ })
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

  // Dirty = ANY of the three drafts disagrees with its snapshot.
  const isDirty = useMemo(
    () =>
      !deepEqualBlob(chromeOverridesDraft, chromeOverridesSnapshot) ||
      !deepEqualBlob(substrateDraft, substrateSnapshot) ||
      !deepEqualBlob(typographyDraft, typographySnapshot),
    [
      chromeOverridesDraft,
      chromeOverridesSnapshot,
      substrateDraft,
      substrateSnapshot,
      typographyDraft,
      typographySnapshot,
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

    const payload = editSessionId
      ? {
          chrome_overrides: latestChromeOverrides,
          substrate: latestSubstrate,
          typography: latestTypography,
          edit_session_id: editSessionId,
        }
      : {
          chrome_overrides: latestChromeOverrides,
          substrate: latestSubstrate,
          typography: latestTypography,
        }

    try {
      const updated = await focusTemplatesService.update(targetId, payload)
      activeTemplateIdRef.current = updated.id
      const chromeOv = (updated.chrome_overrides ?? {}) as ChromeOverridesBlob
      const sub = (updated.substrate ?? {}) as SubstrateBlob
      const typ = (updated.typography ?? {}) as TypographyBlob
      setTemplate(updated)
      setChromeOverridesSnapshot({ ...chromeOv })
      setSubstrateSnapshot({ ...sub })
      setTypographySnapshot({ ...typ })
      setLastSavedAt(new Date())
    } catch (err) {
      // 410 Gone retry — mirror C-2.1.1 cores path.
      const activeId = extractStaleActiveTemplateId(err)
      if (activeId && activeId !== targetId) {
        activeTemplateIdRef.current = activeId
        try {
          const updated = await focusTemplatesService.update(activeId, payload)
          activeTemplateIdRef.current = updated.id
          const chromeOv = (updated.chrome_overrides ??
            {}) as ChromeOverridesBlob
          const sub = (updated.substrate ?? {}) as SubstrateBlob
          const typ = (updated.typography ?? {}) as TypographyBlob
          setTemplate(updated)
          setChromeOverridesSnapshot({ ...chromeOv })
          setSubstrateSnapshot({ ...sub })
          setTypographySnapshot({ ...typ })
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

  const discard = useCallback(() => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
      debounceTimer.current = null
    }
    setChromeOverridesDraft({ ...chromeOverridesSnapshot })
    setSubstrateDraft({ ...substrateSnapshot })
    setTypographyDraft({ ...typographySnapshot })
  }, [chromeOverridesSnapshot, substrateSnapshot, typographySnapshot])

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
    updateChromeOverrides,
    updateSubstrate,
    updateTypography,
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
