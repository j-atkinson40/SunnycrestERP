import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { intelligenceService } from "@/services/intelligence-service";
import type {
  EditPermissionResponse,
  ExperimentResponse,
  ExperimentResultsResponse,
  ExperimentVariantStats,
  PromptDetailResponse,
  PromptVersionResponse,
} from "@/types/intelligence";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  formatAbsoluteTime,
  formatCost,
  formatLatency,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  formatTotalCost,
} from "@/components/intelligence/formatting";
import { AlertTriangle } from "lucide-react";

const MIN_SAMPLE_FOR_CONFIDENCE = 100;

function isRunning(status: string): boolean {
  return status === "running" || status === "active";
}

export default function ExperimentDetail() {
  const { experimentId = "" } = useParams();
  const navigate = useNavigate();

  const [exp, setExp] = useState<ExperimentResponse | null>(null);
  const [results, setResults] = useState<ExperimentResultsResponse | null>(null);
  const [prompt, setPrompt] = useState<PromptDetailResponse | null>(null);
  const [editPerm, setEditPerm] = useState<EditPermissionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [stopOpen, setStopOpen] = useState(false);
  const [promoteTarget, setPromoteTarget] =
    useState<"a" | "b" | null>(null);

  const load = useCallback(async () => {
    if (!experimentId) return;
    setLoading(true);
    setErr(null);
    try {
      const e = await intelligenceService.getExperiment(experimentId);
      const [r, p, perm] = await Promise.all([
        intelligenceService.getExperimentResults(experimentId),
        intelligenceService.getPrompt(e.prompt_id),
        intelligenceService.getEditPermission(e.prompt_id),
      ]);
      setExp(e);
      setResults(r);
      setPrompt(p);
      setEditPerm(perm);
    } catch (err) {
      setErr(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [experimentId]);

  useEffect(() => {
    load();
  }, [load]);

  const variantA = useMemo(
    () => results?.variants.find((v) => v.variant === "a") ?? null,
    [results],
  );
  const variantB = useMemo(
    () => results?.variants.find((v) => v.variant === "b") ?? null,
    [results],
  );

  const lowSample =
    !!variantA &&
    !!variantB &&
    (variantA.sample_count < MIN_SAMPLE_FOR_CONFIDENCE ||
      variantB.sample_count < MIN_SAMPLE_FOR_CONFIDENCE);

  if (loading) return <div className="p-6">Loading…</div>;
  if (err) {
    return (
      <div className="p-6">
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
      </div>
    );
  }
  if (!exp || !prompt) return <div className="p-6">Experiment not found.</div>;

  const versionA = prompt.versions.find((v) => v.id === exp.version_a_id) ?? null;
  const versionB = prompt.versions.find((v) => v.id === exp.version_b_id) ?? null;
  const canEdit = editPerm?.can_edit ?? false;

  async function handleStart() {
    try {
      await intelligenceService.startExperiment(experimentId);
      toast.success("Experiment started");
      await load();
    } catch (e) {
      toast.error(errorDetail(e));
    }
  }

  return (
    <div className="space-y-6 p-6" data-testid="experiment-detail">
      <div>
        <Link
          to="/vault/intelligence/experiments"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Experiments
        </Link>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-3xl font-bold">{exp.name}</h1>
            {exp.hypothesis && (
              <p className="mt-1 max-w-3xl text-muted-foreground">
                {exp.hypothesis}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant={
                isRunning(exp.status)
                  ? "default"
                  : exp.status === "draft"
                  ? "outline"
                  : "secondary"
              }
            >
              {isRunning(exp.status) ? "running" : exp.status}
            </Badge>
            {exp.status === "draft" && canEdit && (
              <Button
                size="sm"
                onClick={handleStart}
                data-testid="experiment-start-button"
              >
                Start
              </Button>
            )}
            {isRunning(exp.status) && canEdit && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setStopOpen(true)}
                data-testid="experiment-stop-button"
              >
                Stop
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Summary grid */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <MetaBox
          label="Prompt"
          value={
            <Link
              to={`/vault/intelligence/prompts/${exp.prompt_id}`}
              className="font-mono text-sm underline"
            >
              {prompt.prompt_key}
            </Link>
          }
        />
        <MetaBox
          label="Variant A"
          value={<span className="font-mono">v{versionA?.version_number}</span>}
        />
        <MetaBox
          label="Variant B"
          value={<span className="font-mono">v{versionB?.version_number}</span>}
        />
        <MetaBox
          label="Traffic split"
          value={`${100 - exp.traffic_split}% / ${exp.traffic_split}%`}
        />
        <MetaBox
          label="Started"
          value={
            exp.started_at ? formatRelativeTime(exp.started_at) : "—"
          }
        />
        <MetaBox
          label="Ended"
          value={
            exp.concluded_at ? formatRelativeTime(exp.concluded_at) : "—"
          }
        />
      </div>

      {lowSample && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/60 bg-amber-500/5 p-3 text-xs">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" />
          <span>
            <strong>Low sample size.</strong> Each variant should reach at
            least {MIN_SAMPLE_FOR_CONFIDENCE} executions before drawing
            conclusions. Current: A = {variantA?.sample_count ?? 0}, B ={" "}
            {variantB?.sample_count ?? 0}.
          </span>
        </div>
      )}

      {/* Results side-by-side */}
      {variantA && variantB && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Results</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <VariantCard
              label="Variant A"
              version={versionA}
              stats={variantA}
              p95={results?.p95_latency_ms.a ?? null}
              highlight={
                variantA.success_rate > variantB.success_rate ? "better" : undefined
              }
            />
            <VariantCard
              label="Variant B"
              version={versionB}
              stats={variantB}
              p95={results?.p95_latency_ms.b ?? null}
              highlight={
                variantB.success_rate > variantA.success_rate ? "better" : undefined
              }
            />
          </div>
        </section>
      )}

      {/* Daily breakdown */}
      {results && results.daily_breakdown.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Daily execution counts</h2>
          <DailyVariantChart data={results.daily_breakdown} />
        </section>
      )}

      {/* Promote */}
      {isRunning(exp.status) && canEdit && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Promote winner</h2>
          <p className="text-sm text-muted-foreground">
            Ends the experiment and makes the chosen variant the new active
            version of this prompt.
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setPromoteTarget("a")}
              data-testid="promote-a-button"
            >
              Promote variant A (v{versionA?.version_number})
            </Button>
            <Button
              variant="outline"
              onClick={() => setPromoteTarget("b")}
              data-testid="promote-b-button"
            >
              Promote variant B (v{versionB?.version_number})
            </Button>
          </div>
        </section>
      )}

      {/* Outcome banner for completed */}
      {exp.status === "completed" && (
        <section className="rounded-md border bg-muted/20 p-3 text-sm">
          <div className="font-medium">Completed {exp.concluded_at && formatAbsoluteTime(exp.concluded_at)}</div>
          {exp.winner_version_id ? (
            <div className="text-muted-foreground">
              Winner: variant{" "}
              {exp.winner_version_id === exp.version_a_id ? "A" : "B"} (
              v
              {exp.winner_version_id === exp.version_a_id
                ? versionA?.version_number
                : versionB?.version_number}
              ). Activated as new version.
            </div>
          ) : (
            <div className="text-muted-foreground">
              Stopped without picking a winner.
              {exp.conclusion_notes && (
                <span> Reason: {exp.conclusion_notes}</span>
              )}
            </div>
          )}
        </section>
      )}

      {/* Stop dialog */}
      <StopDialog
        open={stopOpen}
        onOpenChange={setStopOpen}
        experimentName={exp.name}
        onStop={async (reason) => {
          try {
            await intelligenceService.stopExperiment(experimentId, { reason });
            toast.success("Experiment stopped");
            setStopOpen(false);
            await load();
          } catch (e) {
            toast.error(errorDetail(e));
          }
        }}
      />

      {/* Promote dialog */}
      {promoteTarget && (
        <PromoteDialog
          open={!!promoteTarget}
          onOpenChange={(open) => {
            if (!open) setPromoteTarget(null);
          }}
          prompt={prompt}
          targetVariant={promoteTarget}
          versionA={versionA}
          versionB={versionB}
          requiresConfirmationText={
            editPerm?.requires_confirmation_text ?? false
          }
          onPromoted={async () => {
            toast.success("Variant promoted");
            setPromoteTarget(null);
            // Navigate back to prompt detail so the new active version is in
            // view immediately
            navigate(`/vault/intelligence/prompts/${exp.prompt_id}`);
          }}
          experimentId={experimentId}
        />
      )}
    </div>
  );
}

