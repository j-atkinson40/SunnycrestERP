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
 * Save-semantics: per-block immediate writes (Q-DOCS-2 canon).
 * Each `onUpdateConfig(cfg)` call fires the service immediately —
 * NO form-local batching, NO autosave wrapping. Per-block errors
 * surface via the parent's onError flow (parent calls service and
 * propagates errors back through a separate channel).
 *
 * ─── Arc 4b.1a — Canonical PropControlDispatcher dispatch ───────
 *
 * Pre-Arc-4b.1a this component rendered a JSON textarea for every
 * block kind. Arc 4b.1a routes per-kind canonical configurableProps
 * schemas (declared in `registry/registrations/document-blocks-config.ts`)
 * through `PropControlDispatcher`. Six block kinds (header,
 * body_section, line_items, totals, signature, conditional_wrapper)
 * dispatch through the canonical chain. Four complex shapes consume
 * the Arc 4b.1a ConfigPropType extension (`tableOfColumns`,
 * `tableOfRows`, `listOfParties`, `conditionalRule`).
 *
 * Unknown block kinds (forward-compat — substrate may ship a new
 * kind ahead of the frontend schema) render the canonical JSON
 * textarea fallback. The condition field for `conditional_wrapper`
 * lives on the block row, NOT in config — this component reads it
 * via a synthetic `__condition__` schema entry that maps to the
 * row column via the parent's `onUpdateCondition` callback (added
 * in Arc 4b.1a additive prop).
 */
