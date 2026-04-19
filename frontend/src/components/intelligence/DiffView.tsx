/**
 * Minimal side-by-side diff view for a set of named fields.
 *
 * The activation / rollback flow compares a draft (or target) against the
 * currently active version. We show each changed field on its own row
 * with a "before" and "after" panel. Unchanged fields are collapsed.
 *
 * No external diff library — rendering the whole field both-sides is
 * clearer for prompt editing than line-level hunks (prompts are usually
 * short and humans scan them as a whole).
 */

import type { PromptVersionResponse } from "@/types/intelligence";

type FieldKey =
  | "system_prompt"
  | "user_template"
  | "variable_schema"
  | "response_schema"
  | "model_preference"
  | "max_tokens"
  | "temperature"
  | "force_json"
  | "supports_vision"
  | "vision_content_type";

const FIELDS: Array<{ key: FieldKey; label: string; kind: "text" | "json" | "scalar" }> = [
  { key: "system_prompt", label: "System prompt", kind: "text" },
  { key: "user_template", label: "User template", kind: "text" },
  { key: "variable_schema", label: "Variable schema", kind: "json" },
  { key: "response_schema", label: "Response schema", kind: "json" },
  { key: "model_preference", label: "Model preference", kind: "scalar" },
  { key: "max_tokens", label: "Max tokens", kind: "scalar" },
  { key: "temperature", label: "Temperature", kind: "scalar" },
  { key: "force_json", label: "Force JSON", kind: "scalar" },
  { key: "supports_vision", label: "Supports vision", kind: "scalar" },
  { key: "vision_content_type", label: "Vision content type", kind: "scalar" },
];

function stringify(val: unknown, kind: "text" | "json" | "scalar"): string {
  if (val === null || val === undefined) return "";
  if (kind === "json") return JSON.stringify(val, null, 2);
  if (kind === "text") return String(val);
  return String(val);
}

function isChanged(a: unknown, b: unknown, kind: "text" | "json" | "scalar"): boolean {
  if (kind === "json") {
    return JSON.stringify(a ?? null) !== JSON.stringify(b ?? null);
  }
  return (a ?? null) !== (b ?? null);
}

interface Props {
  before: PromptVersionResponse;
  after: PromptVersionResponse | Partial<PromptVersionResponse>;
  beforeLabel?: string;
  afterLabel?: string;
}

export function DiffView({
  before,
  after,
  beforeLabel = "Current",
  afterLabel = "Proposed",
}: Props) {
  const changed = FIELDS.filter((f) => {
    const beforeVal = (before as unknown as Record<string, unknown>)[f.key];
    const afterVal = (after as unknown as Record<string, unknown>)[f.key];
    return isChanged(beforeVal, afterVal, f.kind);
  });

  if (changed.length === 0) {
    return (
      <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
        No changes detected between these two versions.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {changed.map((f) => {
        const b = stringify(
          (before as unknown as Record<string, unknown>)[f.key],
          f.kind,
        );
        const a = stringify(
          (after as unknown as Record<string, unknown>)[f.key],
          f.kind,
        );
        return (
          <div key={f.key} className="space-y-1">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {f.label}
            </div>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <DiffPanel label={beforeLabel} tone="before" content={b} />
              <DiffPanel label={afterLabel} tone="after" content={a} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DiffPanel({
  label,
  tone,
  content,
}: {
  label: string;
  tone: "before" | "after";
  content: string;
}) {
  const toneClass =
    tone === "before"
      ? "border-destructive/30 bg-destructive/5"
      : "border-primary/30 bg-primary/5";
  return (
    <div className={`rounded-md border ${toneClass}`}>
      <div className="border-b px-2 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <pre
        className="max-h-80 overflow-auto whitespace-pre-wrap break-words p-2 font-mono text-xs leading-5"
      >
        {content || <span className="italic text-muted-foreground">(empty)</span>}
      </pre>
    </div>
  );
}