function errorDetail(e: unknown): string {
  const anyErr = e as { response?: { data?: { detail?: unknown } } };
  const d = anyErr.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d) return JSON.stringify(d);
  return e instanceof Error ? e.message : String(e);
}

function MetaBox({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="truncate text-sm">{value}</div>
    </div>
  );
}

function VariantCard({
  label,
  version,
  stats,
  p95,
  highlight,
}: {
  label: string;
  version: PromptVersionResponse | null;
  stats: ExperimentVariantStats;
  p95: number | null;
  highlight?: "better" | "worse";
}) {
  return (
    <div
      className={`rounded-md border bg-card p-4 ${
        highlight === "better" ? "border-primary/60" : ""
      }`}
    >
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{label}</h3>
        <span className="font-mono text-xs text-muted-foreground">
          v{version?.version_number} · {version?.model_preference}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Executions</dt>
        <dd className="text-right font-medium">
          {formatNumber(stats.sample_count)}
        </dd>

        <dt className="text-muted-foreground">Success rate</dt>
        <dd className="text-right font-medium">
          {formatPercent(stats.success_rate)}{" "}
          {stats.error_count > 0 && (
            <span className="text-xs text-muted-foreground">
              ({stats.error_count} err)
            </span>
          )}
        </dd>

        <dt className="text-muted-foreground">Avg latency</dt>
        <dd className="text-right">{formatLatency(stats.avg_latency_ms)}</dd>

        <dt className="text-muted-foreground">p95 latency</dt>
        <dd className="text-right">{formatLatency(p95)}</dd>

        <dt className="text-muted-foreground">Avg cost / exec</dt>
        <dd className="text-right">
          {formatCost(
            stats.sample_count > 0
              ? parseFloat(stats.total_cost_usd) / stats.sample_count
              : 0,
          )}
        </dd>

        <dt className="text-muted-foreground">Total cost</dt>
        <dd className="text-right">{formatTotalCost(stats.total_cost_usd)}</dd>

        <dt className="text-muted-foreground">Avg tokens (in / out)</dt>
        <dd className="text-right text-xs">
          {stats.avg_input_tokens !== null
            ? Math.round(stats.avg_input_tokens)
            : "—"}{" "}
          /{" "}
          {stats.avg_output_tokens !== null
            ? Math.round(stats.avg_output_tokens)
            : "—"}
        </dd>
      </dl>
    </div>
  );
}

