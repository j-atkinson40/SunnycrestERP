/**
 * Arc 4b.1b — SuggestionDropdown shared component.
 *
 * Ninth canonical shared authoring component primitive (after
 * NodeConfigForm / BlockConfigEditor / BlockKindPicker /
 * InteractivePlacementCanvas / deep-link-state / IconPicker /
 * HierarchicalEditorBrowser / PropControlDispatcher).
 *
 * Generic floating list-of-suggestions surface, parameterized by
 * suggestion type + renderer. Consumers own the keyboard model only
 * for the trigger event (`/` keystroke OR programmatic open); the
 * dropdown handles internal navigation (ArrowUp / ArrowDown / Enter /
 * Escape) once open. State (`activeId`) is controlled so the consumer
 * can keep the trigger input in sync (e.g. echo the highlighted
 * suggestion name into the editor while the dropdown is open).
 *
 * Consumption pattern (slash command — Arc 4b.1b):
 *
 *   const [open, setOpen] = useState(false)
 *   const [activeId, setActiveId] = useState<string | null>(null)
 *   const [query, setQuery] = useState("")
 *
 *   const suggestions = useMemo(
 *     () => blockKinds.filter((k) => k.kind.includes(query)),
 *     [blockKinds, query],
 *   )
 *
 *   <SuggestionDropdown
 *     suggestions={suggestions}
 *     activeId={activeId}
 *     onActiveChange={setActiveId}
 *     onSelect={(s) => { onInsertBlock(s.kind); setOpen(false) }}
 *     onCancel={() => setOpen(false)}
 *     getKey={(s) => s.kind}
 *     renderSuggestion={(s, active) => (
 *       <div>
 *         <div>{s.display_name}</div>
 *         <div className="text-content-muted">{s.description}</div>
 *       </div>
 *     )}
 *     position={{ top: caretRect.bottom, left: caretRect.left }}
 *   />
 *
 * Future consumers:
 *   - Workflows tab: `/` summons node-type picker at the node-config
 *     edit input (when a 4th level lands per generic-stack canon).
 *   - Focus compositions tab: `/` summons widget-kind picker at the
 *     composition palette field.
 *   - Command bar: any inline summon UX wanting a floating tile list
 *     positioned at the caret.
 *
 * Pattern locks vs. the canon: SuggestionDropdown is presentation-only
 * (renders suggestions + handles internal keyboard nav); consumers
 * own the trigger (`/` keystroke + position resolution + query state).
 * NodeConfigForm + BlockConfigEditor are similarly presentation-only.
 * BlockKindPicker is a full-screen modal alternative; this primitive
 * is the inline-floating variant for when the operator's cursor
 * position matters.
 *
 * Chrome per DESIGN_LANGUAGE §14: bg-surface-raised + shadow-level-2 +
 * border-border-subtle (overlay family); active row gets
 * `bg-accent-subtle` + `border-accent` for the brass highlight.
 * `data-active="true"` attribute on the highlighted row carries the
 * source-badge semantics so tests can assert against state, not
 * style.
 */
import { useEffect, useMemo, useRef } from "react"


