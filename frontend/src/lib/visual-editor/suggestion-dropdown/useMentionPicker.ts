/**
 * Arc 4b.2b — useMentionPicker hook.
 *
 * Encapsulates mention-trigger state for a textarea OR input field:
 *   - Watches the field's value + selectionStart for the `@` trigger
 *   - Tracks the partial query typed after `@`
 *   - Provides callbacks for keyboard navigation + selection
 *   - On selection, inserts the canonical `{{ ref(...) }}` token at
 *     the trigger position, replacing `@<query>` with the token
 *   - On β-Escape: clears `@<query>` AND closes (consistent with
 *     Arc 4b.1b slash command Escape semantics — see DocumentsTab
 *     `SlashCommandInput.cancel()` for reference)
 *   - On backspace deletion of `@`: closes
 *
 * Consumer contract:
 *   const {
 *     pickerState,           // { open, triggerPosition, query, entityType }
 *     handleInputChange,     // wire onChange
 *     handleKeyDown,         // wire onKeyDown (for activeId nav + Enter + Escape)
 *     handleSelectCandidate, // call with picked candidate
 *     handleCancel,          // call to dismiss
 *     setEntityType,         // for entity-type tab switching
 *   } = useMentionPicker({ value, onValueChange, fieldRef })
 *
 * Then in JSX:
 *   <textarea ref={fieldRef} value={value}
 *             onChange={handleInputChange}
 *             onKeyDown={handleKeyDown} />
 *   {pickerState.open && <MentionPicker ... />}
 *
 * Picker subset (Q-COUPLING-1): case + order + contact + product.
 * UI vocabulary; substrate vocabulary translated at endpoint per
 * Arc 4b.2a backend mention_filter canon.
 *
 * Token serialization: `{{ ref("entity_type", "entity_id") }}` via
 * `buildRefToken` from document-mentions-service. Identical on
 * frontend and backend.
 *
 * State machine:
 *   CLOSED → user types `@` → OPEN(query="", entityType="case")
 *   OPEN → user types char → OPEN(query+=char)
 *   OPEN → user types space → CLOSED (mention is single-token)
 *   OPEN → user presses Escape → CLOSED + erase `@<query>` (β)
 *   OPEN → user presses backspace at `@` → CLOSED (no erase needed)
 *   OPEN → user picks candidate → CLOSED + replace `@<query>` with token
 */
import { useCallback, useRef, useState } from "react"

import type { MentionEntityType } from "@/bridgeable-admin/services/document-mentions-service"
import {
  MENTION_ENTITY_TYPES,
  buildRefToken,
} from "@/bridgeable-admin/services/document-mentions-service"


/** State of the mention picker. `open === false` is the resting
 *  state — no picker rendered, no queries fired. `triggerPosition`
 *  is the character offset of the `@` in `value`. */
export interface MentionPickerState {
  open: boolean
  /** Character offset of the `@` trigger in the field value. */
  triggerPosition: number
  /** Partial query typed AFTER the `@` (excludes the `@`). */
  query: string
  /** Active entity type tab. Default "case" — operator can switch
   *  via the picker UI. */
  entityType: MentionEntityType
}


const INITIAL_STATE: MentionPickerState = {
  open: false,
  triggerPosition: -1,
  query: "",
  entityType: "case",
}


/** A picked candidate as it arrives from the picker UI. Matches
 *  `MentionCandidate` from document-mentions-service. */
export interface PickedMentionCandidate {
  entity_type: string
  entity_id: string
}


export interface UseMentionPickerOptions {
  /** Current field value (controlled). */
  value: string
  /** Field value setter — called when the picker inserts a token
   *  OR erases on β-Escape. The hook does NOT control the field
   *  directly; consumer threads value/onChange. */
  onValueChange: (next: string) => void
  /** Ref to the underlying textarea / input. Used for cursor
   *  positioning via getCaretCoordinates. */
  fieldRef: React.RefObject<HTMLTextAreaElement | HTMLInputElement | null>
}


