/**
 * Arc 3b — Shared BlockConfigEditor (Q-CROSS-2 canon).
 *
 * Extracted from DocumentsEditorPage.tsx so both the standalone
 * editor at `/visual-editor/documents` AND the inspector's
 * Documents tab consume the same component. Single source of truth.
 *
 * Pattern parallels Phase 2b NodeConfigForm extraction precedent:
 * when a standalone editor's inner authoring component is reusable
 * at inspector width (380px), extract to shared module. Both
 * consumers stay in lockstep; no drift.
 *
 * Presentational + self-contained:
 * - Internal draft state via `useState`
 * - Resync on `block.id` / `block.config` change
 * - `dirty` derivation; Save/Reset/Delete buttons
 * - JSON textarea config (per-kind structured editors are a
 *   separate post-arc concern; JSON is the canonical fallback
 *   per existing standalone editor behavior)
 *
 * Save-semantics: per-block immediate writes (Q-DOCS-2 canon).
 * Each `onUpdateConfig(cfg)` call fires the service immediately —
 * NO form-local batching, NO autosave wrapping. Per-block errors
 * surface via the parent's onError flow (parent calls service and
 * propagates errors back through a separate channel).
 */
import { useEffect, useState } from "react"
import { Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import type {
  BlockKindMetadata,
  TemplateBlock,
} from "@/bridgeable-admin/services/document-blocks-service"


export interface BlockConfigEditorProps {
  block: TemplateBlock
  blockKinds: BlockKindMetadata[]
  onUpdateConfig: (config: Record<string, unknown>) => void
  onDelete: () => void
  canEdit: boolean
  /** Optional inline error message for per-block error UX (Q-DOCS-2).
   *  Parent threads error here when the immediate write fails. */
  errorMessage?: string | null
  /** Optional pending state for visual feedback during immediate write. */
  isSaving?: boolean
}


export function BlockConfigEditor({
  block,
  blockKinds,
  onUpdateConfig,
  onDelete,
  canEdit,
  errorMessage,
  isSaving,
}: BlockConfigEditorProps) {
  const kind = blockKinds.find((k) => k.kind === block.block_kind)
  const [draft, setDraft] = useState<Record<string, unknown>>(block.config)
  const [jsonError, setJsonError] = useState<string | null>(null)

  useEffect(() => {
    setDraft(block.config)
    setJsonError(null)
  }, [block.id, block.config])

  const dirty = JSON.stringify(draft) !== JSON.stringify(block.config)

  return (
    <div
      className="px-3 py-2"
      data-testid={`documents-block-config-${block.id}`}
    >
      <div className="text-body-sm font-medium text-content-strong">
        {kind?.display_name ?? block.block_kind}
      </div>
      <div className="mt-0.5 text-caption text-content-muted">
        {kind?.description}
      </div>
      <div className="mt-3">
        <label className="mb-1 block text-micro uppercase tracking-wider text-content-muted">
          Config (JSON)
        </label>
        <textarea
          value={JSON.stringify(draft, null, 2)}
          onChange={(e) => {
            try {
              setDraft(JSON.parse(e.target.value))
              setJsonError(null)
            } catch (err) {
              setJsonError(
                err instanceof Error ? err.message : "Invalid JSON",
              )
            }
          }}
          disabled={!canEdit}
          rows={10}
          className="w-full rounded-sm border border-border-base bg-surface-raised px-2 py-1 font-plex-mono text-[11px]"
          data-testid={`documents-block-config-textarea-${block.id}`}
        />
        {jsonError && (
          <div
            className="mt-1 text-caption text-status-error"
            data-testid={`documents-block-config-json-error-${block.id}`}
          >
            {jsonError}
          </div>
        )}
      </div>
      {errorMessage && (
        <div
          className="mt-2 rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
          data-testid={`documents-block-config-error-${block.id}`}
        >
          {errorMessage}
        </div>
      )}
      <div className="mt-2 flex items-center gap-2">
        <Button
          size="sm"
          onClick={() => onUpdateConfig(draft)}
          disabled={!canEdit || !dirty || !!jsonError || isSaving}
          data-testid={`documents-block-save-${block.id}`}
        >
          {isSaving ? "Saving…" : "Save"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setDraft(block.config)
            setJsonError(null)
          }}
          disabled={!dirty}
          data-testid={`documents-block-reset-${block.id}`}
        >
          Reset
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="ml-auto text-status-error"
          onClick={onDelete}
          disabled={!canEdit}
          data-testid={`documents-block-delete-${block.id}`}
        >
          <Trash2 size={11} className="mr-1" />
          Delete
        </Button>
      </div>
    </div>
  )
}