export interface SuggestionDropdownProps<T> {
  /** Ordered list of suggestion records. Filter / search at the
   *  consumer level; this primitive renders them verbatim. Empty list
   *  is rendered as an empty-state row (per renderEmpty prop) — does
   *  NOT auto-cancel. */
  suggestions: T[]
  /** Currently-highlighted suggestion id (matches getKey output).
   *  Null when nothing is active (e.g., empty list). Consumer manages
   *  this so it can be echoed back into the trigger input if desired. */
  activeId: string | null
  /** Emit on internal ArrowUp / ArrowDown navigation OR on a hover
   *  event that the consumer wires up. Consumer updates state +
   *  re-renders with the new activeId. */
  onActiveChange: (next: string | null) => void
  /** Emit on Enter OR click. Consumer typically closes + inserts. */
  onSelect: (suggestion: T) => void
  /** Emit on Escape OR click-outside. Consumer typically closes. */
  onCancel: () => void
  /** Extract the canonical id from a suggestion. Stable across
   *  re-renders. */
  getKey: (suggestion: T) => string
  /** Render the suggestion row body. Receives (suggestion, isActive).
   *  Consumer renders display name + description + any per-kind
   *  preview chrome. */
  renderSuggestion: (suggestion: T, isActive: boolean) => React.ReactNode
  /** Optional empty-state body when suggestions[] is empty. Defaults
   *  to a generic "No matches" caption. */
  renderEmpty?: () => React.ReactNode
  /** Absolute position (top + left in CSS px) for the floating
   *  surface. Consumer computes from caret / input position. The
   *  primitive renders position:fixed so it floats above siblings. */
  position: { top: number; left: number }
  /** Optional width override. Defaults to 280px — fits the inspector
   *  380px column with margin. */
  width?: number
  /** Optional max-height override. Defaults to 280px — clamps so
   *  long lists scroll within the surface. */
  maxHeight?: number
  /** Optional data-testid root override. */
  "data-testid"?: string
}


/** Locked keyboard model — consumed by the trigger element via the
 *  exported `handleKeyDown` helper. Trigger element should forward
 *  its keydown events through this; the primitive ALSO listens at
 *  the document level for Escape so click-outside-the-trigger
 *  cancels cleanly. */
export function handleSuggestionKeyDown<T>(
  event: React.KeyboardEvent | KeyboardEvent,
  opts: {
    suggestions: T[]
    activeId: string | null
    onActiveChange: (next: string | null) => void
    onSelect: (s: T) => void
    onCancel: () => void
    getKey: (s: T) => string
  },
): boolean {
  const { suggestions, activeId, onActiveChange, onSelect, onCancel, getKey } =
    opts

  // Find current index (or -1 if not present).
  const currentIndex = suggestions.findIndex((s) => getKey(s) === activeId)

  if (event.key === "ArrowDown") {
    event.preventDefault()
    if (suggestions.length === 0) return true
    const nextIndex =
      currentIndex < 0 || currentIndex >= suggestions.length - 1
        ? 0
        : currentIndex + 1
    onActiveChange(getKey(suggestions[nextIndex]))
    return true
  }
  if (event.key === "ArrowUp") {
    event.preventDefault()
    if (suggestions.length === 0) return true
    const prevIndex =
      currentIndex <= 0 ? suggestions.length - 1 : currentIndex - 1
    onActiveChange(getKey(suggestions[prevIndex]))
    return true
  }
  if (event.key === "Enter") {
    event.preventDefault()
    if (currentIndex < 0) {
      // No active suggestion + Enter → cancel (don't insert garbage).
      // Pick first if list non-empty.
      if (suggestions.length > 0) {
        onSelect(suggestions[0])
      } else {
        onCancel()
      }
      return true
    }
    onSelect(suggestions[currentIndex])
    return true
  }
  if (event.key === "Escape") {
    event.preventDefault()
    onCancel()
    return true
  }
  return false
}


