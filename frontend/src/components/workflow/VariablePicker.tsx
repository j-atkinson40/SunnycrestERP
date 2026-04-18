/**
 * VariablePicker — dropdown that lets the user insert a {input.step_key.field}
 * or {output.step_key.field} variable reference into a text field.
 *
 * Usage:
 *   <VariablePicker
 *     priorSteps={steps.slice(0, currentIndex)}
 *     onSelect={(variable) => insertAtCursor(variable)}
 *   />
 */
import { useState, useRef } from "react";
import { ChevronDown, Variable } from "lucide-react";

export interface StepSummary {
  step_key: string;
  step_type: string;
  display_name?: string | null;
  config?: Record<string, unknown>;
}

interface VariableGroup {
  label: string;        // e.g. "ask_details (Collect Input)"
  prefix: string;       // e.g. "output.ask_details"
  fields: string[];     // e.g. ["quantity", "note"]
}

function inferOutputFields(step: StepSummary): string[] {
  const cfg = step.config ?? {};
  if (step.step_type === "input") {
    // Each input field is keyed by step_key + field_key
    const key = (cfg.field_key as string) || "value";
    return [key];
  }
  if (step.step_type === "action") {
    return ["result", "id", "status"];
  }
  if (step.step_type === "playwright_action") {
    const mapping = cfg.output_mapping as Record<string, string> | undefined;
    if (mapping && Object.keys(mapping).length > 0) {
      return Object.keys(mapping);
    }
    return ["result", "status"];
  }
  if (step.step_type === "condition") {
    return ["matched"];
  }
  return ["value"];
}

function buildGroups(priorSteps: StepSummary[]): VariableGroup[] {
  const groups: VariableGroup[] = [];

  // Static {trigger.*} inputs are always available
  groups.push({
    label: "trigger (Workflow trigger)",
    prefix: "input.trigger",
    fields: ["context", "user_id", "timestamp"],
  });

  for (const step of priorSteps) {
    const name = step.display_name || step.step_key;
    const typeLabel =
      step.step_type === "playwright_action" ? "Automation" : step.step_type;
    groups.push({
      label: `${name} (${typeLabel})`,
      prefix: `output.${step.step_key}`,
      fields: inferOutputFields(step),
    });

    // Input steps also expose collected values under input.*
    if (step.step_type === "input") {
      const key = ((step.config ?? {}).field_key as string) || "value";
      groups.push({
        label: `${name} → user input`,
        prefix: `input.${step.step_key}`,
        fields: [key],
      });
    }
  }

  return groups;
}

interface VariablePickerProps {
  priorSteps: StepSummary[];
  onSelect: (variable: string) => void;
  className?: string;
}

export default function VariablePicker({
  priorSteps,
  onSelect,
  className = "",
}: VariablePickerProps) {
  const [open, setOpen] = useState(false);
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  const groups = buildGroups(priorSteps);

  function handleSelect(prefix: string, field: string) {
    onSelect(`{${prefix}.${field}}`);
    setOpen(false);
    setExpandedGroup(null);
  }

  return (
    <div className={`relative inline-block ${className}`} ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors"
      >
        <Variable className="w-3 h-3" />
        Insert variable
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute z-50 left-0 top-full mt-1 w-72 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          <div className="px-3 py-2 bg-gray-50 border-b border-gray-100">
            <p className="text-xs text-gray-500 font-medium">
              References from prior steps
            </p>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {groups.map((group) => (
              <div key={group.prefix}>
                <button
                  type="button"
                  className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-gray-50 text-xs font-medium text-gray-700"
                  onClick={() =>
                    setExpandedGroup(
                      expandedGroup === group.prefix ? null : group.prefix
                    )
                  }
                >
                  <span className="truncate">{group.label}</span>
                  <ChevronDown
                    className={`w-3 h-3 flex-shrink-0 ml-2 transition-transform ${
                      expandedGroup === group.prefix ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {expandedGroup === group.prefix && (
                  <div className="bg-gray-50 border-t border-gray-100">
                    {group.fields.map((field) => (
                      <button
                        key={field}
                        type="button"
                        className="w-full text-left px-5 py-1.5 text-xs text-blue-700 hover:bg-blue-50 font-mono"
                        onClick={() => handleSelect(group.prefix, field)}
                      >
                        {`{${group.prefix}.${field}}`}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {groups.length === 0 && (
              <p className="px-3 py-4 text-xs text-gray-400 text-center">
                No prior steps
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
