/**
 * AddNoteTablet (park.add-note) — a LIGHT act. S-5 slice 1.
 *
 * The DM-fan-out's second light tablet: add a note to a customer record.
 * Declares no Focus; stays in park. Commits ONLY at Save via the shipped
 * `customerService.createNote`.
 *
 * The record-picker is a PORTALED surface (the AncillaryPoolPin class) —
 * it routes through `FocusPopover`, which lifts the popup above the park
 * layer and self-asserts `pointer-events: auto`, so it stays clickable in
 * the production tier. If it couldn't self-assert, that's the NAMED STOP;
 * it can (reuses the S-3b FocusPopover mechanism).
 */

import { useEffect, useRef, useState } from "react"
import { Loader2, Save, Search } from "lucide-react"

import type { WidgetRendererProps } from "@/components/focus/canvas/widget-renderers"
import { registerWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import {
  FocusPopover,
  FocusPopoverContent,
  FocusPopoverTrigger,
} from "@/components/focus/FocusPopover"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { usePark } from "@/contexts/park-context"
import { customerService } from "@/services/customer-service"

interface NoteDraft {
  customerId?: string
  customerName?: string
  text?: string
  saved?: boolean
}

import { TabletFrame } from "./_shell"

export function AddNoteTablet({ widgetId }: WidgetRendererProps) {
  const { tablets, updateDraft } = usePark()
  const draft = (tablets.find((t) => t.tabletId === widgetId)?.draft ??
    {}) as NoteDraft
  const [saving, setSaving] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<{ id: string; name: string }[]>([])
  const debounced = useDebouncedValue(query, 200)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!pickerOpen) return
    const q = debounced.trim()
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    customerService
      .getCustomers(1, 8, q || undefined)
      .then((res) => {
        if (ctrl.signal.aborted) return
        setResults((res.items ?? []).map((c) => ({ id: c.id, name: c.name })))
      })
      .catch(() => {})
    return () => ctrl.abort()
  }, [debounced, pickerOpen])

  async function save() {
    if (!draft.customerId || !draft.text?.trim() || draft.saved) return
    setSaving(true)
    try {
      await customerService.createNote(draft.customerId, {
        note_type: "general",
        content: draft.text.trim(),
      })
      updateDraft(widgetId, (prev) => ({ ...prev, saved: true }))
    } finally {
      setSaving(false)
    }
  }

  return (
    <TabletFrame
      title="Add note"
      footer={
        <div className="flex items-center justify-between">
          <span className="text-caption text-content-subtle">
            {draft.saved ? "Saved to record" : "Not saved"}
          </span>
          <Button
            size="sm"
            onClick={save}
            disabled={
              saving || draft.saved || !draft.customerId || !draft.text?.trim()
            }
            data-testid="park-note-save"
          >
            {saving ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Save className="size-3.5" />
            )}
            Save
          </Button>
        </div>
      }
    >
      <div className="flex h-full flex-col gap-2">
        {/* Portaled record-picker — FocusPopover self-asserts pointer-
            events + z-lift above the park layer. */}
        <FocusPopover open={pickerOpen} onOpenChange={setPickerOpen}>
          <FocusPopoverTrigger
            render={
              <Button
                variant="outline"
                size="sm"
                className="justify-start"
                data-testid="park-note-record-trigger"
              >
                <Search className="size-3.5" />
                {draft.customerName ?? "Choose a record…"}
              </Button>
            }
          />
          <FocusPopoverContent
            align="start"
            className="w-72 p-2"
            data-testid="park-note-record-popover"
          >
            <Input
              autoFocus
              value={query}
              placeholder="Search customers…"
              onChange={(e) => setQuery(e.target.value)}
              className="h-8"
              data-testid="park-note-record-search"
            />
            <ul className="mt-2 max-h-48 overflow-y-auto" role="listbox">
              {results.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={draft.customerId === c.id}
                    onClick={() => {
                      updateDraft(widgetId, (prev) => ({
                        ...prev,
                        customerId: c.id,
                        customerName: c.name,
                      }))
                      setPickerOpen(false)
                    }}
                    className="flex w-full items-center rounded px-2 py-1.5 text-left text-body-sm text-content-base hover:bg-accent-subtle hover:text-content-strong"
                  >
                    {c.name}
                  </button>
                </li>
              ))}
            </ul>
          </FocusPopoverContent>
        </FocusPopover>

        <Textarea
          value={draft.text ?? ""}
          disabled={draft.saved}
          placeholder="Note…"
          onChange={(e) =>
            updateDraft(widgetId, (prev) => ({ ...prev, text: e.target.value }))
          }
          className="min-h-[6rem] flex-1 resize-none"
          data-testid="park-note-text"
        />
      </div>
    </TabletFrame>
  )
}

registerWidgetRenderer("park.add-note", AddNoteTablet)