function DailyVariantChart({
  data,
}: {
  data: {
    date: string;
    variant_a_count: number;
    variant_b_count: number;
  }[];
}) {
  const maxCount = Math.max(
    ...data.map((d) => d.variant_a_count + d.variant_b_count),
    1,
  );
  return (
    <div className="space-y-2">
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="w-full rounded-md border bg-card"
        style={{ height: 140 }}
      >
        {data.map((d, i) => {
          const x = (i * 100) / data.length;
          const w = 100 / data.length;
          const aHeight = (d.variant_a_count / maxCount) * 100;
          const bHeight = (d.variant_b_count / maxCount) * 100;
          return (
            <g key={d.date}>
              <rect
                x={x + 0.2}
                y={100 - aHeight}
                width={w / 2 - 0.3}
                height={aHeight}
                fill="currentColor"
                className="text-primary/70"
              >
                <title>
                  {d.date}: A = {d.variant_a_count}, B = {d.variant_b_count}
                </title>
              </rect>
              <rect
                x={x + w / 2 + 0.1}
                y={100 - bHeight}
                width={w / 2 - 0.3}
                height={bHeight}
                fill="currentColor"
                className="text-amber-500/80"
              >
                <title>
                  {d.date}: A = {d.variant_a_count}, B = {d.variant_b_count}
                </title>
              </rect>
            </g>
          );
        })}
      </svg>
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-3 rounded-sm bg-primary/70" />
          Variant A
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-3 rounded-sm bg-amber-500/80" />
          Variant B
        </span>
      </div>
    </div>
  );
}

