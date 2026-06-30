/**
 * VocabCell — the inline frequency/type picker (MoC Task Editing 2b).
 *
 * Click → a dropdown reading the constrained vocabulary (2a's list endpoint by
 * kind+vertical), plus a "+ Add value" affordance at the bottom: typing a new
 * value POSTs it to the vocabulary and selects it in one flow — the
 * start-minimal-add-later payoff, IN the picker, not a separate trip. Selecting
 * a value (or clearing) calls `onSelect`; the parent owns the PATCH + error
 * revert. Used both in the table cells and the create/edit panel.
 */
import { useEffect, useRef, useState, type ReactNode } from "react"
import { Check, Plus } from "lucide-react"

import {
  addVocabularyValue,
  listVocabulary,
  type MoCVocabValue,
} from "@/bridgeable-admin/services/moc-service"

export interface VocabCellProps {
  kind: "frequency" | "type"
  value: string | null
  vertical: string
  disabled?: boolean
  /** Selecting a value, clearing (null), or adding (then selecting). */
  onSelect: (value: string | null) => void
  /** The cell display (a pill for type, plain text for frequency, em-dash empty). */
  children: ReactNode
}

export function VocabCell({
  kind, value, vertical, disabled, onSelect, children,
}: VocabCellProps) {
  const [open, setOpen] = useState(false)
  const [values, setValues] = useState<MoCVocabValue[]>([])
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState("")
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    listVocabulary({ kind, vertical }).then(setValues).catch(() => setValues([]))
  }, [open, kind, vertical])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setAdding(false)
      }
    }
    document.addEventListener("mousedown", onDoc)
    return () => document.removeEventListener("mousedown", onDoc)
  }, [open])

  async function commitAdd() {
    const v = draft.trim()
    if (!v || busy) return
    setBusy(true)
    try {
      await addVocabularyValue({ kind, value: v })
      onSelect(v)
      setOpen(false)
      setAdding(false)
      setDraft("")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className="-mx-1 rounded-sm px-1 text-left hover:bg-surface-sunken disabled:cursor-default disabled:hover:bg-transparent"
        data-testid={`vocab-cell-${kind}`}
      >
        {children}
      </button>
      {open && (
        <div
          className="absolute left-0 z-50 mt-1 min-w-[200px] rounded-md border border-border-subtle bg-surface-raised p-1 shadow-level-2"
          data-testid={`vocab-menu-${kind}`}
        >
          <div className="max-h-56 overflow-auto">
            {values.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => { onSelect(v.value); setOpen(false) }}
                className="flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1 text-left text-body-sm text-content-base hover:bg-accent-subtle"
              >
                <span>{v.value}</span>
                {value === v.value ? <Check size={13} className="text-accent" /> : null}
              </button>
            ))}
            {value ? (
              <button
                type="button"
                onClick={() => { onSelect(null); setOpen(false) }}
                className="w-full rounded-sm px-2 py-1 text-left text-body-sm text-content-subtle hover:bg-surface-sunken"
              >
                Clear
              </button>
            ) : null}
          </div>
          <div className="my-1 border-t border-border-subtle" />
          {adding ? (
            <div className="flex items-center gap-1 px-1">
              <input
                autoFocus
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitAdd()
                  if (e.key === "Escape") { setAdding(false); setDraft("") }
                }}
                placeholder={`New ${kind}…`}
                data-testid={`vocab-add-input-${kind}`}
                className="min-w-0 flex-1 rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-body-sm text-content-base focus-visible:border-accent focus-visible:outline-none"
              />
              <button
                type="button"
                onClick={commitAdd}
                disabled={busy || !draft.trim()}
                className="rounded-sm bg-accent px-2 py-1 text-caption font-medium text-content-on-accent disabled:opacity-40"
              >
                Add
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setAdding(true)}
              data-testid={`vocab-add-${kind}`}
              className="flex w-full items-center gap-1.5 rounded-sm px-2 py-1 text-left text-body-sm text-accent hover:bg-accent-subtle"
            >
              <Plus size={13} /> Add value
            </button>
          )}
        </div>
      )}
    </div>
  )
}
