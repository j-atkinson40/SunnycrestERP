/**
 * InvokeGenerationFocusConfig — R-6.0b workflow editor inspector pane.
 *
 * Renders inside WorkflowEditorPage's right-rail when the selected
 * canvas node has `type === "invoke_generation_focus"`. Mirrors the
 * shape the backend `_handle_invoke_generation_focus` consumes:
 *
 *   {
 *     focus_id: "burial_vault_personalization_studio",
 *     op_id:    "extract_decedent_info",
 *     kwargs:   { instance_id: "{workflow_input.instance_id}" }
 *   }
 *
 * `kwargs` is authored as a list of source-bindings rows (key + source
 * type + path). Each row produces a `kwargs[key]` entry; literal sources
 * write the raw value, ref sources write a `{<prefix>.<path>}` template
 * string the engine resolves at execution time via `resolve_variables`.
 *
 * R-6.0b ships a hardcoded focus_id catalog (only Burial Vault
 * Personalization Studio is registered today). Future Generation Focus
 * templates extend HEADLESS_DISPATCH on the backend + add an entry
 * here. A registry-driven catalog (R-6.x) replaces the hardcode once
 * 2+ focuses ship.
 */

import { Plus, Trash2 } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"


// ── Hardcoded headless dispatch catalog (mirrors backend) ──────────


/** Source-of-truth for what backend `HEADLESS_DISPATCH` registers.
 *  Future Generation Focuses register on backend → add entry here. */
export const HEADLESS_FOCUS_CATALOG: ReadonlyArray<{
  focus_id: string
  display_name: string
  output_type: string
  ops: ReadonlyArray<{ op_id: string; display_name: string }>
}> = [
  {
    focus_id: "burial_vault_personalization_studio",
    display_name: "Burial Vault Personalization Studio",
    output_type: "burial_vault_personalization_draft",
    ops: [
      { op_id: "extract_decedent_info", display_name: "Extract decedent info" },
      { op_id: "suggest_layout", display_name: "Suggest layout" },
      { op_id: "suggest_text_style", display_name: "Suggest text style" },
    ],
  },
] as const


/** Source-prefix vocabulary aligned with backend `resolve_variables`. */
export const BINDING_SOURCE_TYPES = [
  { value: "literal", display: "Literal value" },
  { value: "current_record", display: "current_record.X" },
  { value: "current_user", display: "current_user.X" },
  { value: "current_company", display: "current_company.X" },
  { value: "incoming_email", display: "incoming_email.X" },
  { value: "incoming_transcription", display: "incoming_transcription.X" },
  { value: "vault_item", display: "vault_item.X" },
  { value: "workflow_input", display: "workflow_input.X" },
] as const


type BindingSourceType = (typeof BINDING_SOURCE_TYPES)[number]["value"]


// ── Bindings ↔ kwargs serialization ─────────────────────────────────


export interface BindingRow {
  key: string
  source_type: BindingSourceType
  path: string
}


/** Convert a kwargs dict back into authoring rows. Reverses
 *  `bindingRowsToKwargs`. Unrecognized values fall back to literal. */
export function kwargsToBindingRows(
  kwargs: Record<string, unknown> | undefined | null,
): BindingRow[] {
  if (!kwargs || typeof kwargs !== "object") return []
  const out: BindingRow[] = []
  for (const [key, raw] of Object.entries(kwargs)) {
    if (typeof raw === "string") {
      const m = raw.match(/^\{([a-z_]+)\.(.+)\}$/)
      if (m) {
        const prefix = m[1] as BindingSourceType
        if (BINDING_SOURCE_TYPES.some((t) => t.value === prefix)) {
          out.push({ key, source_type: prefix, path: m[2] })
          continue
        }
      }
    }
    out.push({ key, source_type: "literal", path: String(raw ?? "") })
  }
  return out
}


/** Convert authoring rows into the `kwargs` dict the backend handler
 *  expects. Empty keys are dropped. */
export function bindingRowsToKwargs(
  rows: BindingRow[],
): Record<string, string> {
  const out: Record<string, string> = {}
  for (const row of rows) {
    const k = row.key.trim()
    if (!k) continue
    if (row.source_type === "literal") {
      out[k] = row.path
    } else {
      out[k] = `{${row.source_type}.${row.path.trim()}}`
    }
  }
  return out
}


// ── Component ───────────────────────────────────────────────────────


export interface InvokeGenerationFocusConfigProps {
  config: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
}