export function SuggestionDropdown<T>({
  suggestions,
  activeId,
  onActiveChange,
  onSelect,
  onCancel,
  getKey,
  renderSuggestion,
  renderEmpty,
  position,
  width = 280,
  maxHeight = 280,
  "data-testid": testid = "suggestion-dropdown",
}: SuggestionDropdownProps<T>) {
  const surfaceRef = useRef<HTMLDivElement | null>(null)
  const activeRowRef = useRef<HTMLDivElement | null>(null)

  // Map for fast lookup.
  const keyToIndex = useMemo(() => {
    const map = new Map<string, number>()
    suggestions.forEach((s, i) => {
      map.set(getKey(s), i)
    })
    return map
  }, [suggestions, getKey])

  // Document-level click-outside cancellation. Mounted while the
  // surface is rendered; cleaned up when the consumer unmounts the
  // dropdown.
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!surfaceRef.current) return
      if (e.target instanceof Node && !surfaceRef.current.contains(e.target)) {
        // Click outside surface — cancel. Consumer can re-open if
        // appropriate.
        onCancel()
      }
    }
    document.addEventListener("mousedown", onDocClick)
    return () => {
      document.removeEventListener("mousedown", onDocClick)
    }
  }, [onCancel])

  // Document-level Escape — defense-in-depth. The trigger element
  // already handles Escape via `handleSuggestionKeyDown`, but if
  // focus drifted off the trigger (rare), the document listener
  // still cancels.
  useEffect(() => {
    function onDocKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onCancel()
      }
    }
    document.addEventListener("keydown", onDocKey)
    return () => {
      document.removeEventListener("keydown", onDocKey)
    }
  }, [onCancel])

  // Scroll active row into view when it changes. jsdom's HTMLElement
  // doesn't implement scrollIntoView; guard defensively.
  useEffect(() => {
    if (activeId === null || !activeRowRef.current) return
    if (typeof activeRowRef.current.scrollIntoView !== "function") return
    activeRowRef.current.scrollIntoView({
      block: "nearest",
      behavior: "auto",
    })
  }, [activeId])

  const isEmpty = suggestions.length === 0

  return (
    <div
      ref={surfaceRef}
      role="listbox"
      aria-label="Suggestions"
      data-testid={testid}
      style={{
        position: "fixed",
        top: position.top,
        left: position.left,
        width,
        maxHeight,
      }}
      className="z-50 overflow-y-auto rounded-md border border-border-subtle bg-surface-raised shadow-level-2"
    >
      {isEmpty ? (
        <div
          className="px-3 py-2 text-caption text-content-muted"
          data-testid={`${testid}-empty`}
        >
          {renderEmpty ? renderEmpty() : <>No matches.</>}
        </div>
      ) : (
        <div className="flex flex-col">
          {suggestions.map((s) => {
            const id = getKey(s)
            const isActive = id === activeId
            return (
              <div
                key={id}
                ref={isActive ? activeRowRef : null}
                role="option"
                aria-selected={isActive}
                data-testid={`${testid}-option-${id}`}
                data-active={isActive ? "true" : "false"}
                onMouseEnter={() => onActiveChange(id)}
                onMouseDown={(e) => {
                  // Prevent the parent click-outside listener from
                  // firing before onSelect runs. mousedown fires
                  // BEFORE click, and the document listener
                  // intercepts mousedown.
                  e.preventDefault()
                  onSelect(s)
                }}
                className={[
                  "cursor-pointer border-l-2 px-3 py-2 transition-colors",
                  isActive
                    ? "border-accent bg-accent-subtle/60 text-content-strong"
                    : "border-transparent text-content-base hover:bg-accent-subtle/30",
                  // Adjacent row separator
                  "border-b border-b-border-subtle last:border-b-0",
                ].join(" ")}
              >
                {renderSuggestion(s, isActive)}
              </div>
            )
          })}
        </div>
      )}
      {!isEmpty && (
        <div
          className="sticky bottom-0 flex items-center gap-2 border-t border-border-subtle bg-surface-elevated px-3 py-1 text-micro uppercase tracking-wider text-content-muted"
          data-testid={`${testid}-hint`}
        >
          <span>
            <kbd className="rounded-sm border border-border-subtle bg-surface-raised px-1 font-plex-mono">
              ↑↓
            </kbd>{" "}
            navigate
          </span>
          <span>
            <kbd className="rounded-sm border border-border-subtle bg-surface-raised px-1 font-plex-mono">
              ↵
            </kbd>{" "}
            insert
          </span>
          <span>
            <kbd className="rounded-sm border border-border-subtle bg-surface-raised px-1 font-plex-mono">
              esc
            </kbd>{" "}
            cancel
          </span>
        </div>
      )}
      {/* Keep keyToIndex referenced for tree-shake stability. */}
      {keyToIndex.size === -1 && null}
    </div>
  )
}
