import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { intelligenceService } from "@/services/intelligence-service";
import type {
  EditPermissionResponse,
  PromptDetailResponse,
  PromptListItem,
} from "@/types/intelligence";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Create a new experiment.
 *
 * Entry points:
 *   1. Query string ?prompt_id=…&variant_b_version_id=… (from PromptDetail
 *      version-history action) — prefills the form.
 *   2. No params — renders full prompt picker.
 */
export default function CreateExperiment() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const preselectedPromptId = params.get("prompt_id") ?? "";
  const preselectedVariantB = params.get("variant_b_version_id") ?? "";

  const [prompts, setPrompts] = useState<PromptListItem[]>([]);
  const [promptId, setPromptId] = useState(preselectedPromptId);
  const [promptDetail, setPromptDetail] = useState<PromptDetailResponse | null>(
    null,
  );
  const [editPerm, setEditPerm] = useState<EditPermissionResponse | null>(null);

  const [variantAId, setVariantAId] = useState("");
  const [variantBId, setVariantBId] = useState(preselectedVariantB);
  const [name, setName] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [trafficSplit, setTrafficSplit] = useState(50);
  const [minSampleSize, setMinSampleSize] = useState(100);

  const [loadingPrompts, setLoadingPrompts] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    intelligenceService
      .listPrompts({ limit: 500 })
      .then(setPrompts)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoadingPrompts(false));
  }, []);

  // Load prompt detail + edit permission whenever the picker changes
  const loadPrompt = useCallback(async (id: string) => {
    if (!id) {
      setPromptDetail(null);
      setEditPerm(null);
      return;
    }
    try {
      const [d, perm] = await Promise.all([
        intelligenceService.getPrompt(id),
        intelligenceService.getEditPermission(id),
      ]);
      setPromptDetail(d);
      setEditPerm(perm);
      // Prefill variant A = active, variant B = preselected or most recent
      // non-active
      const active = d.versions.find((v) => v.status === "active");
      setVariantAId(active?.id ?? "");
      if (!preselectedVariantB) {
        const nonActive = d.versions
          .filter((v) => v.id !== active?.id)
          .sort((a, b) => b.version_number - a.version_number);
        setVariantBId(nonActive[0]?.id ?? "");
      }
      // Default name
      if (!name && active) {
        setName(`${d.prompt_key} — v${active.version_number} vs …`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preselectedVariantB, name]);

  useEffect(() => {
    if (promptId) {
      loadPrompt(promptId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promptId]);

  async function handleSubmit(startImmediately: boolean) {
    setErr(null);
    if (!promptId || !variantAId || !variantBId) {
      setErr("Pick a prompt and both variants.");
      return;
    }
    if (variantAId === variantBId) {
      setErr("Variants A and B must be different versions.");
      return;
    }
    if (!name.trim()) {
      setErr("Name the experiment.");
      return;
    }
    setSubmitting(true);
    try {
      const exp = await intelligenceService.createExperiment({
        prompt_id: promptId,
        name: name.trim(),
        hypothesis: hypothesis.trim() || undefined,
        version_a_id: variantAId,
        version_b_id: variantBId,
        traffic_split: trafficSplit,
        min_sample_size: minSampleSize,
        start_immediately: startImmediately,
      });
      toast.success(
        startImmediately ? "Experiment started" : "Draft experiment created",
      );
      navigate(`/vault/intelligence/experiments/${exp.id}`);
    } catch (e) {
      const anyErr = e as { response?: { data?: { detail?: unknown } } };
      const d = anyErr.response?.data?.detail;
      setErr(
        typeof d === "string"
          ? d
          : d
          ? JSON.stringify(d)
          : e instanceof Error
          ? e.message
          : String(e),
      );
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    !!promptId &&
    !!variantAId &&
    !!variantBId &&
    variantAId !== variantBId &&
    !!name.trim() &&
    editPerm?.can_edit === true &&
    !submitting;

  return (
    <div className="space-y-6 p-6" data-testid="create-experiment">
      <div>
        <Link
          to="/vault/intelligence/experiments"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Experiments
        </Link>
        <h1 className="mt-1 text-3xl font-bold">New experiment</h1>
        <p className="text-muted-foreground">
          A/B test a candidate version against the current active version of
          a prompt. Traffic splits deterministically by input hash.
        </p>
      </div>

      {editPerm && !editPerm.can_edit && (
        <div className="rounded-md border border-destructive/50 bg-destructive/5 p-3 text-sm text-destructive">
          {editPerm.reason ?? "You cannot create experiments on this prompt."}
        </div>
      )}

      <div className="space-y-4 rounded-md border p-4">
        <label className="block space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Prompt
          </span>
          <select
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            value={promptId}
            onChange={(e) => setPromptId(e.target.value)}
            data-testid="experiment-prompt-picker"
          >
            <option value="">
              {loadingPrompts ? "Loading prompts…" : "Pick a prompt…"}
            </option>
            {prompts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.prompt_key} {p.company_id === null ? "(platform)" : ""}
              </option>
            ))}
          </select>
        </label>

        {promptDetail && (
          <div className="grid grid-cols-2 gap-3">
            <label className="block space-y-1">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Variant A (defaults to active)
              </span>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={variantAId}
                onChange={(e) => setVariantAId(e.target.value)}
                data-testid="experiment-variant-a-picker"
              >
                <option value="">Pick variant A…</option>
                {promptDetail.versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} — {v.status}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Variant B
              </span>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={variantBId}
                onChange={(e) => setVariantBId(e.target.value)}
                data-testid="experiment-variant-b-picker"
              >
                <option value="">Pick variant B…</option>
                {promptDetail.versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} — {v.status}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        <label className="block space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Name <span className="text-destructive">*</span>
          </span>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="v3 vs v4 — reduce hallucination"
          />
        </label>

        <label className="block space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Hypothesis (optional)
          </span>
          <textarea
            className="h-16 w-full rounded-md border border-input bg-transparent p-2 text-sm"
            value={hypothesis}
            onChange={(e) => setHypothesis(e.target.value)}
            placeholder="Expected outcome and how you'll evaluate the variants."
          />
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block space-y-1">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Traffic to variant B: {trafficSplit}%
            </span>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={trafficSplit}
              onChange={(e) => setTrafficSplit(parseInt(e.target.value, 10))}
              className="w-full"
            />
            <div className="text-[10px] text-muted-foreground">
              A: {100 - trafficSplit}% · B: {trafficSplit}%
            </div>
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Min sample size per variant
            </span>
            <Input
              type="number"
              value={minSampleSize}
              onChange={(e) =>
                setMinSampleSize(parseInt(e.target.value, 10) || 0)
              }
            />
          </label>
        </div>

        {err && (
          <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
            {err}
          </div>
        )}

        <div className="flex justify-end gap-2 border-t pt-3">
          <Button
            variant="outline"
            disabled={!canSubmit}
            onClick={() => handleSubmit(false)}
            data-testid="create-as-draft-button"
          >
            Create as draft
          </Button>
          <Button
            disabled={!canSubmit}
            onClick={() => handleSubmit(true)}
            data-testid="create-and-start-button"
          >
            Create and start
          </Button>
        </div>
      </div>
    </div>
  );
}
