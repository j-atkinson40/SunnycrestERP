/**
 * TriggerInspector — Phase B sub-arc B-5 (selection-driven chrome).
 *
 * Right-rail inspector shown on BACKGROUND selection (clicking empty
 * canvas). Edits the workflow-level TRIGGER — the genuine gap B-5 closes:
 * no trigger editor existed before (the trigger was preserved on load
 * but uneditable). Background selection is trigger-FOCUSED per the
 * operator decision (option iii): workflow METADATA
 * (display_name/description/scope/forks) stays in the existing left pane
 * and is NOT duplicated here.
 *
 * Shape (audit-first outcome): trigger types are NOT registered in the
 * component registry with configurableProps, so this is a bespoke editor
 * — a `trigger_type` <select> over the 5 canonical values + a JSON editor
 * for `trigger_config` (opaque-per-trigger_type per the canvas_state
 * schema). FILE FORWARD: register trigger types for schema-driven config
 * (then this becomes RegistryDrivenConfig-keyed-by-trigger_type, like
 * the B-3 node inspectors).
 *
 * Mirrors the B-3 inspector contract: `{ trigger, onChange }` where
 * onChange emits the full next trigger; the page proxies it into
 * canvas_state.trigger via the existing mutation + auto-save path.
 */

import { useEffect, useState } from "react"

import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { CanvasTrigger } from "@/bridgeable-admin/services/workflow-templates-service"

/** The 5 canonical trigger_type values (mirrors the CanvasTrigger union
 *  + backend canvas_validator trigger_type enum). */
export const TRIGGER_TYPES: ReadonlyArray<CanvasTrigger["trigger_type"]> = [
  "manual",
  "event",
  "scheduled",
  "time_after_event",
  "time_of_day",
]

const DEFAULT_TRIGGER: CanvasTrigger = {
  trigger_type: "manual",
  trigger_config: {},
}

export interface TriggerInspectorProps {
  /** Current canvas_state.trigger (may be undefined for legacy canvases). */
  trigger: CanvasTrigger | undefined
  onChange: (next: CanvasTrigger) => void
}

export function TriggerInspector({ trigger, onChange }: TriggerInspectorProps) {
  const current = trigger ?? DEFAULT_TRIGGER

  // Local JSON text buffer so invalid-mid-edit JSON doesn't clobber the
  // committed config; commit only parses-clean edits.
  const [configText, setConfigText] = useState(() =>
    JSON.stringify(current.trigger_config ?? {}, null, 2),
  )
  const [configError, setConfigError] = useState<string | null>(null)

  // Resync the buffer when the underlying trigger identity changes (e.g.
  // a different template loads).
  useEffect(() => {
    setConfigText(JSON.stringify(current.trigger_config ?? {}, null, 2))
    setConfigError(null)
    // Keyed on the serialized config; local edits own the buffer between syncs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current.trigger_type, JSON.stringify(current.trigger_config ?? {})])

  return (
    <div className="flex flex-col gap-3" data-testid="trigger-inspector">
      <p className="text-caption text-content-muted">
        Workflow trigger — when this workflow runs. (Name, description &
        scope live in the left panel.)
      </p>

      <div>
        <Label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Trigger type
        </Label>
        <Select
          value={current.trigger_type}
          onValueChange={(next) =>
            onChange({
              trigger_type: next as CanvasTrigger["trigger_type"],
              trigger_config: current.trigger_config ?? {},
            })
          }
        >
          <SelectTrigger
            data-testid="trigger-inspector-type"
            className="text-caption"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TRIGGER_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label className="mb-1.5 block text-micro uppercase tracking-wider text-content-muted">
          Trigger config (JSON)
        </Label>
        <textarea
          value={configText}
          rows={6}
          onChange={(e) => {
            setConfigText(e.target.value)
            try {
              const parsed = JSON.parse(e.target.value || "{}")
              if (
                typeof parsed === "object" &&
                parsed !== null &&
                !Array.isArray(parsed)
              ) {
                setConfigError(null)
                onChange({
                  trigger_type: current.trigger_type,
                  trigger_config: parsed as Record<string, unknown>,
                })
              } else {
                setConfigError("Must be a JSON object")
              }
            } catch {
              setConfigError("Invalid JSON")
            }
          }}
          data-testid="trigger-inspector-config"
          className="w-full rounded-md border border-border-base bg-surface-raised p-2 font-plex-mono text-caption text-content-base"
        />
        {configError && (
          <span
            className="text-caption text-status-error"
            data-testid="trigger-inspector-config-error"
          >
            {configError}
          </span>
        )}
      </div>
    </div>
  )
}