import { useEffect, useMemo, useState } from "react"
import { Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { PropControlDispatcher } from "@/lib/visual-editor/components/PropControls"
import {
  getBlockKindConfigSchema,
  getCanonicalFieldsForKind,
} from "@/lib/visual-editor/registry/registrations/document-blocks-config"
import type { ConfigPropSchema } from "@/lib/visual-editor/registry"
import type {
  BlockKindMetadata,
  TemplateBlock,
} from "@/bridgeable-admin/services/document-blocks-service"


/** Synthetic schema key for `conditional_wrapper.condition`. The
 *  underlying storage is `document_template_blocks.condition` (row
 *  column), NOT `config` JSONB. BlockConfigEditor reads the column
 *  through this synthetic key + writes back via `onUpdateCondition`. */
const CONDITION_SYNTHETIC_KEY = "__condition__"


/** Backward-compat helper. Maps the row-column `condition` string
 *  (Jinja fragment OR JSON-serialized ConditionalRule) to the
 *  ConditionalRule shape the control expects. Pre-Arc-4b.1a rows
 *  carried raw Jinja strings (free-form); Arc 4b.1a writes serialized
 *  JSON of ConditionalRule. Reads gracefully degrade. */
function parseConditionForEditor(
  raw: string | null,
): { field: string; operator: string; value?: string } {
  if (!raw) return { field: "", operator: "equals", value: "" }
  // Try to parse as serialized Arc 4b.1a rule
  try {
    const parsed = JSON.parse(raw)
    if (
      parsed &&
      typeof parsed === "object" &&
      typeof parsed.operator === "string"
    ) {
      return {
        field: String(parsed.field ?? ""),
        operator: String(parsed.operator),
        value: parsed.value !== undefined ? String(parsed.value) : "",
      }
    }
  } catch {
    // fall through — legacy raw Jinja
  }
  // Legacy: surface the raw string as the field so the operator
  // tries to migrate the operator forward without losing data.
  return { field: raw, operator: "equals", value: "" }
}


/** Inverse — serialize the rule for storage. Arc 4b.1a writes
 *  serialized JSON so the editor round-trips losslessly. The
 *  block_composer reads the row column and (in a future arc) will
 *  translate to Jinja render-side; for now the composer expects
 *  raw Jinja via the existing `__condition__` config key, so writes
 *  must thread through both paths during the transition. */
function serializeConditionForRow(value: unknown): string {
  if (value && typeof value === "object") {
    return JSON.stringify(value)
  }
  return value === null || value === undefined ? "" : String(value)
}


export interface BlockConfigEditorProps {
  block: TemplateBlock
  blockKinds: BlockKindMetadata[]
  onUpdateConfig: (config: Record<string, unknown>) => void
  /** Arc 4b.1a — additive callback for conditional_wrapper row-column
   *  condition writes. When absent, condition editing falls back to
   *  the canonical JSON textarea path (forward-compat for callers
   *  not yet migrated). */
  onUpdateCondition?: (condition: string | null) => void
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
  onUpdateCondition,
  onDelete,
  canEdit,
  errorMessage,
  isSaving,
}: BlockConfigEditorProps) {
  const kind = blockKinds.find((k) => k.kind === block.block_kind)
  const schemaMap = getBlockKindConfigSchema(block.block_kind)
  const canonicalFields = useMemo(
    () => getCanonicalFieldsForKind(block.block_kind),
    [block.block_kind],
  )

  // Per-field draft for canonical dispatch. JSON-textarea fallback
  // retains its own separate draft state below.
  const [fieldDraft, setFieldDraft] = useState<Record<string, unknown>>(() =>
    buildFieldDraft(block, canonicalFields),
  )
  const [jsonDraft, setJsonDraft] = useState<Record<string, unknown>>(block.config)
  const [jsonError, setJsonError] = useState<string | null>(null)

  useEffect(() => {
    setFieldDraft(buildFieldDraft(block, canonicalFields))
    setJsonDraft(block.config)
    setJsonError(null)
  }, [block.id, block.config, block.condition, canonicalFields])

  // Build a normalized "saved" snapshot in the same shape as the
  // active draft (config keys + synthetic __condition__) so the
  // dirty check is structural.
  const savedFieldSnapshot = useMemo(
    () => buildFieldDraft(block, canonicalFields),
    [block, canonicalFields],
  )

  const dirty =
    schemaMap !== null
      ? JSON.stringify(fieldDraft) !== JSON.stringify(savedFieldSnapshot)
      : JSON.stringify(jsonDraft) !== JSON.stringify(block.config)

  const handleCanonicalSave = () => {
    if (!schemaMap) return
    // Split the draft into config keys + the synthetic condition key
    const { __condition__: synthCondition, ...configFields } = fieldDraft
    onUpdateConfig(configFields)
    if (
      block.block_kind === "conditional_wrapper" &&
      synthCondition !== undefined &&
      onUpdateCondition
    ) {
      const serialized = serializeConditionForRow(synthCondition)
      const next = serialized || null
      if (next !== (block.condition ?? null)) {
        onUpdateCondition(next)
      }
    }
  }

  const handleCanonicalReset = () => {
    setFieldDraft(buildFieldDraft(block, canonicalFields))
  }

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

      {schemaMap ? (
        // ─── Canonical PropControlDispatcher path ──────────────
        <div
          className="mt-3 flex flex-col gap-3"
          data-testid={`documents-block-config-canonical-${block.id}`}
        >
          {Object.entries(schemaMap).map(([fieldKey, schema]) => {
            const isCondition =
              block.block_kind === "conditional_wrapper" &&
              fieldKey === CONDITION_SYNTHETIC_KEY
            // Condition synthetic field requires onUpdateCondition;
            // if the parent didn't provide one, fall back to JSON
            // textarea path below to avoid silent write-loss.
            if (isCondition && !onUpdateCondition) return null
            return (
              <FieldRow
                key={fieldKey}
                fieldKey={fieldKey}
                schema={schema}
                value={fieldDraft[fieldKey]}
                onChange={(next) =>
                  setFieldDraft((d) => ({ ...d, [fieldKey]: next }))
                }
                canEdit={canEdit}
                testid={`documents-block-field-${block.id}-${fieldKey}`}
              />
            )
          })}
          {errorMessage && (
            <div
              className="mt-2 rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
              data-testid={`documents-block-config-error-${block.id}`}
            >
              {errorMessage}
            </div>
          )}
          <div className="mt-1 flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleCanonicalSave}
              disabled={!canEdit || !dirty || isSaving}
              data-testid={`documents-block-save-${block.id}`}
            >
              {isSaving ? "Saving…" : "Save"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={handleCanonicalReset}
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
      ) : (
        // ─── JSON textarea fallback for unknown block kinds ────
        <div
          className="mt-3"
          data-testid={`documents-block-config-fallback-${block.id}`}
        >
          <label className="mb-1 block text-micro uppercase tracking-wider text-content-muted">
            Config (JSON — unrecognized block kind)
          </label>
          <textarea
            value={JSON.stringify(jsonDraft, null, 2)}
            onChange={(e) => {
              try {
                setJsonDraft(JSON.parse(e.target.value))
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
              onClick={() => onUpdateConfig(jsonDraft)}
              disabled={!canEdit || !dirty || !!jsonError || isSaving}
              data-testid={`documents-block-save-${block.id}`}
            >
              {isSaving ? "Saving…" : "Save"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setJsonDraft(block.config)
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
      )}
    </div>
  )
}


// ─── Field row + builder helpers ────────────────────────────────


interface FieldRowProps {
  fieldKey: string
  schema: ConfigPropSchema
  value: unknown
  onChange: (next: unknown) => void
  canEdit: boolean
  testid: string
}

function FieldRow({
  fieldKey,
  schema,
  value,
  onChange,
  canEdit,
  testid,
}: FieldRowProps) {
  const label = schema.displayLabel ?? humanize(fieldKey)
  return (
    <div className="flex flex-col gap-1" data-testid={testid}>
      <label className="text-micro uppercase tracking-wider text-content-muted">
        {label}
      </label>
      {schema.description && (
        <span
          className="text-caption text-content-muted"
          data-testid={`${testid}-description`}
        >
          {schema.description}
        </span>
      )}
      <PropControlDispatcher
        schema={schema}
        value={value}
        onChange={onChange}
        disabled={!canEdit}
        data-testid={`${testid}-control`}
      />
    </div>
  )
}


function buildFieldDraft(
  block: TemplateBlock,
  canonicalFields: string[],
): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const key of canonicalFields) {
    if (
      key === CONDITION_SYNTHETIC_KEY &&
      block.block_kind === "conditional_wrapper"
    ) {
      out[key] = parseConditionForEditor(block.condition ?? null)
      continue
    }
    out[key] = block.config[key]
  }
  return out
}


function humanize(key: string): string {
  return key
    .replace(/^_+/, "")
    .replace(/_+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim()
}
