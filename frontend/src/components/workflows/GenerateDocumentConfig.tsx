/**
 * Config UI for the `generate_document` workflow action (Phase D-1).
 *
 * Replaces the generic JSON editor when action_type === "generate_document".
 * Admins get:
 *   - Template key dropdown (hardcoded list in D-1 — matches the file-based
 *     registry in backend/app/services/documents/template_loader.py)
 *   - Document type dropdown (invoice, statement, etc.)
 *   - Title input (supports {variable.references})
 *   - Description input
 *   - Context JSON editor
 *
 * D-2 replaces the template-key dropdown with a DB-backed list.
 */

import { Input } from "@/components/ui/input";

// Keep in sync with backend/app/services/documents/template_loader.py
const TEMPLATE_KEYS: { value: string; label: string }[] = [
  { value: "invoice.modern", label: "Invoice — Modern" },
  { value: "invoice.professional", label: "Invoice — Professional" },
  { value: "invoice.clean_minimal", label: "Invoice — Clean Minimal" },
  { value: "statement.modern", label: "Statement — Modern" },
  { value: "statement.professional", label: "Statement — Professional" },
  { value: "statement.clean_minimal", label: "Statement — Clean Minimal" },
  { value: "price_list.grouped", label: "Price List — Grouped" },
  { value: "disinterment.release_form", label: "Disinterment Release Form" },
];

const DOCUMENT_TYPES: { value: string; label: string }[] = [
  { value: "invoice", label: "Invoice" },
  { value: "statement", label: "Customer statement" },
  { value: "price_list", label: "Price list" },
  { value: "disinterment_release_form", label: "Disinterment release form" },
  { value: "obituary", label: "Obituary" },
  { value: "safety_program", label: "Safety program" },
  { value: "legacy_vault_print", label: "Legacy vault print" },
  { value: "social_service_certificate", label: "Social service certificate" },
  { value: "custom", label: "Custom" },
];

interface Props {
  cfg: Record<string, unknown>;
  onConfigChange: (patch: Record<string, unknown>) => void;
}

export function GenerateDocumentConfig({ cfg, onConfigChange }: Props) {
  const templateKey = (cfg.template_key as string) || "";
  const documentType = (cfg.document_type as string) || "";
  const title = (cfg.title as string) || "";
  const description = (cfg.description as string) || "";
  const context = (cfg.context as Record<string, unknown>) || {};

  function updateContext(text: string) {
    try {
      const parsed = JSON.parse(text || "{}");
      onConfigChange({ context: parsed });
    } catch {
      /* leave as-is; user will fix the JSON */
    }
  }

  return (
    <div className="space-y-3">
      <Field
        label="Template"
        hint="Pick the template this step will render. D-2 replaces this dropdown with a DB-backed registry."
      >
        <select
          value={templateKey}
          onChange={(e) => onConfigChange({ template_key: e.target.value })}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">— pick a template —</option>
          {TEMPLATE_KEYS.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </Field>

      <Field
        label="Document type"
        hint="Used for filtering and listing in the document library."
      >
        <select
          value={documentType}
          onChange={(e) => onConfigChange({ document_type: e.target.value })}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">— pick a type —</option>
          {DOCUMENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </Field>

      <Field
        label="Title"
        hint="Human-readable. Supports {variable.references} that resolve at runtime."
      >
        <Input
          value={title}
          onChange={(e) => onConfigChange({ title: e.target.value })}
          placeholder="Invoice {input.ask_invoice.number}"
        />
      </Field>

      <Field label="Description (optional)">
        <Input
          value={description}
          onChange={(e) => onConfigChange({ description: e.target.value })}
          placeholder="What this document represents"
        />
      </Field>

      <Field
        label="Context (JSON)"
        hint="Variables the template expects. Values can be literals OR {variable.references} — the workflow engine resolves them at runtime."
      >
        <textarea
          className="h-40 w-full rounded border border-slate-300 bg-white p-2 font-mono text-xs leading-5"
          defaultValue={JSON.stringify(context, null, 2)}
          onBlur={(e) => updateContext(e.target.value)}
          spellCheck={false}
        />
      </Field>

      <div className="rounded border border-blue-200 bg-blue-50 p-2 text-[11px] text-blue-900">
        The generated document will appear in the Document library with
        linkage back to this workflow run. Downstream steps can reference{" "}
        <code className="font-mono">{`{output.<step_key>.document_id}`}</code>{" "}
        and{" "}
        <code className="font-mono">{`{output.<step_key>.pdf_url}`}</code>.
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <label className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
          {label}
        </label>
        {hint && <span className="text-[10px] text-slate-400">{hint}</span>}
      </div>
      {children}
    </div>
  );
}
