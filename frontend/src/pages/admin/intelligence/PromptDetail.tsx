import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { intelligenceService } from "@/services/intelligence-service";
import type {
  EditPermissionResponse,
  ExecutionListItem,
  ModelRouteResponse,
  PromptDetailResponse,
  PromptStatsResponse,
  PromptVersionResponse,
} from "@/types/intelligence";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pencil } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  formatAbsoluteTime,
  formatCost,
  formatLatency,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  formatTotalCost,
} from "@/components/intelligence/formatting";
import { JsonBlock, MonospaceBlock } from "@/components/intelligence/JsonBlock";
import { DailyChart } from "@/components/intelligence/DailyChart";
import { PromptEditor } from "@/components/intelligence/PromptEditor";
import { RollbackDialog } from "@/components/intelligence/RollbackDialog";
import { AuditLogSection } from "@/components/intelligence/AuditLogSection";
import { CreateExperimentLink } from "@/pages/admin/intelligence/ExperimentLibrary";

/**
 * Build a link to the Execution Log filtered to this prompt over the same
 * 30-day window PromptDetail displays. Threads start_date / end_date as
 * ISO-8601 URL params so totals stay consistent across pages.
 */
function buildExecutionLogLink(promptKey: string, days = 30): string {
  const now = new Date();
  const start = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
  const qs = new URLSearchParams({
    prompt_key: promptKey,
    start_date: start.toISOString(),
    end_date: now.toISOString(),
  });
  return `/vault/intelligence/executions?${qs.toString()}`;
}

