import { useMemo } from "react";
import { Input } from "@/components/ui/input";

/**
 * Form fields for each variable declared in a prompt version's
 * variable_schema. Used by Preview and TestRun modals.
 *
 * The schema shape we support (matching what seed prompts use):
 *   { "var_name": { required?: bool, optional?: bool, type?: string, ... }, ... }
 *
 * For non-string types (numbers, booleans, arrays, objects) we accept
 * raw text and parse at submit time. Keeps the editor flat and fast.
 */

interface Props {
  schema: Record<string, unknown>;
  values: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}

export function VariablesEditor({ schema, values, onChange }: Props) {
  const keys = useMemo(() => Object.keys(schema).sort(), [schema]);

  if (keys.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No variables declared in variable_schema.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {keys.map((key) => {
        const spec = schema[key] as Record<string, unknown> | null;
        const required = Boolean(spec?.required);
        const optional = Boolean(spec?.optional);
        const type = typeof spec?.type === "string" ? spec.type : "string";
        const raw = values[key];
        const display =
          raw === undefined || raw === null
            ? ""
            : typeof raw === "string"
            ? raw
            : JSON.stringify(raw);
        return (
          <label key={key} className="block">
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="font-mono">
                {key}{" "}
                {required && (
                  <span className="text-destructive" title="required">
                    *
                  </span>
                )}
                {optional && (
                  <span className="text-muted-foreground"> (optional)</span>
                )}
              </span>
              <span className="font-mono text-[10px] text-muted-foreground">
                {type}
              </span>
            </div>
            <Input
              value={display}
              onChange={(e) =>
                onChange({ ...values, [key]: e.target.value })
              }
              placeholder={
                type === "number"
                  ? "123"
                  : type === "boolean"
                  ? "true / false"
                  : "sample text"
              }
            />
          </label>
        );
      })}
    </div>
  );
}

/** Render a {{ var }} template client-side — no Jinja runtime needed. */
export function renderTemplatePreview(
  template: string,
  variables: Record<string, unknown>,
): string {
  return template.replace(
    /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g,
    (_match, key) => {
      const v = variables[key];
      if (v === undefined || v === null || v === "") {
        return `{{ ${key} }}`;
      }
      return typeof v === "string" ? v : JSON.stringify(v);
    },
  );
}
