/**
 * RankedRows — Books Review Arc B B-2. The shared numbered-row selection primitive.
 *
 * THREE consumers (Books Review): candidate pairings, flag destinations, recipient
 * search. Built shared from the start.
 *
 * OWNS: numbered rows (1..9), capture-phase keyboard selection (digit + Arrow/Enter),
 * the input-focus guard, and the escape row.
 * DOES NOT OWN: where rows come from, async loading, debounce, abort, or what "empty"
 * looks like — all caller territory. Handed [] it renders no numbered rows (plus the
 * escape row if given) and never breaks; the caller renders its own empty message.
 *
 * KEYS:
 *  - Digit 1..9 selects that row. Read from `e.code` ("Digit3") first so the Mac
 *    Option layer (Option+3 → "£") doesn't defeat it, then `e.key`. (Harvested from
 *    cmd-digit-shortcuts, which capped at 1..5 and only fired with the command bar
 *    open — this is the 1..9, Focus-scoped generalization.)
 *  - Arrow Up/Down move the active row; Enter selects it. The escape row is NOT in
 *    the arrow cycle.
 *  - The escape row is key `0` — a DISTINCT affordance ("none of these"), below a
 *    divider, NOT numbered as row N+1. `Esc` is left free for the parent to close the
 *    picker.
 *  - Input-focus guard: while an INPUT/TEXTAREA/SELECT/contenteditable is focused
 *    (recipient search), a BARE digit types into it; only a modifier chord
 *    (Option/Cmd/Ctrl + digit) selects. Arrow/Enter work regardless.
 */
import { useEffect, useId, useRef, useState } from "react"

import { cn } from "@/lib/utils"

const MAX_DIGIT = 9

export interface RankedRowsEscape {
  /** Row content, e.g. "None of these — code it manually". */
  label: React.ReactNode
  onSelect: () => void
}

export interface RankedRowContext {
  index: number
  /** 1-based badge number, or null past `maxNumbered`. */
  number: number | null
  active: boolean
}

export interface RankedRowsProps<T> {
  items: T[]
  getKey: (item: T, index: number) => string
  renderItem: (item: T, ctx: RankedRowContext) => React.ReactNode
  onSelect: (item: T, index: number) => void
  /** Keyboard capture on/off. Callers keep at most one instance enabled at a time. */
  enabled?: boolean
  /** The distinct "none of these" exit affordance (key `0`). Omit for no escape row. */
  escape?: RankedRowsEscape
  /** Rows past this many carry no digit badge (still clickable). Default 9. */
  maxNumbered?: number
  className?: string
  ariaLabel?: string
  /**
   * Listbox id. Options get `${id}-opt-{index}` ids so a combobox consumer
   * (recipient search) can point its input's aria-activedescendant at the active
   * option. Defaults to a generated id when omitted.
   */
  id?: string
}

function isEditableTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null
  if (!el || typeof el.tagName !== "string") return false
  const tag = el.tagName
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true
  if (el.isContentEditable) return true
  if (el.getAttribute?.("role") === "textbox") return true
  return false
}

/** 0..9 from `e.code` ("Digit3") first (survives the Mac Option layer), else `e.key`. */
function digitFromEvent(e: KeyboardEvent): number | null {
  if (typeof e.code === "string" && /^Digit[0-9]$/.test(e.code)) {
    return parseInt(e.code.slice(5), 10)
  }
  if (typeof e.key === "string" && /^[0-9]$/.test(e.key)) {
    return parseInt(e.key, 10)
  }
  return null
}