function StopDialog({
  open,
  onOpenChange,
  experimentName,
  onStop,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  experimentName: string;
  onStop: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Stop "{experimentName}"?</DialogTitle>
          <DialogDescription>
            Stops traffic-splitting immediately. No winner is picked — the
            prompt's current active version continues to serve traffic.
          </DialogDescription>
        </DialogHeader>
        <label className="block space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Reason
          </span>
          <textarea
            className="h-20 w-full rounded-md border border-input bg-transparent p-2 text-sm"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why are you stopping this experiment?"
          />
        </label>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={submitting}
            onClick={async () => {
              setSubmitting(true);
              await onStop(reason);
              setSubmitting(false);
            }}
          >
            {submitting ? "Stopping…" : "Stop experiment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PromoteDialog({
  open,
  onOpenChange,
  prompt,
  targetVariant,
  versionA,
  versionB,
  requiresConfirmationText,
  experimentId,
  onPromoted,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prompt: PromptDetailResponse;
  targetVariant: "a" | "b";
  versionA: PromptVersionResponse | null;
  versionB: PromptVersionResponse | null;
  requiresConfirmationText: boolean;
  experimentId: string;
  onPromoted: () => Promise<void> | void;
}) {
  const chosen = targetVariant === "a" ? versionA : versionB;
  const [changelog, setChangelog] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const confirmationOk =
    !requiresConfirmationText || confirmation.trim() === prompt.prompt_key;
  const changelogOk = changelog.trim().length > 0;
  const canSubmit = !!chosen && confirmationOk && changelogOk && !submitting;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            Promote variant {targetVariant.toUpperCase()} of{" "}
            <code className="font-mono">{prompt.prompt_key}</code>?
          </DialogTitle>
          <DialogDescription>
            Ends the experiment and activates v{chosen?.version_number} as
            the new active version. The current active version (if any) is
            retired.
          </DialogDescription>
        </DialogHeader>

        {prompt.company_id === null && (
          <div className="rounded-md border border-amber-500/60 bg-amber-500/5 p-3 text-xs">
            <div className="flex items-center gap-2 font-medium">
              <AlertTriangle className="h-4 w-4" />
              Platform-global prompt — change affects every tenant.
            </div>
          </div>
        )}

        <label className="block space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Changelog <span className="text-destructive">*</span>
          </span>
          <textarea
            className="h-20 w-full rounded-md border border-input bg-transparent p-2 text-sm"
            value={changelog}
            onChange={(e) => setChangelog(e.target.value)}
            placeholder="Why promote this variant?"
          />
        </label>

        {requiresConfirmationText && (
          <label className="block space-y-1">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Confirm — type <code>{prompt.prompt_key}</code>
            </span>
            <Input
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
              autoComplete="off"
            />
          </label>
        )}

        {err && (
          <pre className="max-h-40 overflow-auto rounded-md border border-destructive bg-destructive/10 p-3 font-mono text-xs text-destructive">
            {err}
          </pre>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={!canSubmit}
            data-testid="promote-confirm-button"
            onClick={async () => {
              if (!chosen) return;
              setSubmitting(true);
              setErr(null);
              try {
                await intelligenceService.promoteExperiment(experimentId, {
                  variant_version_id: chosen.id,
                  changelog: changelog.trim(),
                  confirmation_text: requiresConfirmationText
                    ? confirmation
                    : undefined,
                });
                await onPromoted();
              } catch (e) {
                setErr(errorDetail(e));
              } finally {
                setSubmitting(false);
              }
            }}
          >
            {submitting ? "Promoting…" : "Promote"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
