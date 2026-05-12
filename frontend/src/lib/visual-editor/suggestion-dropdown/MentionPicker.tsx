/**
 * Arc 4b.2b — MentionPicker component.
 *
 * Second consumer of SuggestionDropdown (after Arc 4b.1b slash
 * command). Renders entity-type tabs (case/order/contact/product per
 * Q-COUPLING-1 picker subset) + a debounced query against the
 * Arc 4b.2a mention endpoint, surfacing matched candidates inside
 * the canonical SuggestionDropdown chrome.
 *
 * Companion to `useMentionPicker` hook. The hook owns trigger
 * detection + state machine; this component renders the dropdown
 * itself (anchored at cursor coordinates via `getCaretCoordinates`).
 *
 * Consumer pattern:
 *
 *   const fieldRef = useRef<HTMLTextAreaElement | null>(null)
 *   const picker = useMentionPicker({ value, onValueChange, fieldRef })
 *   return (
 *     <>
 *       <textarea ref={fieldRef} value={value}
 *                 onChange={picker.handleInputChange}
 *                 onKeyDown={picker.handleKeyDown} />
 *       <MentionPicker
 *         pickerState={picker.pickerState}
 *         fieldRef={fieldRef}
 *         onSelectCandidate={picker.handleSelectCandidate}
 *         onCancelKeepText={picker.handleCancelKeepText}
 *         onCancelEraseText={picker.handleCancelEraseText}
 *         onSwitchEntityType={picker.setEntityType}
 *       />
 *     </>
 *   )
 *
 * Per-suggestion renderer: entity-type badge + display_name +
 * preview_snippet (mirror of Arc 4b.1b's per-slash-suggestion shape
 * — block_kind + display_name + description).
 *
 * Empty / loading / error states render in the dropdown empty slot.
 *
 * Architectural anchor (canon §14 second-consumer canon validation):
 * SuggestionDropdown's interface holds verbatim under this second
 * consumer — no API changes. The getCaretCoordinates companion
 * utility is the only addition, per Q-ARC4B2-4 settled outcome (b).
 */
import { useEffect, useMemo, useRef, useState } from "react"

import {
  type MentionCandidate,
  type MentionEntityType,
  MENTION_ENTITY_LABELS_PLURAL,
  MENTION_ENTITY_TYPES,
  resolveMention,
} from "@/bridgeable-admin/services/document-mentions-service"

import { getCaretCoordinates } from "./getCaretCoordinates"
import {
  SuggestionDropdown,
  handleSuggestionKeyDown,
} from "./SuggestionDropdown"
import type { MentionPickerState } from "./useMentionPicker"


export interface MentionPickerProps {
  /** Picker state from `useMentionPicker`. When `open === false`
   *  this component renders nothing. */
  pickerState: MentionPickerState
  /** Field ref (textarea or input) — used for caret-position
   *  resolution via getCaretCoordinates. */
  fieldRef: React.RefObject<HTMLTextAreaElement | HTMLInputElement | null>
  /** Operator picked a candidate — insert canonical Jinja token. */
  onSelectCandidate: (candidate: MentionCandidate) => void
  /** Click-outside / α dismissal — preserves typed `@<query>`. */
  onCancelKeepText: () => void
  /** β dismissal — erases `@<query>`. */
  onCancelEraseText: () => void
  /** Switch entity-type tab. */
  onSwitchEntityType: (next: MentionEntityType) => void
  /** Optional debounce in ms for the resolve call. Defaults to 150ms
   *  — tight enough to feel live, loose enough to coalesce key
   *  presses. */
  debounceMs?: number
  /** Optional data-testid override for the root surface. */
  "data-testid"?: string
}


/** Cap suggestion fetch size — Arc 4b.2a endpoint default is 10. */
const DEFAULT_LIMIT = 10


