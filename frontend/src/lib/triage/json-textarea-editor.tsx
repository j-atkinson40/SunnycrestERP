/**
 * JsonTextareaEditor — R-6.0b modal JSON-shaped payload editor.
 *
 * Used by WorkflowReviewItemDisplay's edit_and_approve action to mutate
 * the WorkflowReviewItem's input_data prior to commit. R-6.0 ships
 * JSON-textarea as the canonical edit surface for review items —
 * per-template visual editors (e.g. burial-vault canvas, decedent-info
 * structured form) land in R-6.x as Generation Focus templates mature.
 *
 * Validates JSON.parse on Save; parse errors keep the dialog open and
 * surface the error inline so the operator can fix without losing
 * their edits.
 */

import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"


export interface JsonTextareaEditorProps {
  open: boolean
  onClose: () => void
  initialData: unknown
  /** Title rendered in the dialog header. Defaults to
   *  "Edit decision payload". */
  title?: string
  /** Description rendered below the title. */
  description?: string
  onSave: (parsed: unknown) => void | Promise<void>
}


export function JsonTextareaEditor({
  open,
  onClose,
  initialData,
  title = "Edit decision payload",
  description,
  onSave,
}: JsonTextareaEditorProps) {
  const initialText = stringifyForEdit(initialData)
  const [text, setText] = useState(initialText)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // Resync the textarea when the dialog re-opens with a new payload.
  useEffect(() => {
    if (open) {
      setText(stringifyForEdit(initialData))
      setError(null)
      setSaving(false)
    }
  }, [open, initialData])

  const handleSave = async () => {
    let parsed: unknown
    try {
      parsed = JSON.parse(text || "null")
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Invalid JSON"
      setError(msg)
      return
    }
    setError(null)
    setSaving(true)
    try {
      await onSave(parsed)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Save failed"
      setError(msg)
      setSaving(false)
      return
    }
    setSaving(false)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose()
      }}
    >
      <DialogContent
        className="max-w-2xl"
        data-testid="json-textarea-editor"
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? (
            <DialogDescription>{description}</DialogDescription>
          ) : null}
        </DialogHeader>

        <div className="flex flex-col gap-2">
          <Label htmlFor="json-textarea-editor-textarea">Payload (JSON)</Label>
          <Textarea
            id="json-textarea-editor-textarea"
            value={text}
            onChange={(e) => {
              setText(e.target.value)
              if (error) setError(null)
            }}
            rows={14}
            className="font-plex-mono text-caption"
            data-testid="json-textarea-editor-textarea"
          />
          {error ? (
            <p
              className="text-caption text-status-error"
              data-testid="json-textarea-editor-error"
              role="alert"
            >
              {error}
            </p>
          ) : null}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={saving}
            data-testid="json-textarea-editor-cancel"
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSave}
            disabled={saving}
            data-testid="json-textarea-editor-save"
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}


function stringifyForEdit(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return "{}"
  }
}
