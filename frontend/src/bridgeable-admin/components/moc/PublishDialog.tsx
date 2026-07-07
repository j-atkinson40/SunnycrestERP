/**
 * Publish dialog (Focus Variations V-2) — the explicit release boundary.
 *
 * Editing a default is PRIVATE until this. The dialog shows the
 * unpublished delta (derived from the retained snapshots) + a patch-notes
 * field PREFILLED with the derived scaffold (authored-with-derived-
 * fallback: the author edits intent over mechanics, or keeps the
 * scaffold). Publishing creates one offer per downstream variation —
 * the count is shown before the click commits (consequence legible).
 */

import * as React from "react"
import { toast } from "sonner"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { UpdateDiffList } from "@/bridgeable-admin/components/moc/UpdateDiffList"
import {
  getPublishPreview,
  publishCoreUpdate,
  type PublishPreview,
} from "@/bridgeable-admin/services/moc-service"
import type { MoCTypeCardEntry } from "@/bridgeable-admin/components/moc/MoCTypeCards"

export function PublishDialog({
  source,
  onClose,
  onPublished,
}: {
  /** The default (a focus-cores entry; artifact_id = the ACTIVE core id). */
  source: MoCTypeCardEntry
  onClose: () => void
  onPublished: (offersCreated: number) => void
}) {
  const [preview, setPreview] = React.useState<PublishPreview | null>(null)
  const [failed, setFailed] = React.useState(false)
  const [notes, setNotes] = React.useState("")
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    if (!source.artifact_id) return
    getPublishPreview(source.artifact_id)
      .then((p) => {
        setPreview(p)
        setNotes(p.scaffold) // the derived fallback, editable into intent
      })
      .catch(() => setFailed(true))
  }, [source.artifact_id])

  async function submit() {
    if (!source.artifact_id) return
    setSaving(true)
    try {
      const r = await publishCoreUpdate({
        core_id: source.artifact_id,
        patch_notes: notes.trim() || null,
      })
      onPublished(r.offers_created)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Publish failed")
      setSaving(false)
    }
  }

  const nothingToPublish = preview?.already_published === true

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-lg" data-testid="publish-dialog">
        <DialogHeader>
          <DialogTitle>Publish update — {source.label}</DialogTitle>
          <DialogDescription>
            {preview
              ? nothingToPublish
                ? `v${preview.current_version} is already published — edit the default first.`
                : `v${preview.published_version ?? "—"} → v${preview.current_version}. ` +
                  `${preview.downstream_count} downstream template${
                    preview.downstream_count === 1 ? "" : "s"
                  } will be offered this update.`
              : failed
                ? "Couldn't load the preview."
                : "Loading the unpublished delta…"}
          </DialogDescription>
        </DialogHeader>

        {preview && !nothingToPublish ? (
          <div className="space-y-4">
            <div className="max-h-44 overflow-y-auto">
              <UpdateDiffList fields={preview.derived_diff.fields} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="publish-notes">Patch notes</Label>
              <Textarea
                id="publish-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                data-testid="publish-notes-input"
              />
              <p className="text-caption text-content-subtle">
                Prefilled with the derived summary — say WHY, not just what.
              </p>
            </div>
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            onClick={() => void submit()}
            disabled={!preview || nothingToPublish || saving}
            data-testid="publish-confirm-button"
          >
            {saving ? "Publishing…" : "Publish"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
