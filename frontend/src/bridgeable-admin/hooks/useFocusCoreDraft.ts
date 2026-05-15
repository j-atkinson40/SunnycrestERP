/**
 * useFocusCoreDraft — Tier 1 core draft lifecycle (sub-arc C-2.1).
 *
 * Manages load / draft / dirty-state / debounced auto-save for a
 * single Tier 1 core's chrome blob. Pattern-establisher reused by
 * C-2.2's Tier 2 template editor and sub-arc D's Tier 3 in-place
 * editor.
 *
 * coreId === null  → empty draft (creating new core).
 * coreId provided  → fetch on mount, populate draft from
 *                    response.chrome.
 *
 * Auto-save: 300ms after the last updateDraft, the hook calls
 * focusCoresService.update(coreId, { chrome, edit_session_id })
 * automatically.
 *
 * Dirty state: derived from JSON-stringify equality with the last
 * persisted snapshot. Updated synchronously on every updateDraft.
 *
 * Sub-arc C-2.1.1 — session-aware update semantics:
 *
 * On mount (or when `coreId` changes to a real value) the hook
 * generates a fresh UUID v4 edit-session token and sends it with
 * every PUT. The backend mutates in place within a 5-minute window
 * matching that token; outside the window (or with a different
 * token) it version-bumps per B-1.
 *
 * If the backend returns 410 Gone (caller's core_id is now inactive
 * because someone bumped versions outside this session), the hook
 * extracts `active_core_id` from the response body, swaps its
 * internal pointer to the active row, and retries the save once
 * under the SAME session token — the user's scrub keeps going
 * without visible interruption.
 *
 * Session-token lifecycle:
 *   - Generated when coreId transitions null → real value, or
 *     real → different real value.
 *   - Preserved across re-renders for the same coreId.
 *   - NOT persisted across page reload (intentional fresh session).
 *   - NOT used for create / list / get — only for update.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import {
  focusCoresService,
  type CoreRecord,
  type StaleCoreErrorBody,
} from "@/bridgeable-admin/services/focus-cores-service"

export type ChromeDraft = Record<string, unknown>

export interface UseFocusCoreDraftResult {
  /** Loaded core record (null while creating new / loading). */
  core: CoreRecord | null
  /** Current chrome draft. */
  draft: ChromeDraft
  /** Merge a partial chrome update into the draft. */
  updateDraft: (partial: ChromeDraft) => void
  /** Force an immediate save (bypasses debounce). */
  save: () => Promise<void>
  /** Revert draft to last-saved snapshot. */
  discard: () => void
  /** Is draft different from last persisted snapshot? */
  isDirty: boolean
  /** Save in flight? */
  isSaving: boolean
  /** When was the last successful save (Date). */
  lastSavedAt: Date | null
  /** Any load or save error. */
  error: string | null
  /** Load in flight? */
  isLoading: boolean
  /** Current edit-session token (null until the hook attaches to a coreId). */
  editSessionId: string | null
}

const AUTO_SAVE_DEBOUNCE_MS = 300