export interface UseMentionPickerResult {
  pickerState: MentionPickerState
  /** Wire to the field's onChange. Detects `@` and updates state. */
  handleInputChange: (
    event: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>,
  ) => void
  /** Wire to the field's onKeyDown. Handles Escape (β semantics) +
   *  backspace at trigger. Returns true when key was consumed. */
  handleKeyDown: (
    event: React.KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>,
  ) => boolean
  /** Call when the picker selects a candidate. Inserts the canonical
   *  Jinja ref token at the trigger position, replacing `@<query>`,
   *  and closes the picker. */
  handleSelectCandidate: (candidate: PickedMentionCandidate) => void
  /** Call to cancel without inserting (e.g., dropdown click-outside).
   *  Per α semantics — does NOT erase typed content. Differs from
   *  β-Escape which DOES erase per Q-ARC4B2-5 settled scope. */
  handleCancelKeepText: () => void
  /** Call to cancel with β semantics — erase `@<query>` and close. */
  handleCancelEraseText: () => void
  /** Switch the active entity-type tab. Does not close the picker. */
  setEntityType: (next: MentionEntityType) => void
  /** Force-close (no value mutation). Used for programmatic
   *  dismissal in tests. */
  forceClose: () => void
}


/**
 * Mention picker controller hook.
 *
 * Owns picker state and the precise mutations to apply when:
 *   - The user types `@` at a non-quoted, non-mid-word position
 *   - The user types characters that extend or break the query
 *   - The user picks a candidate (inserts canonical Jinja token)
 *   - The user dismisses via Escape (β semantics — erase) or
 *     click-outside (α semantics — preserve typed content)
 */
