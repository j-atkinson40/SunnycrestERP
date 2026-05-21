/**
 * useWidgetAutoSave — WB-4a composition_blob auto-save hook.
 *
 * Mirrors the canonical FF-2 substrate auto-save pattern (used by
 * `useFocusTemplateDraft`): debounced PUT, ref-based stale-closure
 * prevention, fire-and-forget on unmount. Tailored for the simpler
 * WB-4a surface — a single composition_blob, no separate substrate /
 * typography blobs.
 *
 * Per Area 2 lock + Step 8 of the WB-4a build prompt:
 *   - Debounce: 200ms (per spec).
 *   - Dispatches PUT /widget-definitions/{slug}/draft.
 *   - Status indicator: "idle" → "saving" → "saved" → "dirty" (when
 *     local draft differs from last server snapshot).
 *   - Network-failure-resilient: keeps the local state; surfaces an
 *     error so the UI can show "Save failed, retrying...". The next
 *     edit retries by virtue of debounce.
 *   - AbortController cancels in-flight requests when a newer
 *     debounce fires.
 *   - edit_session_id: persistent across the lifetime of the hook
 *     (one session per builder mount). Re-rolled when slug changes.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import type { CompositionBlob } from "@/lib/widget-builder/types/composition-blob"
import {
  widgetBuilderService,
  type WidgetBuilderRecord,
} from "@/bridgeable-admin/services/widget-builder-service"


export type AutoSaveStatus = "idle" | "saving" | "saved" | "dirty" | "error"

export const AUTO_SAVE_DEBOUNCE_MS = 200


function generateSessionId(): string {
  const c =
    typeof globalThis !== "undefined"
      ? (globalThis as { crypto?: { randomUUID?: () => string } }).crypto
      : undefined
  if (c?.randomUUID) {
    return c.randomUUID()
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0
    const v = ch === "x" ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}


export interface UseWidgetAutoSaveOptions {
  slug: string | null
  /** Server snapshot AFTER the most recent successful save. Used as
   *  the "saved" reference for the dirty indicator. */
  lastServerSnapshot: CompositionBlob | null
  /** Called with the freshest server record after each successful
   *  draft PUT. The page-level state syncs from this callback. */
  onSaved: (record: WidgetBuilderRecord) => void
  /** Optional title update piggybacks on the same PUT (rename UI). */
  title?: string
}


export interface UseWidgetAutoSaveResult {
  /** Local in-flight draft (the operator's currently-typed shape). */
  draft: CompositionBlob | null
  /** Apply a new composition_blob. Schedules a debounced save. */
  setDraft: (next: CompositionBlob) => void
  /** Force-flush the pending save immediately. Returns the saved record. */
  flush: () => Promise<WidgetBuilderRecord | null>
  status: AutoSaveStatus
  error: string | null
  /** Session token sent with every draft PUT. */
  editSessionId: string
}


export function useWidgetAutoSave(
  options: UseWidgetAutoSaveOptions,
): UseWidgetAutoSaveResult {
  const { slug, lastServerSnapshot, onSaved, title } = options

  const [draft, setDraftState] = useState<CompositionBlob | null>(
    lastServerSnapshot,
  )
  const [status, setStatus] = useState<AutoSaveStatus>("idle")
  const [error, setError] = useState<string | null>(null)
  const [editSessionId, setEditSessionId] = useState<string>(() =>
    generateSessionId(),
  )

  // Refs to avoid stale closures inside the debounced callback.
  const draftRef = useRef<CompositionBlob | null>(draft)
  const slugRef = useRef<string | null>(slug)
  const titleRef = useRef<string | undefined>(title)
  const onSavedRef = useRef(onSaved)
  const sessionRef = useRef<string>(editSessionId)
  const inFlightAbortRef = useRef<AbortController | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync refs.
  useEffect(() => {
    draftRef.current = draft
  }, [draft])
  useEffect(() => {
    slugRef.current = slug
  }, [slug])
  useEffect(() => {
    titleRef.current = title
  }, [title])
  useEffect(() => {
    onSavedRef.current = onSaved
  }, [onSaved])

  // When slug changes, roll a fresh session + reset draft to server
  // snapshot.
  useEffect(() => {
    const next = generateSessionId()
    sessionRef.current = next
    setEditSessionId(next)
    setDraftState(lastServerSnapshot)
    setStatus("idle")
    setError(null)
    // Reset any pending save.
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    if (inFlightAbortRef.current !== null) {
      inFlightAbortRef.current.abort()
      inFlightAbortRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug])

  // Hydrate draft when the server snapshot transitions from null to
  // populated (initial GET completes after the slug already settled).
  // Subsequent saves update via onSaved, which the page-level state
  // syncs back into lastServerSnapshot; we should NOT clobber the
  // operator's in-flight draft on every snapshot change — only the
  // null → populated transition matters.
  useEffect(() => {
    if (draftRef.current === null && lastServerSnapshot !== null) {
      setDraftState(lastServerSnapshot)
    }
  }, [lastServerSnapshot])

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current)
      if (inFlightAbortRef.current !== null) {
        inFlightAbortRef.current.abort()
      }
    }
  }, [])

  const doSave = useCallback(async (): Promise<WidgetBuilderRecord | null> => {
    const activeSlug = slugRef.current
    const activeBlob = draftRef.current
    if (activeSlug === null || activeBlob === null) return null

    // Cancel any prior in-flight request.
    if (inFlightAbortRef.current !== null) {
      inFlightAbortRef.current.abort()
    }
    const abort = new AbortController()
    inFlightAbortRef.current = abort
    setStatus("saving")
    setError(null)
    try {
      const record = await widgetBuilderService.saveDraft(activeSlug, {
        composition_blob: activeBlob,
        edit_session_id: sessionRef.current,
        title: titleRef.current,
      })
      if (abort.signal.aborted) return null
      setStatus("saved")
      onSavedRef.current(record)
      return record
    } catch (err) {
      if (abort.signal.aborted) return null
      setStatus("error")
      setError(err instanceof Error ? err.message : String(err))
      return null
    } finally {
      if (inFlightAbortRef.current === abort) {
        inFlightAbortRef.current = null
      }
    }
  }, [])

  const setDraft = useCallback(
    (next: CompositionBlob) => {
      setDraftState(next)
      setStatus("dirty")
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current)
      }
      timerRef.current = setTimeout(() => {
        timerRef.current = null
        void doSave()
      }, AUTO_SAVE_DEBOUNCE_MS)
    },
    [doSave],
  )

  const flush = useCallback(async () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    return doSave()
  }, [doSave])

  return {
    draft,
    setDraft,
    flush,
    status,
    error,
    editSessionId,
  }
}
