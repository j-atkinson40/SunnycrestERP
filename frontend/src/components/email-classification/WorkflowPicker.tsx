/**
 * WorkflowPicker — filtered Select for choosing a workflow target.
 *
 * Used by:
 *   - TriggerConfigEditor — `fire_action.workflow_id` for non-suppress
 *     rules.
 *   - CategoryEditor — `mapped_workflow_id` for Tier 2 routing.
 *
 * Filter rules per investigation §10 risk #8 + R-5.1 universal-fallback
 * convention:
 *   - Inactive workflows are excluded from the visible list.
 *   - When `tenantVertical` is provided, workflows whose `vertical` is
 *     null (cross-vertical / platform-global) are always visible. When
 *     `vertical` is set on a workflow, it's visible only when matching
 *     the caller's tenant vertical.
 *   - `null` `tenantVertical` falls back to showing all active
 *     workflows (universal-show — useful for tenants without a vertical
 *     assignment yet).
 *
 * v1 ships with native search via the Select trigger's typeahead. A
 * dedicated search input inside the popup is deferred to R-6.x when
 * concrete operator signal warrants (the canonical workflow library
 * size on Sunnycrest staging is ~30, well within typeahead reach).
 *
 * Empty / null selection: pass `value={null}` and the component renders
 * the placeholder text. `allowNone` enables an explicit "Don't auto-route"
 * sentinel — used by CategoryEditor's nullable mapping.
 */

import * as React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { WorkflowSummary } from "@/types/email-classification";

const NONE_SENTINEL = "__none__";

export interface WorkflowPickerProps {
  workflows: WorkflowSummary[];
  value: string | null;
  onChange: (workflowId: string | null) => void;
  /** When set, applies the tenant-vertical filter (workflows with
   *  vertical=null OR vertical=match are visible). */
  tenantVertical?: string | null;
  placeholder?: string;
  disabled?: boolean;
  /** Adds an explicit "Don't auto-route" sentinel that resolves to null. */
  allowNone?: boolean;
  noneLabel?: string;
  "data-testid"?: string;
}

/**
 * Pure visibility filter. Exported separately so tests can exercise
 * the universal-fallback semantic without rendering the Select.
 */
export function filterWorkflowsForPicker(
  workflows: WorkflowSummary[],
  tenantVertical: string | null | undefined,
): WorkflowSummary[] {
  const active = workflows.filter((w) => w.is_active !== false);
  if (!tenantVertical) {
    // Null tenantVertical => show every active workflow (universal
    // fallback per R-5.1 ButtonPicker precedent).
    return active;
  }
  return active.filter(
    (w) => w.vertical === null || w.vertical === tenantVertical,
  );
}

export function WorkflowPicker({
  workflows,
  value,
  onChange,
  tenantVertical,
  placeholder = "Select a workflow…",
  disabled = false,
  allowNone = false,
  noneLabel = "Don't auto-route",
  ...props
}: WorkflowPickerProps) {
  const visible = React.useMemo(
    () => filterWorkflowsForPicker(workflows, tenantVertical),
    [workflows, tenantVertical],
  );

  const selectValue =
    value === null && allowNone ? NONE_SENTINEL : value ?? "";

  function handleChange(next: string | null) {
    if (next === NONE_SENTINEL) {
      onChange(null);
    } else if (typeof next === "string" && next.length > 0) {
      onChange(next);
    }
  }

  return (
    <Select
      value={selectValue}
      onValueChange={handleChange}
      disabled={disabled}
    >
      <SelectTrigger data-testid={props["data-testid"] ?? "workflow-picker"}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {allowNone ? (
          <SelectItem value={NONE_SENTINEL} data-testid="workflow-picker-none">
            {noneLabel}
          </SelectItem>
        ) : null}
        {visible.length === 0 ? (
          <div className="px-3 py-4 text-caption text-content-muted">
            No active workflows match your tenant vertical.
          </div>
        ) : (
          visible.map((wf) => (
            <SelectItem
              key={wf.id}
              value={wf.id}
              data-testid={`workflow-picker-option-${wf.id}`}
            >
              <span className="flex flex-col items-start">
                <span className="font-medium text-content-strong">
                  {wf.name}
                </span>
                {wf.description ? (
                  <span className="text-caption text-content-muted">
                    {wf.description}
                  </span>
                ) : null}
              </span>
            </SelectItem>
          ))
        )}
      </SelectContent>
    </Select>
  );
}
