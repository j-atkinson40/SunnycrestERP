/**
 * useActionPicker — state hook for ActionPicker (Lock 4a + Lock 4c).
 *
 * Manages: verb-switch confirm modal state, pending verb selection,
 * commit + cancel. Pure stateful hook — DOES NOT dispatch.
 */
import { useCallback, useState } from "react"

import type { ActionRef } from "@/lib/widget-builder/types/composition-blob"

import {
  type ActionKind,
  hasNonDefaultContent,
  makeDefaultAction,
} from "./types"


export interface UseActionPickerOptions {
  value: ActionRef | null
  onChange: (next: ActionRef | null) => void
}


export interface UseActionPickerResult {
  /** Operator selects a verb from the dropdown. */
  selectVerb: (next: ActionKind | "") => void
  /** Verb-switch confirm modal: which verb is pending. */
  pendingVerb: ActionKind | null
  /** Verb-switch confirm modal: commit the swap. Wipes prior config. */
  commitPendingVerb: () => void
  /** Verb-switch confirm modal: cancel the swap. */
  cancelPendingVerb: () => void
}


export function useActionPicker({
  value,
  onChange,
}: UseActionPickerOptions): UseActionPickerResult {
  const [pendingVerb, setPendingVerb] = useState<ActionKind | null>(null)

  const selectVerb = useCallback(
    (next: ActionKind | "") => {
      if (next === "") {
        // Empty selection — clear the action entirely.
        if (value && hasNonDefaultContent(value)) {
          setPendingVerb(null)
          // Treat "" as wipe; surface a confirm via setting
          // pendingVerb to a sentinel? Phase 1: simple wipe-with-no-
          // confirm for empty selection.
        }
        onChange(null)
        return
      }
      if (!value) {
        // First selection — set defaults directly.
        onChange(makeDefaultAction(next))
        return
      }
      if (value.action_kind === next) {
        return // no-op
      }
      // Switching verbs. Per Lock 4c, confirm if prior config has
      // non-default content; otherwise wipe directly.
      if (hasNonDefaultContent(value)) {
        setPendingVerb(next)
      } else {
        onChange(makeDefaultAction(next))
      }
    },
    [onChange, value],
  )

  const commitPendingVerb = useCallback(() => {
    if (pendingVerb !== null) {
      onChange(makeDefaultAction(pendingVerb))
      setPendingVerb(null)
    }
  }, [onChange, pendingVerb])

  const cancelPendingVerb = useCallback(() => {
    setPendingVerb(null)
  }, [])

  return {
    selectVerb,
    pendingVerb,
    commitPendingVerb,
    cancelPendingVerb,
  }
}
