import { useCallback, useEffect, useMemo, useState } from "react";
import { intelligenceService } from "@/services/intelligence-service";
import type {
  PromptDetailResponse,
  PromptListItem,
  PromptVersionResponse,
} from "@/types/intelligence";

/**
 * Step-config UI for the `ai_prompt` workflow step (Phase 3d).
 *
 * Lets an admin pick a managed prompt, then maps each variable in the
 * prompt's active version's variable_schema either to a literal value or
 * to a reference string like `{input.step_key.field}` /
 * `{output.step_key.field}`. A small "Insert reference" picker populates
 * references from the list of prior steps.
 *
 * Output structure preview is shown below the variable mapping: either
 * listing fields from response_schema (if present) or noting that the
 * output will be text / generic JSON.
 */

interface PriorStep {
  step_order: number;
  step_key: string;
  step_type: string;
  config: Record<string, unknown>;
}

interface Props {
  cfg: Record<string, unknown>;
  priorSteps: PriorStep[];
  onConfigChange: (patch: Record<string, unknown>) => void;
}

export function AiPromptStepConfig({ cfg, priorSteps, onConfigChange }: Props) {
  const promptKey = (cfg.prompt_key as string) || "";
  const variables = (cfg.variables as Record<string, unknown> | undefined) || {};
  const storeOutputAs = (cfg.store_output_as as string) || "result";

  const [prompts, setPrompts] = useState<PromptListItem[]>([]);
  const [promptDetail, setPromptDetail] = useState<PromptDetailResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    intelligenceService
      .listPrompts({ is_active: true, limit: 500 })
      .then(setPrompts)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  const activeVersion = useMemo<PromptVersionResponse | null>(
    () =>
      promptDetail?.versions.find((v) => v.status === "active") ?? null,
    [promptDetail],
  );

  // Resolve details for the selected prompt_key. Use prompt_key because the
  // step config stores the key (portable across tenants), not the id.
  const loadPromptByKey = useCallback(
    async (key: string) => {
      if (!key) {
        setPromptDetail(null);
        return;
      }
      const match = prompts.find((p) => p.prompt_key === key);
      if (!match) return;
      setLoading(true);
      try {
        const detail = await intelligenceService.getPrompt(match.id);
        setPromptDetail(detail);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [prompts],
  );

  // Re-fetch detail when prompts list arrives OR prompt_key changes.
  useEffect(() => {
    if (promptKey && prompts.length) {
      loadPromptByKey(promptKey);
    }
  }, [promptKey, prompts, loadPromptByKey]);

  const schema = (activeVersion?.variable_schema || {}) as Record<
    string,
    { required?: boolean; optional?: boolean; type?: string } | null
  >;
  const schemaKeys = Object.keys(schema);
  const missingRequired = schemaKeys.filter((k) => {
    const spec = schema[k];
    const required = !!spec?.required;
    return required && !(k in variables);
  });

  function setVariable(name: string, value: string) {
    onConfigChange({
      variables: { ...variables, [name]: value },
    });
  }

  function removeVariable(name: string) {
    const next = { ...variables };
    delete next[name];
    onConfigChange({ variables: next });
  }

  // Available reference options: {input.step_key} for input steps,
  // {output.step_key} for everything else (we can't introspect the
  // output shape without running it, so we suggest the root).
  const referenceOptions = useMemo(() => {
    const opts: { label: string; value: string }[] = [];
    for (const s of priorSteps) {
      if (s.step_type === "input") {
        opts.push({
          label: `Input: ${s.step_key}`,
          value: `{input.${s.step_key}}`,
        });
      } else {
        opts.push({
          label: `Output: ${s.step_key}`,
          value: `{output.${s.step_key}}`,
        });
      }
    }
    return opts;
  }, [priorSteps]);

  return (
    <div className="space-y-4">
      <Field
        label="Managed prompt"
        hint="Pick the prompt to run. Shows active prompts visible to this tenant."
      >
        <select
          value={promptKey}
          onChange={(e) =>
            onConfigChange({ prompt_key: e.target.value, variables: {} })
          }
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">— pick a prompt —</option>
          {prompts.map((p) => (
            <option key={p.id} value={p.prompt_key}>
              {p.prompt_key}
              {p.company_id === null ? " (platform)" : ""}
            </option>
          ))}
        </select>
      </Field>

      {err && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-900">
          {err}
        </div>
      )}

      {loading && (
        <p className="text-xs text-slate-500">Loading prompt details…</p>
      )}

      {promptDetail && activeVersion && (
        <>
          <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-700">
            <div className="font-medium">{promptDetail.display_name}</div>
            {promptDetail.description && (
              <div className="mt-0.5 text-slate-500">
                {promptDetail.description}
              </div>
            )}
            <div className="mt-1 font-mono text-[10px] text-slate-500">
              v{activeVersion.version_number} · {activeVersion.model_preference}
              {activeVersion.force_json ? " · force_json" : ""}
            </div>
          </div>

          <Field
            label="Variables"
            hint="Map each variable to a literal value or a reference string like {input.step.field}."
          >
            {schemaKeys.length === 0 ? (
              <p className="text-xs text-slate-500">
                This prompt declares no variables.
              </p>
            ) : (
              <div className="space-y-2">
                {schemaKeys.map((name) => {
                  const spec = schema[name];
                  const isRequired = !!spec?.required;
                  const isOptional = !!spec?.optional;
                  const value = variables[name];
                  const mapped = name in variables;
                  return (
                    <div
                      key={name}
                      className="rounded border border-slate-200 p-2"
                    >
                      <div className="mb-1 flex items-center justify-between text-[11px]">
                        <span className="font-mono">
                          {name}
                          {isRequired && (
                            <span
                              className="ml-1 text-red-600"
                              title="Required"
                            >
                              *
                            </span>
                          )}
                          {isOptional && (
                            <span className="ml-1 text-slate-400">
                              (optional)
                            </span>
                          )}
                        </span>
                        <span className="font-mono text-[10px] text-slate-500">
                          {spec?.type ?? "string"}
                        </span>
                      </div>
                      <div className="flex gap-1">
                        <input
                          value={
                            typeof value === "string" || typeof value === "number"
                              ? String(value)
                              : ""
                          }
                          onChange={(e) => setVariable(name, e.target.value)}
                          placeholder={
                            isOptional
                              ? "(blank — skip)"
                              : "literal or {input.step.field}"
                          }
                          className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs font-mono"
                        />
                        <select
                          value=""
                          onChange={(e) => {
                            if (!e.target.value) return;
                            setVariable(
                              name,
                              ((value as string) || "") + e.target.value,
                            );
                            e.target.value = "";
                          }}
                          className="rounded border border-slate-300 bg-slate-50 px-1 py-1 text-xs"
                          title="Insert reference from a prior step"
                        >
                          <option value="">Insert ref…</option>
                          {referenceOptions.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                        {mapped && (
                          <button
                            type="button"
                            onClick={() => removeVariable(name)}
                            className="rounded border border-slate-300 px-1 py-1 text-xs"
                            title="Clear"
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Field>

          {missingRequired.length > 0 && (
            <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-900">
              <strong>Required variables missing:</strong>{" "}
              {missingRequired.join(", ")}. The workflow won't save until
              every required variable is mapped.
            </div>
          )}

          <Field
            label="Output structure"
            hint="Preview of what downstream steps can reference."
          >
            <OutputStructurePreview
              version={activeVersion}
              stepKey={storeOutputAs || "result"}
            />
          </Field>

          <Field
            label="Store output as"
            hint="Optional label for the output object. Downstream steps reference {output.this_step_key.field}."
          >
            <input
              value={storeOutputAs}
              onChange={(e) =>
                onConfigChange({ store_output_as: e.target.value })
              }
              placeholder="result"
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm font-mono"
            />
          </Field>
        </>
      )}
    </div>
  );
}

function OutputStructurePreview({
  version,
  stepKey,
}: {
  version: PromptVersionResponse;
  stepKey: string;
}) {
  // If force_json + response_schema has declared field keys at its top level,
  // list them. Otherwise describe the shape.
  const schema = version.response_schema ?? null;
  const hasFields =
    version.force_json &&
    schema &&
    typeof schema === "object" &&
    Object.keys(schema as Record<string, unknown>).length > 0;

  if (hasFields) {
    const keys = Object.keys(schema as Record<string, unknown>);
    return (
      <div className="rounded border border-slate-200 bg-white p-2 text-[11px]">
        <p className="mb-1 text-slate-500">
          Fields available downstream as <code>{`{output.<step>.<field>}`}</code>:
        </p>
        <ul className="space-y-0.5 font-mono text-[11px] text-slate-700">
          {keys.map((k) => (
            <li key={k}>· {`{output.<this_step>.${k}}`}</li>
          ))}
        </ul>
      </div>
    );
  }
  if (version.force_json) {
    return (
      <p className="rounded border border-slate-200 bg-white p-2 text-[11px] text-slate-600">
        Output will be a JSON object. Field names depend on the actual
        response. Reference with{" "}
        <code className="font-mono">{`{output.<this_step>.<field>}`}</code>.
      </p>
    );
  }
  return (
    <p className="rounded border border-slate-200 bg-white p-2 text-[11px] text-slate-600">
      Output is free-form text. Reference with{" "}
      <code className="font-mono">{`{output.${stepKey || "<this_step>"}.text}`}</code>
      .
    </p>
  );
}

function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
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