export default function PromptDetail() {
  const { promptId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const [prompt, setPrompt] = useState<PromptDetailResponse | null>(null);
  const [stats, setStats] = useState<PromptStatsResponse | null>(null);
  const [recent, setRecent] = useState<ExecutionListItem[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<PromptVersionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // ── Phase 3b — editing state ─────────────────────────────────────────
  const [editPerm, setEditPerm] = useState<EditPermissionResponse | null>(null);
  const [modelRoutes, setModelRoutes] = useState<ModelRouteResponse[]>([]);
  // URL-state: ?edit=1 persists edit mode across reloads
  const editing = params.get("edit") === "1";
  const [rollbackTarget, setRollbackTarget] =
    useState<PromptVersionResponse | null>(null);
  /** Bump to force the audit-log section to refetch after an action. */
  const [auditTick, setAuditTick] = useState(0);

  const load = useCallback(async () => {
    if (!promptId) return;
    setLoading(true);
    setErr(null);
    try {
      const [detail, statsData, recentExecs, perm, routes] = await Promise.all([
        intelligenceService.getPrompt(promptId),
        intelligenceService.getPromptStats(promptId, 30),
        intelligenceService.listExecutions({
          prompt_key: undefined, // can't filter by id; fetch recent for this prompt
          since_days: 30,
          limit: 10,
        }),
        intelligenceService.getEditPermission(promptId),
        intelligenceService.listModelRoutes(),
      ]);
      setPrompt(detail);
      setStats(statsData);
      setRecent(recentExecs.filter((e) => e.prompt_id === promptId).slice(0, 10));
      setEditPerm(perm);
      setModelRoutes(routes);

      // Select: existing draft wins (so edit mode lands on the draft), else
      // the active version, else the highest-numbered version.
      const draft = detail.versions.find((v) => v.status === "draft");
      const active = detail.versions.find((v) => v.status === "active");
      setSelectedVersion(draft ?? active ?? detail.versions[0] ?? null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [promptId]);

  useEffect(() => {
    load();
  }, [load]);

  function setEditing(on: boolean) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (on) {
        next.set("edit", "1");
      } else {
        next.delete("edit");
      }
      return next;
    });
  }

  async function startEditing() {
    if (!prompt || !editPerm?.can_edit) return;
    // If a draft already exists, just enter edit mode on it. Otherwise
    // create one from the current active version.
    const existingDraft = prompt.versions.find((v) => v.status === "draft");
    if (existingDraft) {
      setSelectedVersion(existingDraft);
      setEditing(true);
      toast.info(`Resumed draft v${existingDraft.version_number}`);
      return;
    }
    try {
      await intelligenceService.createDraft(prompt.id, {});
      toast.success("Draft created");
      await load();
      setEditing(true);
    } catch (e) {
      const anyErr = e as { response?: { data?: { detail?: string } } };
      toast.error(
        anyErr.response?.data?.detail ??
          (e instanceof Error ? e.message : String(e)),
      );
    }
  }

  if (loading) {
    return <div className="p-6">Loading…</div>;
  }
  if (err) {
    return (
      <div className="p-6">
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
        <div className="mt-4">
          <Link to="/vault/intelligence/prompts" className="text-sm underline">
            ← Back to Prompt Library
          </Link>
        </div>
      </div>
    );
  }
  if (!prompt) {
    return <div className="p-6">Prompt not found.</div>;
  }

  const activeVersion =
    prompt.versions.find((v) => v.status === "active") ?? null;
  const draftVersion =
    prompt.versions.find((v) => v.status === "draft") ?? null;

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link
          to="/vault/intelligence/prompts"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Prompt Library
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="font-mono text-2xl font-bold">{prompt.prompt_key}</h1>
          <Badge variant="outline">{prompt.domain}</Badge>
          {prompt.company_id === null && <Badge variant="secondary">platform-global</Badge>}
          {!prompt.is_active && <Badge variant="destructive">inactive</Badge>}
        </div>
        <div className="mt-1 text-lg">{prompt.display_name}</div>
        {prompt.description && (
          <p className="mt-1 max-w-3xl text-muted-foreground">
            {prompt.description}
          </p>
        )}
        <div className="mt-2 text-xs text-muted-foreground">
          Created {formatAbsoluteTime(prompt.created_at)} · Updated{" "}
          {formatRelativeTime(prompt.updated_at)} · Caller module:{" "}
          {prompt.caller_module ?? "—"}
        </div>
      </div>

      {/* 30-day stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            label="Executions (30d)"
            value={formatNumber(stats.total_executions)}
          />
          <StatCard
            label="Error rate"
            value={formatPercent(
              stats.total_executions > 0
                ? stats.error_count / stats.total_executions
                : 0
            )}
            variant={
              stats.total_executions > 0 &&
              stats.error_count / stats.total_executions > 0.05
                ? "warn"
                : "default"
            }
          />
          <StatCard label="Avg latency" value={formatLatency(stats.avg_latency_ms)} />
          <StatCard
            label="Total cost (30d)"
            value={formatTotalCost(stats.total_cost_usd)}
          />
        </div>
      )}

      {/* Daily chart */}
      {stats && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Daily activity</h2>
          <DailyChart data={stats.daily_breakdown} />
        </section>
      )}

      {/* Draft indicator — banner when a draft exists but we're not in edit mode */}
      {!editing && draftVersion && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-500/50 bg-amber-500/5 p-3 text-xs">
          <span>
            <strong>Draft v{draftVersion.version_number} in progress</strong>
            {draftVersion.changelog && (
              <span className="text-muted-foreground"> — {draftVersion.changelog}</span>
            )}
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setSelectedVersion(draftVersion);
              setEditing(true);
            }}
          >
            Open draft
          </Button>
        </div>
      )}

      {/* Active / selected version — one focus at a time. Clicking a row in
          Version History below swaps this panel; non-active selections show
          a "Return to active" affordance so it's always one click back.
          Phase 3b: in edit mode, the panel is replaced by the PromptEditor. */}
      {editing && selectedVersion?.status === "draft" ? (
        <PromptEditor
          prompt={prompt}
          draft={selectedVersion}
          activeVersion={activeVersion}
          requiresConfirmationText={editPerm?.requires_confirmation_text ?? false}
          modelRoutes={modelRoutes}
          onSaved={(updated) => {
            // Keep selectedVersion in sync with the draft we just saved
            setSelectedVersion(updated);
            setAuditTick((t) => t + 1);
          }}
          onDiscarded={() => {
            setEditing(false);
            load();
            setAuditTick((t) => t + 1);
          }}
          onActivated={() => {
            setEditing(false);
            toast.success("Version activated");
            load();
            setAuditTick((t) => t + 1);
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="space-y-0.5">
              <h2 className="text-lg font-semibold">
                {selectedVersion?.status === "active"
                  ? "Active Version"
                  : `Viewing version ${selectedVersion?.version_number} (${selectedVersion?.status})`}
              </h2>
              {selectedVersion &&
                selectedVersion.status !== "active" &&
                activeVersion && (
                  <p className="text-xs text-muted-foreground">
                    Active version is v{activeVersion.version_number}.{" "}
                    <button
                      type="button"
                      className="underline hover:text-foreground"
                      onClick={() => setSelectedVersion(activeVersion)}
                    >
                      Return to active version
                    </button>
                  </p>
                )}
            </div>
            <div className="flex items-center gap-2">
              {prompt.versions.length > 1 && (
                <select
                  className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={selectedVersion?.id ?? ""}
                  onChange={(e) => {
                    const v = prompt.versions.find((x) => x.id === e.target.value);
                    if (v) setSelectedVersion(v);
                  }}
                  aria-label="Select version"
                >
                  {prompt.versions.map((v) => (
                    <option key={v.id} value={v.id}>
                      v{v.version_number} — {v.status}
                    </option>
                  ))}
                </select>
              )}
              <Button
                size="sm"
                onClick={startEditing}
                disabled={!editPerm?.can_edit}
                title={
                  editPerm?.can_edit
                    ? undefined
                    : editPerm?.reason ??
                      "You don't have permission to edit this prompt."
                }
              >
                <Pencil className="mr-1 h-3.5 w-3.5" />
                {draftVersion ? "Open draft" : "Edit"}
              </Button>
            </div>
          </div>

          {selectedVersion ? (
            <VersionContent version={selectedVersion} />
          ) : (
            <p className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
              This prompt has no versions — a data integrity issue. The prompt
              row exists but nothing was ever written to{" "}
              <code>intelligence_prompt_versions</code>. Re-run{" "}
              <code>seed_intelligence.py</code> or create a version from the
              admin tools.
            </p>
          )}
        </section>
      )}

      {/* Version history */}
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Version History</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Version</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Activated</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Changelog</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {prompt.versions.map((v) => (
                <TableRow
                  key={v.id}
                  className={
                    selectedVersion?.id === v.id
                      ? "bg-muted/40"
                      : "cursor-pointer hover:bg-muted/20"
                  }
                  onClick={() => setSelectedVersion(v)}
                >
                  <TableCell className="font-mono">v{v.version_number}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        v.status === "active"
                          ? "default"
                          : v.status === "draft"
                          ? "outline"
                          : "secondary"
                      }
                    >
                      {v.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {v.model_preference}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {v.activated_at ? formatRelativeTime(v.activated_at) : "—"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatRelativeTime(v.created_at)}
                  </TableCell>
                  <TableCell
                    className="max-w-[320px] truncate text-xs"
                    title={v.changelog ?? ""}
                  >
                    {v.changelog ?? "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {v.status === "retired" && editPerm?.can_edit && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            setRollbackTarget(v);
                          }}
                        >
                          Roll back
                        </Button>
                      )}
                      {/* Phase 3c — shortcut to create an experiment with
                          this version as variant B. Only makes sense for
                          non-active versions (active becomes variant A by
                          default). */}
                      {v.status !== "active" && editPerm?.can_edit && (
                        <CreateExperimentLink
                          promptId={prompt.id}
                          versionId={v.id}
                          label="A/B test"
                        />
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      {rollbackTarget && (
        <RollbackDialog
          open={!!rollbackTarget}
          onOpenChange={(open) => {
            if (!open) setRollbackTarget(null);
          }}
          prompt={prompt}
          target={rollbackTarget}
          activeVersion={activeVersion}
          requiresConfirmationText={
            editPerm?.requires_confirmation_text ?? false
          }
          onRolledBack={() => {
            setRollbackTarget(null);
            toast.success("Rolled back");
            load();
            setAuditTick((t) => t + 1);
          }}
        />
      )}

      {/* Recent executions */}
      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent Executions</h2>
          <Link
            to={buildExecutionLogLink(prompt.prompt_key)}
            className="text-sm underline"
          >
            View all in last 30 days →
          </Link>
        </div>
        {recent.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No recent executions for this prompt.
          </p>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Caller</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead className="text-right">Latency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recent.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>
                      <Link
                        to={`/vault/intelligence/executions/${e.id}`}
                        className="text-xs underline"
                        title={e.created_at}
                      >
                        {formatRelativeTime(e.created_at)}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={e.status === "success" ? "default" : "destructive"}
                      >
                        {e.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {e.model_used ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {e.caller_module ?? "—"}
                    </TableCell>
                    <TableCell className="text-right text-xs">
                      {formatNumber(e.input_tokens)} / {formatNumber(e.output_tokens)}
                    </TableCell>
                    <TableCell className="text-right text-xs">
                      {formatCost(e.cost_usd)}
                    </TableCell>
                    <TableCell className="text-right text-xs">
                      {formatLatency(e.latency_ms)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      {/* Audit tab — every state transition written here. Less prominent
          than Active Version / Version History by spec. */}
      <AuditLogSection promptId={prompt.id} refreshToken={auditTick} />
    </div>
  );
}

function VersionContent({ version }: { version: PromptVersionResponse }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        <MetaBox label="Model" value={version.model_preference} mono />
        <MetaBox label="Max tokens" value={String(version.max_tokens)} />
        <MetaBox label="Temperature" value={version.temperature.toFixed(2)} />
        <MetaBox label="Force JSON" value={version.force_json ? "Yes" : "No"} />
        <MetaBox
          label="Vision"
          value={
            version.supports_vision
              ? version.vision_content_type ?? "yes"
              : "no"
          }
        />
        <MetaBox
          label="Streaming / Tool use"
          value={`${version.supports_streaming ? "s" : "—"} / ${
            version.supports_tool_use ? "t" : "—"
          }`}
        />
      </div>

      <MonospaceBlock content={version.system_prompt} label="System prompt" />
      <MonospaceBlock content={version.user_template} label="User template" />

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <JsonBlock
          data={version.variable_schema}
          label="Variable schema"
          collapsible
        />
        <JsonBlock
          data={version.response_schema}
          label="Response schema"
          collapsible
        />
      </div>

      {version.changelog && (
        <MonospaceBlock content={version.changelog} label="Changelog" maxHeight={120} />
      )}
    </div>
  );
}

function MetaBox({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={`text-sm ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}

function StatCard({
  label,
  value,
  variant = "default",
}: {
  label: string;
  value: string;
  variant?: "default" | "warn";
}) {
  return (
    <div
      className={`rounded-md border bg-card p-4 ${
        variant === "warn" ? "border-destructive/50" : ""
      }`}
    >
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={`mt-1 text-2xl font-semibold ${
          variant === "warn" ? "text-destructive" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}