export function useMentionPicker({
  value,
  onValueChange,
  fieldRef,
}: UseMentionPickerOptions): UseMentionPickerResult {
  const [pickerState, _setPickerState] = useState<MentionPickerState>(INITIAL_STATE)
  // Track which value we last reacted to so onChange events that
  // ALSO happen to land on `@` don't fire the trigger spuriously
  // when the user pasted multi-character content.
  const lastValueRef = useRef<string>(value)
  // Mirror picker state in a ref so the change handler reads the
  // current state synchronously across consecutive React events
  // within a single tick (e.g., type "@" then type "H" — the second
  // change event must see `open=true` even though React hasn't
  // re-rendered yet). Without this mirror, the change handler closes
  // over the stale render-time pickerState.
  const pickerStateRef = useRef<MentionPickerState>(INITIAL_STATE)

  /** Wrapped setter that updates both React state + the ref mirror
   *  in lockstep so the change handler reads a coherent view. */
  const setPickerState = useCallback(
    (next: MentionPickerState | ((s: MentionPickerState) => MentionPickerState)) => {
      _setPickerState((prev) => {
        const resolved = typeof next === "function" ? next(prev) : next
        pickerStateRef.current = resolved
        return resolved
      })
    },
    [],
  )

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) => {
      const nextValue = event.target.value
      const cursor = event.target.selectionStart ?? nextValue.length
      const prevValue = lastValueRef.current
      lastValueRef.current = nextValue

      // Propagate the value change immediately. Consumer owns the
      // controlled field; the hook just reads `value` and reacts.
      onValueChange(nextValue)

      // Read picker state from the ref mirror (coherent within a tick).
      const currentState = pickerStateRef.current

      // If picker is already open, update query OR close.
      if (currentState.open) {
        const triggerPos = currentState.triggerPosition
        // Validate: trigger position must still be `@`.
        if (triggerPos >= nextValue.length || nextValue[triggerPos] !== "@") {
          // Trigger was deleted — close.
          setPickerState(INITIAL_STATE)
          return
        }
        // Validate: cursor must still be AFTER the trigger.
        if (cursor <= triggerPos) {
          setPickerState(INITIAL_STATE)
          return
        }
        // Extract query = chars between triggerPos+1 and cursor.
        const candidateQuery = nextValue.slice(triggerPos + 1, cursor)
        // If query contains whitespace or newline, the mention is over.
        if (/\s/.test(candidateQuery)) {
          setPickerState(INITIAL_STATE)
          return
        }
        setPickerState((s) => ({ ...s, query: candidateQuery }))
        return
      }

      // Picker closed — check for `@` trigger.
      // Only fire when net delta = single `@` character inserted at
      // cursor-1 (typing OR paste-of-`@`). Avoid firing when paste
      // contains `@` in the middle of pasted text.
      if (nextValue.length !== prevValue.length + 1) return
      if (cursor < 1) return
      const insertedChar = nextValue[cursor - 1]
      if (insertedChar !== "@") return

      // Anchor check: the char BEFORE the `@` must be either
      // (a) start-of-string, (b) whitespace, OR (c) newline.
      // Mid-word `@` (e.g. email addresses) does NOT trigger.
      if (cursor >= 2) {
        const prevChar = nextValue[cursor - 2]
        if (!/[\s\n]/.test(prevChar)) return
      }

      setPickerState({
        open: true,
        triggerPosition: cursor - 1,
        query: "",
        entityType: "case",
      })
    },
    [onValueChange, setPickerState],
  )

  /** Erase `@<query>` from `value`. Used by β-Escape. Reads picker
   *  state from the ref mirror so the operation works consistently
   *  even when invoked synchronously after an open transition. */
  const handleCancelEraseText = useCallback(() => {
    const current = pickerStateRef.current
    if (!current.open) return
    const triggerPos = current.triggerPosition
    const after = triggerPos + 1 + current.query.length
    // Use lastValueRef (latest value the hook has seen) rather than
    // captured `value` to avoid a stale closure.
    const baseValue = lastValueRef.current
    const next = baseValue.slice(0, triggerPos) + baseValue.slice(after)
    onValueChange(next)
    lastValueRef.current = next
    setPickerState(INITIAL_STATE)
    // Restore cursor to triggerPos via DOM after value change.
    // jsdom may not apply this until next tick; consumer can rely
    // on React's controlled-field re-render.
    const el = fieldRef.current
    if (el && typeof el.setSelectionRange === "function") {
      // Defer to next microtask so the value setter has flushed.
      Promise.resolve().then(() => {
        try {
          el.setSelectionRange(triggerPos, triggerPos)
        } catch {
          // jsdom: input type=text without value setter may throw;
          // safe to swallow.
        }
      })
    }
  }, [fieldRef, onValueChange, setPickerState])

  /** Cancel without erasing — used for click-outside dismissal. */
  const handleCancelKeepText = useCallback(() => {
    setPickerState(INITIAL_STATE)
  }, [setPickerState])

  const forceClose = useCallback(() => {
    setPickerState(INITIAL_STATE)
  }, [setPickerState])

  /** Key handler — handles Escape (β semantics) AND backspace at
   *  trigger. Returns true when consumed. Consumer should NOT
   *  forward to SuggestionDropdown's `handleSuggestionKeyDown`
   *  when this returns true. */
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>) => {
      if (!pickerStateRef.current.open) return false
      if (event.key === "Escape") {
        event.preventDefault()
        handleCancelEraseText()
        return true
      }
      // Backspace at trigger: deletes `@`, closes picker. Browser
      // does the deletion; we just close on the resulting onChange.
      // No need to short-circuit here.
      return false
    },
    [handleCancelEraseText],
  )

  /** Insert the canonical Jinja ref token at the trigger position,
   *  replacing `@<query>`. Closes the picker. */
  const handleSelectCandidate = useCallback(
    (candidate: PickedMentionCandidate) => {
      const current = pickerStateRef.current
      if (!current.open) return
      const triggerPos = current.triggerPosition
      const after = triggerPos + 1 + current.query.length
      const token = buildRefToken(candidate.entity_type, candidate.entity_id)
      const baseValue = lastValueRef.current
      const next = baseValue.slice(0, triggerPos) + token + baseValue.slice(after)
      onValueChange(next)
      lastValueRef.current = next
      setPickerState(INITIAL_STATE)
      // Move cursor to AFTER the inserted token.
      const newCursor = triggerPos + token.length
      const el = fieldRef.current
      if (el && typeof el.setSelectionRange === "function") {
        Promise.resolve().then(() => {
          try {
            el.setSelectionRange(newCursor, newCursor)
            el.focus()
          } catch {
            // jsdom safety
          }
        })
      }
    },
    [fieldRef, onValueChange, setPickerState],
  )

  const setEntityType = useCallback(
    (next: MentionEntityType) => {
      setPickerState((s) => (s.open ? { ...s, entityType: next } : s))
    },
    [setPickerState],
  )

  return {
    pickerState,
    handleInputChange,
    handleKeyDown,
    handleSelectCandidate,
    handleCancelKeepText,
    handleCancelEraseText,
    setEntityType,
    forceClose,
  }
}


/** Re-export the canonical picker-subset list for consumers
 *  rendering entity-type tabs without a separate import. */
export { MENTION_ENTITY_TYPES }
export type { MentionEntityType }