export function MentionPicker({
  pickerState,
  fieldRef,
  onSelectCandidate,
  onCancelKeepText,
  onCancelEraseText,
  onSwitchEntityType,
  debounceMs = 150,
  "data-testid": testid = "documents-mention-picker",
}: MentionPickerProps) {
  const [results, setResults] = useState<MentionCandidate[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const requestSeq = useRef<number>(0)

  // Compute caret coordinates each render while open. Recomputed
  // when query / triggerPosition / entityType changes (cursor moves).
  const position = useMemo(() => {
    if (!pickerState.open) return { top: 0, left: 0 }
    const el = fieldRef.current
    if (!el) return { top: 0, left: 0 }
    // Position the dropdown UNDER the line containing the cursor.
    // Use the cursor position (NOT the trigger) so the dropdown
    // follows the user's typing if they navigate within the query.
    const cursorPos =
      pickerState.triggerPosition + 1 + pickerState.query.length
    const caret = getCaretCoordinates(el, cursorPos)
    // Add ~22px so the dropdown sits below the caret line, not
    // overlapping. Approximates line-height of the canonical
    // `caption` text size.
    return { top: caret.top + 22, left: caret.left }
  }, [pickerState.open, pickerState.triggerPosition, pickerState.query, fieldRef])

  // Debounced fetch on query / entityType change.
  useEffect(() => {
    if (!pickerState.open) {
      setResults([])
      setError(null)
      setActiveId(null)
      return
    }
    const seq = ++requestSeq.current
    setIsLoading(true)
    setError(null)

    const handle = setTimeout(() => {
      void resolveMention({
        entity_type: pickerState.entityType,
        query: pickerState.query,
        limit: DEFAULT_LIMIT,
      })
        .then((res) => {
          if (seq !== requestSeq.current) return // stale
          setResults(res.results)
          setIsLoading(false)
          // Initialize activeId to first result.
          if (res.results.length > 0) {
            setActiveId(makeKey(res.results[0]))
          } else {
            setActiveId(null)
          }
        })
        .catch((err: unknown) => {
          if (seq !== requestSeq.current) return // stale
          setIsLoading(false)
          setError(err instanceof Error ? err.message : "Failed to fetch")
          setResults([])
          setActiveId(null)
        })
    }, debounceMs)

    return () => clearTimeout(handle)
  }, [pickerState.open, pickerState.entityType, pickerState.query, debounceMs])

  if (!pickerState.open) return null

  return (
    <div data-testid={testid} data-mention-open="true">
      {/* Entity-type tabs (rendered ABOVE the dropdown via the
          position offset). Renders as a sibling so SuggestionDropdown
          can stay presentation-only. */}
      <div
        role="tablist"
        aria-label="Mention entity type"
        data-testid={`${testid}-tabs`}
        style={{
          position: "fixed",
          top: position.top - 32,
          left: position.left,
          zIndex: 51, // above dropdown (z-50)
        }}
        className="flex gap-0.5 rounded-t-md border border-b-0 border-border-subtle bg-surface-elevated px-1 py-0.5 shadow-level-1"
      >
        {MENTION_ENTITY_TYPES.map((kind) => {
          const isActive = kind === pickerState.entityType
          return (
            <button
              key={kind}
              type="button"
              role="tab"
              aria-selected={isActive}
              data-testid={`${testid}-tab-${kind}`}
              data-active={isActive ? "true" : "false"}
              onMouseDown={(e) => {
                // Don't blur the field — onMouseDown + preventDefault
                // keeps focus on the textarea so keystrokes after
                // selection land correctly.
                e.preventDefault()
                onSwitchEntityType(kind)
              }}
              className={[
                "rounded-sm px-2 py-0.5 text-micro uppercase tracking-wider transition-colors",
                isActive
                  ? "bg-accent-subtle text-content-strong"
                  : "text-content-muted hover:bg-accent-subtle/30",
              ].join(" ")}
            >
              {MENTION_ENTITY_LABELS_PLURAL[kind]}
            </button>
          )
        })}
      </div>

      <SuggestionDropdown<MentionCandidate>
        suggestions={results}
        activeId={activeId}
        onActiveChange={setActiveId}
        onSelect={onSelectCandidate}
        onCancel={onCancelKeepText}
        getKey={makeKey}
        position={position}
        width={340}
        renderSuggestion={(c, active) => (
          <div data-testid={`${testid}-row-${c.entity_id}`}>
            <div className="flex items-center gap-1.5">
              <span
                className="rounded-sm border border-border-subtle bg-surface-elevated px-1 py-0.5 font-plex-mono text-micro uppercase text-content-muted"
                data-testid={`${testid}-row-${c.entity_id}-type`}
              >
                {c.entity_type}
              </span>
              <span
                className={`text-body-sm font-medium ${
                  active ? "text-content-strong" : "text-content-base"
                }`}
              >
                {c.display_name}
              </span>
            </div>
            {c.preview_snippet && (
              <div className="mt-0.5 text-caption text-content-muted line-clamp-1">
                {c.preview_snippet}
              </div>
            )}
          </div>
        )}
        renderEmpty={() => (
          <span data-testid={`${testid}-empty`}>
            {isLoading
              ? "Searching…"
              : error
                ? `Error: ${error}`
                : pickerState.query
                  ? `No ${MENTION_ENTITY_LABELS_PLURAL[
                      pickerState.entityType
                    ].toLowerCase()} match “${pickerState.query}”.`
                  : `Start typing to search ${MENTION_ENTITY_LABELS_PLURAL[
                      pickerState.entityType
                    ].toLowerCase()}…`}
          </span>
        )}
        data-testid={`${testid}-dropdown`}
      />
      {/* onCancelEraseText is kept in the props so the consumer
          can pass through to Escape handling via the hook's
          handleKeyDown wiring (textarea keydown invokes
          handleKeyDown which calls cancelEraseText on Escape).
          Suppress unused-prop warning via the void expression. */}
      {void onCancelEraseText}
    </div>
  )
}


/** Stable id for a candidate. */
function makeKey(c: MentionCandidate): string {
  return `${c.entity_type}:${c.entity_id}`
}


/** Re-export the canonical SuggestionDropdown keyboard handler so
 *  consumers can wire keydown directly without an extra import. */
export { handleSuggestionKeyDown }
