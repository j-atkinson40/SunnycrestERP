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
 * focusCoresService.update(coreId, { chrome: draft }) automatically.
 *
 * Dirty state: derived from JSON-stringify equality with the last
 * persisted snapshot. Updated synchronously on every updateDraft.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import {
  focusCoresService,
  type CoreRecord,
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
}

const AUTO_SAVE_DEBOUNCE_MS = 300

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

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inFlightCoreId = useRef<string | null>(null)

  // Load on coreId change.
  useEffect(() => {
    if (!coreId) {
      setCore(null)
      setDraft({})
      setSavedSnapshot({})
      setError(null)
      return
    }
    let cancelled = false
    setIsLoading(true)
    setError(null)
    inFlightCoreId.current = coreId
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

  const isDirty =
    JSON.stringify(draft) !== JSON.stringify(savedSnapshot)

  const save = useCallback(async () => {
    if (!coreId) return
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
      debounceTimer.current = null
    }
    setIsSaving(true)
    setError(null)
    try {
      const updated = await focusCoresService.update(coreId, { chrome: draft })
      const chrome = (updated.chrome ?? {}) as ChromeDraft
      setCore(updated)
      setSavedSnapshot({ ...chrome })
      setLastSavedAt(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed")
    } finally {
      setIsSaving(false)
    }
  }, [coreId, draft])

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
  }
}

export default useFocusCoreDraft