export function RankedRows<T>({
  items,
  getKey,
  renderItem,
  onSelect,
  enabled = true,
  escape,
  maxNumbered = MAX_DIGIT,
  className,
  ariaLabel,
  id,
}: RankedRowsProps<T>) {
  const generatedId = useId()
  const listboxId = id ?? generatedId
  const optionId = (i: number) => `${listboxId}-opt-${i}`
  const numbered = Math.min(items.length, maxNumbered)
  const [active, setActive] = useState(0)

  // Fresh snapshot for the window listener (registered once).
  const ref = useRef({ items, onSelect, escape, enabled, numbered, active })
  ref.current = { items, onSelect, escape, enabled, numbered, active }

  // Reset the active row whenever the item set changes (e.g. a new search page).
  useEffect(() => {
    setActive(0)
  }, [items])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const s = ref.current
      if (!s.enabled) return

      if (e.key === "ArrowDown") {
        if (s.numbered === 0) return
        e.preventDefault()
        setActive((a) => Math.min(a + 1, s.numbered - 1))
        return
      }
      if (e.key === "ArrowUp") {
        if (s.numbered === 0) return
        e.preventDefault()
        setActive((a) => Math.max(a - 1, 0))
        return
      }
      if (e.key === "Enter") {
        if (s.numbered === 0) return
        const i = Math.min(s.active, s.numbered - 1)
        e.preventDefault()
        e.stopPropagation()
        s.onSelect(s.items[i], i)
        return
      }

      const digit = digitFromEvent(e)
      if (digit === null) return
      // While typing, a bare digit types; only a modifier chord selects.
      const chord = (e.altKey || e.metaKey || e.ctrlKey) && !e.shiftKey
      if (isEditableTarget(e.target) && !chord) return

      if (digit === 0) {
        if (!s.escape) return
        e.preventDefault()
        e.stopPropagation()
        s.escape.onSelect()
        return
      }
      if (digit >= 1 && digit <= s.numbered) {
        e.preventDefault()
        e.stopPropagation()
        s.onSelect(s.items[digit - 1], digit - 1)
      }
    }
    window.addEventListener("keydown", handler, { capture: true })
    return () => window.removeEventListener("keydown", handler, { capture: true })
  }, [])

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {/* The list is one Tab stop (roving via aria-activedescendant), so arrow
          nav announces the active option to a screen reader without N tab stops.
          The escape row is a sibling BELOW the listbox — never a listbox option. */}
      <div
        role="listbox"
        tabIndex={0}
        aria-label={ariaLabel}
        aria-activedescendant={numbered > 0 ? optionId(Math.min(active, numbered - 1)) : undefined}
        className="flex flex-col gap-1 rounded-md outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-signature-steel/50"
      >
        {items.map((item, i) => {
          const number = i < maxNumbered ? i + 1 : null
          const isActive = i === active && i < numbered
          return (
            <button
              type="button"
              role="option"
              id={optionId(i)}
              aria-selected={isActive}
              tabIndex={-1}
              key={getKey(item, i)}
              onMouseEnter={() => {
                if (i < numbered) setActive(i)
              }}
              onClick={() => onSelect(item, i)}
              className={cn(
                "flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left",
                "text-content-base transition-colors duration-quick",
                isActive
                  ? "border-border-subtle bg-surface-raised ring-1 ring-inset ring-signature-steel/50"
                  : "border-border-subtle bg-surface-elevated hover:bg-surface-raised",
              )}
            >
              {number !== null && (
                <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded bg-surface-sunken px-1 font-plex-mono text-micro tabular-nums text-content-muted">
                  {number}
                </kbd>
              )}
              <span className="min-w-0 flex-1">
                {renderItem(item, { index: i, number, active: isActive })}
              </span>
            </button>
          )
        })}
      </div>

      {escape && (
        <>
          <div role="separator" className="my-1 h-px bg-border-subtle" />
          <button
            type="button"
            onClick={escape.onSelect}
            className={cn(
              "flex w-full items-center gap-3 rounded-md border border-transparent px-3 py-2 text-left",
              "text-content-muted transition-colors duration-quick",
              "hover:bg-surface-sunken hover:text-content-base",
            )}
          >
            <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded bg-surface-sunken px-1 font-plex-mono text-micro tabular-nums text-content-subtle">
              0
            </kbd>
            <span className="min-w-0 flex-1">{escape.label}</span>
          </button>
        </>
      )}
    </div>
  )
}