/**
 * Lightweight UUID v4 generator. Prefers crypto.randomUUID() when
 * available (modern browsers + Node 19+); falls back to a Math.random
 * approximation for older test environments. Not security-sensitive
 * — the session token is an opaque correlation key, not an auth
 * credential.
 */
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
 * Sub-arc C-2.1.3 — dirty-state fix (the real one).
 *
 * C-2.1.2's `deepEqualChrome` was key-order-tolerant but still
 * key-set-strict — it counted `{a: 1, b: null}` and `{a: 1}` as
 * different. Production response from `_core_to_response` stripped
 * null-valued fields (`dict(row.chrome or {})` preserved whatever
 * shape the JSONB column had, and that often dropped never-written
 * fields entirely). Frontend drafts always carried the full
 * 7-field chrome shape (some values null because the user hadn't
 * touched a slider yet). Save round-trip → response has 4 keys,
 * draft has 7, dirty check returned true forever → Unsaved
 * indicator stuck.
 *
 * C-2.1.3 fix:
 *   - Backend `_core_to_response` + `_template_to_response` now
 *     normalize the response to the full canonical field set with
 *     explicit nulls (matching the draft shape).
 *   - This frontend helper additionally treats missing-key and
 *     explicit-null-value as semantically equivalent, defensively
 *     handling any current or future backend serializer that drops
 *     null fields.
 *
 * Equality semantics:
 *   - `{ a: 1, b: null }` deep-equals `{ a: 1 }`           (missing == null)
 *   - `{ a: 1, b: undefined }` deep-equals `{ a: 1 }`      (missing == undefined)
 *   - `{ a: 1, b: null }` deep-equals `{ a: 1, b: null }`  (trivial)
 *   - `{ a: 1, b: 0 }` does NOT deep-equal `{ a: 1 }`      (0 is a real value)
 *
 * Recursive: same rules apply to nested objects/arrays.
 *
 * Limited to the shape `useFocusCoreDraft` traffics in (primitive
 * values, plain objects, arrays of those) — NOT a general
 * structural-equality library.
 */
function deepEqualChrome(a: unknown, b: unknown): boolean {
  if (a === b) return true
  // Treat null and undefined as interchangeable absence.
  if (a == null && b == null) return true
  if (a == null || b == null) return false
  if (typeof a !== typeof b) return false
  if (typeof a !== "object") return false
  if (Array.isArray(a)) {
    if (!Array.isArray(b)) return false
    if (a.length !== b.length) return false
    for (let i = 0; i < a.length; i += 1) {
      if (!deepEqualChrome(a[i], b[i])) return false
    }
    return true
  }
  if (Array.isArray(b)) return false
  const aObj = a as Record<string, unknown>
  const bObj = b as Record<string, unknown>
  // Compare the union of keys; missing-key on one side is
  // equivalent to explicit null/undefined on the other.
  const allKeys = new Set([...Object.keys(aObj), ...Object.keys(bObj)])
  for (const k of allKeys) {
    const av = Object.prototype.hasOwnProperty.call(aObj, k)
      ? aObj[k]
      : undefined
    const bv = Object.prototype.hasOwnProperty.call(bObj, k)
      ? bObj[k]
      : undefined
    if (!deepEqualChrome(av, bv)) return false
  }
  return true
}


function extractStaleActiveId(err: unknown): string | null {
  if (!err || typeof err !== "object") return null
  const e = err as {
    response?: { status?: number; data?: { detail?: StaleCoreErrorBody } }
  }
  if (e.response?.status !== 410) return null
  const detail = e.response?.data?.detail
  if (!detail || typeof detail !== "object") return null
  return typeof detail.active_core_id === "string" ? detail.active_core_id : null
}

