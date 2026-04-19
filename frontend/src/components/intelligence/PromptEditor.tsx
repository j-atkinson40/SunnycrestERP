import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { intelligenceService } from "@/services/intelligence-service";
import type {
  ModelRouteResponse,
  PromptDetailResponse,
  PromptVersionResponse,
} from "@/types/intelligence";
import { PreviewModal } from "./PreviewModal";
import { TestRunModal } from "./TestRunModal";
import { ActivationDialog } from "./ActivationDialog";

interface Props {
  prompt: PromptDetailResponse;
  draft: PromptVersionResponse;
  activeVersion: PromptVersionResponse | null;
  requiresConfirmationText: boolean;
  modelRoutes: ModelRouteResponse[];
  onSaved: (updated: PromptVersionResponse) => void;
  onDiscarded: () => void;
  onActivated: () => void;
  onCancel: () => void;
}

/**
 * The edit form. State is local to this component — caller gets updated
 * draft rows via `onSaved` and final activation notification via
 * `onActivated`.
 */
export function PromptEditor({
  prompt,
  draft: initialDraft,
  activeVersion,
  requiresConfirmationText,
  modelRoutes,
  onSaved,
  onDiscarded,
  onActivated,
  onCancel,
}: Props) {
  const [draft, setDraft] = useState<PromptVersionResponse>(initialDraft);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [previewOpen, setPreviewOpen] = useState(false);
  const [testRunOpen, setTestRunOpen] = useState(false);
  const [activateOpen, setActivateOpen] = useState(false);
  const [discardConfirmOpen, setDiscardConfirmOpen] = useState(false);

  useEffect(() => {
    setDraft(initialDraft);
  }, [initialDraft]);

  function patchLocal<K extends keyof PromptVersionResponse>(
    key: K,
    value: PromptVersionResponse[K],
  ) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  async function saveDraft() {
    setSaving(true);
    setErr(null);
    try {
      const updated = await intelligenceService.updateDraft(
        prompt.id,
        draft.id,
        {
          system_prompt: draft.system_prompt,
          user_template: draft.user_template,
          variable_schema: draft.variable_schema,
          response_schema: draft.response_schema,
          model_preference: draft.model_preference,
          temperature: draft.temperature,
          max_tokens: draft.max_tokens,
          force_json: draft.force_json,
          supports_vision: draft.supports_vision,
          vision_content_type: draft.vision_content_type,
          changelog: draft.changelog ?? undefined,
        },
      );
      setDraft(updated);
      onSaved(updated);
      toast.success("Draft saved");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function discardDraft() {
    try {
      await intelligenceService.deleteDraft(prompt.id, draft.id);
      onDiscarded();
      toast.success("Draft discarded");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
  }

  const routeOptions = modelRoutes.length
    ? modelRoutes
    : [
        { route_key: draft.model_preference } as ModelRouteResponse,
      ];

  return (
    <div className="space-y-4 rounded-md border border-primary/40 bg-primary/5 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-2 text-lg font-semibold">
            Editing draft v{draft.version_number}
            <Badge variant="outline">draft</Badge>
          </h3>
          <p className="text-xs text-muted-foreground">
            Changes apply only after you click Activate. The current active
            version stays live until then.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setDiscardConfirmOpen(true)}
          >
            Discard draft
          </Button>
        </div>
      </div>

      {/* Field grid */}
      <div className="grid gap-2 md:grid-cols-4">
        <label className="block">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Model preference
          </span>
          <select
            className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            value={draft.model_preference}
            onChange={(e) => patchLocal("model_preference", e.target.value)}
          >
            {routeOptions.map((r) => (
              <option key={r.route_key} value={r.route_key}>
                {r.route_key}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Max tokens
          </span>
          <Input
            type="number"
            value={draft.max_tokens}
            onChange={(e) =>
              patchLocal("max_tokens", parseInt(e.target.value, 10) || 0)
            }
          />
        </label>
        <label className="block">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Temperature
          </span>
          <Input
            type="number"
            step="0.01"
            min="0"
            max="1"
            value={draft.temperature}
            onChange={(e) =>
              patchLocal("temperature", parseFloat(e.target.value) || 0)
            }
          />
        </label>
        <label className="flex items-end gap-2">
          <input
            type="checkbox"
            checked={draft.force_json}
            onChange={(e) => patchLocal("force_json", e.target.checked)}
            className="h-4 w-4"
          />
          <span className="text-xs">Force JSON response</span>
        </label>
      </div>

      <FieldTextarea
        label="System prompt"
        value={draft.system_prompt}
        onChange={(v) => patchLocal("system_prompt", v)}
        rows={8}
      />

      <FieldTextarea
        label="User template"
        value={draft.user_template}
        onChange={(v) => patchLocal("user_template", v)}
        rows={6}
      />

      <FieldJsonEditor
        label="Variable schema"
        value={draft.variable_schema}
        onChange={(v) =>
          patchLocal(
            "variable_schema",
            v as PromptVersionResponse["variable_schema"],
          )
        }
      />
      <FieldJsonEditor
        label="Response schema"
        value={draft.response_schema ?? null}
        onChange={(v) =>
          patchLocal(
            "response_schema",
            v as PromptVersionResponse["response_schema"],
          )
        }
        allowNull
      />

      <FieldTextarea
        label="Changelog"
        value={draft.changelog ?? ""}
        onChange={(v) => patchLocal("changelog", v)}
        rows={3}
        placeholder="Why this change?"
      />

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-xs text-destructive">
          {err}
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-t pt-3">
        <Button variant="outline" onClick={saveDraft} disabled={saving}>
          {saving ? "Saving…" : "Save draft"}
        </Button>
        <Button variant="outline" onClick={() => setPreviewOpen(true)}>
          Preview
        </Button>
        <Button variant="outline" onClick={() => setTestRunOpen(true)}>
          Run test
        </Button>
        <div className="flex-1" />
        <Button onClick={() => setActivateOpen(true)}>Activate</Button>
      </div>

      {/* Modals */}
      <PreviewModal
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        systemPrompt={draft.system_prompt}
        userTemplate={draft.user_template}
        variableSchema={draft.variable_schema}
      />
      <TestRunModal
        open={testRunOpen}
        onOpenChange={setTestRunOpen}
        promptId={prompt.id}
        version={draft}
        modelRoutes={modelRoutes}
      />
      <ActivationDialog
        open={activateOpen}
        onOpenChange={setActivateOpen}
        prompt={prompt}
        draft={draft}
        activeVersion={activeVersion}
        requiresConfirmationText={requiresConfirmationText}
        onActivated={onActivated}
      />

      {/* Discard confirmation */}
      {discardConfirmOpen && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm">
          <p>Discard this draft? This cannot be undone.</p>
          <div className="mt-2 flex gap-2">
            <Button
              variant="destructive"
              size="sm"
              onClick={discardDraft}
            >
              Yes, discard
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDiscardConfirmOpen(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function FieldTextarea({
  label,
  value,
  onChange,
  rows = 4,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  placeholder?: string;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <textarea
        className="w-full rounded-md border border-input bg-background p-2 font-mono text-xs leading-5"
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

function FieldJsonEditor({
  label,
  value,
  onChange,
  allowNull = false,
}: {
  label: string;
  value: unknown;
  onChange: (v: unknown) => void;
  allowNull?: boolean;
}) {
  const [text, setText] = useState(
    value === null || value === undefined
      ? allowNull ? "null" : "{}"
      : JSON.stringify(value, null, 2),
  );
  const [parseErr, setParseErr] = useState<string | null>(null);

  useEffect(() => {
    // Re-sync when the parent replaces the value (e.g. after Save)
    setText(
      value === null || value === undefined
        ? allowNull ? "null" : "{}"
        : JSON.stringify(value, null, 2),
    );
    setParseErr(null);
  }, [value, allowNull]);

  return (
    <label className="block space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        {parseErr && (
          <span className="text-xs text-destructive">{parseErr}</span>
        )}
      </div>
      <textarea
        className={`w-full rounded-md border bg-background p-2 font-mono text-xs leading-5 ${
          parseErr ? "border-destructive" : "border-input"
        }`}
        rows={6}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          try {
            const trimmed = text.trim();
            if (allowNull && (trimmed === "null" || trimmed === "")) {
              onChange(null);
              setParseErr(null);
              return;
            }
            onChange(JSON.parse(trimmed || "{}"));
            setParseErr(null);
          } catch (e) {
            setParseErr(e instanceof Error ? e.message : "Invalid JSON");
          }
        }}
      />
    </label>
  );
}