export function InvokeGenerationFocusConfig({
  config,
  onChange,
}: InvokeGenerationFocusConfigProps) {
  const focus_id =
    typeof config.focus_id === "string" ? config.focus_id : ""
  const op_id = typeof config.op_id === "string" ? config.op_id : ""

  const [rows, setRows] = useState<BindingRow[]>(() =>
    kwargsToBindingRows(
      (config.kwargs as Record<string, unknown> | undefined) ?? null,
    ),
  )

  // Resync rows when the underlying node (its config.kwargs) changes —
  // e.g. the operator selects a different node in the canvas.
  useEffect(() => {
    setRows(
      kwargsToBindingRows(
        (config.kwargs as Record<string, unknown> | undefined) ?? null,
      ),
    )
    // We intentionally only care about the kwargs identity here; rows
    // local state owns the per-row edits between syncs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(config.kwargs ?? {})])

  const focusEntry = HEADLESS_FOCUS_CATALOG.find((f) => f.focus_id === focus_id)

  const patchAndPersistRows = useCallback(
    (nextRows: BindingRow[]) => {
      setRows(nextRows)
      onChange({
        ...config,
        kwargs: bindingRowsToKwargs(nextRows),
      })
    },
    [config, onChange],
  )

  const handleFocusChange = (next: string | null) => {
    // Reset op_id when the focus changes (the prior op_id may not exist
    // on the new focus). kwargs stays — operator may want to retain
    // shared bindings.
    onChange({ ...config, focus_id: next ?? "", op_id: "" })
  }

  const handleOpChange = (next: string | null) => {
    onChange({ ...config, op_id: next ?? "" })
  }

  const handleAddBinding = () => {
    patchAndPersistRows([
      ...rows,
      { key: "", source_type: "workflow_input", path: "" },
    ])
  }

  const handleUpdateRow = (idx: number, patch: Partial<BindingRow>) => {
    patchAndPersistRows(
      rows.map((r, i) => (i === idx ? { ...r, ...patch } : r)),
    )
  }

  const handleRemoveRow = (idx: number) => {
    patchAndPersistRows(rows.filter((_, i) => i !== idx))
  }

  return (
    <div
      className="flex flex-col gap-3"
      data-testid="wf-invoke-generation-focus-config"
    >
      <div>
        <Label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Generation Focus
        </Label>
        <Select value={focus_id || undefined} onValueChange={handleFocusChange}>
          <SelectTrigger
            data-testid="wf-invoke-generation-focus-template"
            className="text-caption"
          >
            <SelectValue placeholder="Select Generation Focus" />
          </SelectTrigger>
          <SelectContent>
            {HEADLESS_FOCUS_CATALOG.map((entry) => (
              <SelectItem key={entry.focus_id} value={entry.focus_id}>
                {entry.display_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Operation
        </Label>
        <Select
          value={op_id || undefined}
          onValueChange={handleOpChange}
          disabled={!focusEntry}
        >
          <SelectTrigger
            data-testid="wf-invoke-generation-focus-operation"
            className="text-caption"
          >
            <SelectValue
              placeholder={
                focusEntry
                  ? "Select operation"
                  : "Select a Generation Focus first"
              }
            />
          </SelectTrigger>
          <SelectContent>
            {(focusEntry?.ops ?? []).map((op) => (
              <SelectItem key={op.op_id} value={op.op_id}>
                {op.display_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Output type
        </Label>
        <div
          className="rounded-md border border-border-subtle bg-surface-sunken px-2 py-1.5 font-plex-mono text-caption text-content-muted"
          data-testid="wf-invoke-generation-focus-output-type"
        >
          {focusEntry?.output_type ?? "—"}
        </div>
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <Label className="text-micro uppercase tracking-wider text-content-muted">
            Source bindings (kwargs)
          </Label>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleAddBinding}
            data-testid="wf-invoke-generation-focus-add-binding"
          >
            <Plus size={12} className="mr-1" />
            Add binding
          </Button>
        </div>

        {rows.length === 0 ? (
          <p className="text-caption text-content-muted">
            No bindings yet. Add bindings to pass operation kwargs.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {rows.map((row, idx) => (
              <li
                key={idx}
                className="flex flex-col gap-1.5 rounded-md border border-border-subtle bg-surface-raised p-2"
                data-testid={`wf-invoke-generation-focus-binding-${idx}`}
              >
                <div className="flex items-center gap-1.5">
                  <Input
                    value={row.key}
                    placeholder="kwarg name"
                    onChange={(e) =>
                      handleUpdateRow(idx, { key: e.target.value })
                    }
                    className="h-8 flex-1 font-plex-mono text-caption"
                    data-testid={`wf-invoke-generation-focus-binding-${idx}-key`}
                  />
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    onClick={() => handleRemoveRow(idx)}
                    aria-label="Remove binding"
                    data-testid={`wf-invoke-generation-focus-binding-${idx}-remove`}
                  >
                    <Trash2 size={12} />
                  </Button>
                </div>
                <div className="flex items-center gap-1.5">
                  <Select
                    value={row.source_type}
                    onValueChange={(v) => {
                      if (v) {
                        handleUpdateRow(idx, {
                          source_type: v as BindingSourceType,
                        })
                      }
                    }}
                  >
                    <SelectTrigger
                      className="h-8 w-44 text-caption"
                      data-testid={`wf-invoke-generation-focus-binding-${idx}-source`}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {BINDING_SOURCE_TYPES.map((t) => (
                        <SelectItem key={t.value} value={t.value}>
                          {t.display}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    value={row.path}
                    placeholder={
                      row.source_type === "literal" ? "literal value" : "path"
                    }
                    onChange={(e) =>
                      handleUpdateRow(idx, { path: e.target.value })
                    }
                    className="h-8 flex-1 font-plex-mono text-caption"
                    data-testid={`wf-invoke-generation-focus-binding-${idx}-path`}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