export function useFocusCoreDraft(
  coreId: string | null,
): UseFocusCoreDraftResult {
  const [core, setCore] = useState<CoreRecord | null>(null)
  const [draft, setDraft] = useState<ChromeDraft>({})
  const [savedSnapshot, setSavedSnapshot] = useState<ChromeDraft>({})
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)
  // Sub-arc C-2.1.1: session token. Generated lazily per coreId.
  const [editSessionId, setEditSessionId] = useState<string | null>(null)
  // Active id may diverge from `coreId` after a 410-Gone retry — we
  // keep editing the same logical core via its new active row id.
  const activeCoreIdRef = useRef<string | null>(null)

  // Sub-arc C-2.1.4: draftRef tracks the latest draft so `save` can
  // read it via mutable reference rather than closure capture. Without
  // this, save's setTimeout (registered in updateDraft) captures the
  // draft value at registration time; subsequent rapid updateDraft
  // calls advance the state but the queued save still reads the old
  // closure value. Result on a continuous scrub: every save persists
  // a value one event behind the actual draft, so savedSnapshot ===
  // draft is never true and isDirty never clears.
  const draftRef = useRef<ChromeDraft>({})

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inFlightCoreId = useRef<string | null>(null)

  // Sub-arc C-2.1.4: keep draftRef in sync with draft state so the
  // save callback always reads the latest committed draft, not the
  // closure-captured one.
  useEffect(() => {
    draftRef.current = draft
  }, [draft])

  // Load on coreId change.
  useEffect(() => {
    if (!coreId) {
      setCore(null)
      setDraft({})
      setSavedSnapshot({})
      setError(null)
      setEditSessionId(null)
      activeCoreIdRef.current = null
      return
    }
    let cancelled = false
    setIsLoading(true)
    setError(null)
    inFlightCoreId.current = coreId
    activeCoreIdRef.current = coreId
    // Fresh session token per coreId transition. Page reload generates
    // a new one too (intentional — page reload = new session).
    setEditSessionId(generateSessionToken())
    focusCoresService
      .get(coreId)
      .then((rec) => {
        if (cancelled) return
        const chrome = (rec.chrome ?? {}) as ChromeDraft
        setCore(rec)
        setDraft({ ...chrome })
        setSavedSnapshot({ ...chrome })
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : "Failed to load core")
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [coreId])

  // Sub-arc C-2.1.3: dirty check via key-order-AND-key-set-tolerant
  // deep equality (see deepEqualChrome above for why). useMemo so we
  // recompute only when draft or savedSnapshot identity changes.
  const isDirty = useMemo(
    () => !deepEqualChrome(draft, savedSnapshot),
    [draft, savedSnapshot],
  )

  const save = useCallback(async () => {
    const targetId = activeCoreIdRef.current ?? coreId
    if (!targetId) return
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
      debounceTimer.current = null
    }
    setIsSaving(true)
    setError(null)

    // Sub-arc C-2.1.4: read latest draft via ref, not closure. The
    // closure value (`draft`) is captured at save-callback creation
    // time; rapid updateDraft calls advance the React state but the
    // queued save would still send the stale closure value.
    const latestDraft = draftRef.current
    const payload = editSessionId
      ? { chrome: latestDraft, edit_session_id: editSessionId }
      : { chrome: latestDraft }

    try {
      const updated = await focusCoresService.update(targetId, payload)
      activeCoreIdRef.current = updated.id
      const chrome = (updated.chrome ?? {}) as ChromeDraft
      setCore(updated)
      setSavedSnapshot({ ...chrome })
      setLastSavedAt(new Date())
    } catch (err) {
      // Sub-arc C-2.1.1: 410 Gone retry path. The id we're holding is
      // stale (someone version-bumped outside this session). Switch
      // to the active id surfaced in the error body and retry once
      // under the same session token.
      const activeId = extractStaleActiveId(err)
      if (activeId && activeId !== targetId) {
        activeCoreIdRef.current = activeId
        try {
          const updated = await focusCoresService.update(activeId, payload)
          activeCoreIdRef.current = updated.id
          const chrome = (updated.chrome ?? {}) as ChromeDraft
          setCore(updated)
          setSavedSnapshot({ ...chrome })
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
    // Sub-arc C-2.1.4: deps intentionally exclude `draft` — save
    // reads it from draftRef.current to avoid the stale-closure race.
  }, [coreId, editSessionId])

  const updateDraft = useCallback(
    (partial: ChromeDraft) => {
      setDraft((prev) => ({ ...prev, ...partial }))
      if (!coreId) return
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
      debounceTimer.current = setTimeout(() => {
        void save()
      }, AUTO_SAVE_DEBOUNCE_MS)
    },
    [coreId, save],
  )

  const discard = useCallback(() => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
      debounceTimer.current = null
    }
    setDraft({ ...savedSnapshot })
  }, [savedSnapshot])

  // Cleanup pending timer on unmount.
  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
    }
  }, [])

  return {
    core,
    draft,
    updateDraft,
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

export default useFocusCoreDraft
