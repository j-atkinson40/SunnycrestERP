import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { intelligenceService } from "@/services/intelligence-service";
import type { ExperimentListItem } from "@/types/intelligence";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  formatNumber,
  formatRelativeTime,
} from "@/components/intelligence/formatting";

function isRunning(status: string): boolean {
  return status === "running" || status === "active";
}

function daysRunning(startedAt: string | null, endedAt: string | null): number {
  if (!startedAt) return 0;
  const start = new Date(startedAt).getTime();
  const end = endedAt ? new Date(endedAt).getTime() : Date.now();
  return Math.max(0, Math.floor((end - start) / (1000 * 60 * 60 * 24)));
}

export default function ExperimentLibrary() {
  const [params, setParams] = useSearchParams();
  const statusFilter = params.get("status") ?? "all";

  const [items, setItems] = useState<ExperimentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const rows = await intelligenceService.listExperiments({
        status: statusFilter === "all" ? "all" : (statusFilter as "running" | "completed" | "draft"),
        limit: 200,
      });
      setItems(rows);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const summary = useMemo(() => {
    const active = items.filter((e) => isRunning(e.status)).length;
    const nowMonth = new Date().getMonth();
    const nowYear = new Date().getFullYear();
    const completedThisMonth = items.filter((e) => {
      if (e.status !== "completed" || !e.concluded_at) return false;
      const d = new Date(e.concluded_at);
      return d.getMonth() === nowMonth && d.getFullYear() === nowYear;
    }).length;
    return { active, completedThisMonth };
  }, [items]);

  function setStatusFilter(v: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v === "all") {
        next.delete("status");
      } else {
        next.set("status", v);
      }
      return next;
    });
  }

  return (
    <div className="space-y-6 p-6" data-testid="experiment-library">
      <div>
        <Link
          to="/vault/intelligence/prompts"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Prompt Library
        </Link>
        <h1 className="mt-1 text-3xl font-bold">Experiments</h1>
        <p className="text-muted-foreground">
          A/B tests across prompt versions. Traffic splits deterministically
          by input hash — same input always lands on the same variant.
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <SummaryCard label="Active experiments" value={summary.active} />
        <SummaryCard
          label="Completed this month"
          value={summary.completedThisMonth}
        />
        <SummaryCard label="Total tracked" value={items.length} />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          data-testid="experiment-status-filter"
        >
          <option value="all">All statuses</option>
          <option value="running">Running</option>
          <option value="draft">Draft</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
      )}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Prompt</TableHead>
              <TableHead>Variants (A / B)</TableHead>
              <TableHead>Traffic split</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Execs (A / B)</TableHead>
              <TableHead>Days running</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="py-6 text-center text-muted-foreground"
                >
                  No experiments yet. Create one from a prompt's version
                  history.
                </TableCell>
              </TableRow>
            ) : (
              items.map((e) => (
                <TableRow key={e.id} data-testid="experiment-row">
                  <TableCell>
                    <Link
                      to={`/vault/intelligence/experiments/${e.id}`}
                      className="font-medium underline"
                    >
                      {e.name}
                    </Link>
                    {e.hypothesis && (
                      <div
                        className="mt-0.5 truncate text-xs text-muted-foreground"
                        title={e.hypothesis}
                      >
                        {e.hypothesis}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {e.prompt_key ? (
                      <Link
                        to={`/vault/intelligence/prompts/${e.prompt_id}`}
                        className="underline"
                      >
                        {e.prompt_key}
                      </Link>
                    ) : (
                      e.prompt_id.slice(0, 8)
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    v{e.version_a_number ?? "?"} / v{e.version_b_number ?? "?"}
                  </TableCell>
                  <TableCell className="text-xs">
                    {100 - e.traffic_split}% / {e.traffic_split}%
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        isRunning(e.status)
                          ? "default"
                          : e.status === "draft"
                          ? "outline"
                          : "secondary"
                      }
                    >
                      {isRunning(e.status) ? "running" : e.status}
                    </Badge>
                    {e.status === "completed" && e.winner_version_id && (
                      <div className="mt-0.5 text-[10px] text-muted-foreground">
                        winner:{" "}
                        {e.winner_version_id === e.version_a_id ? "A" : "B"}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs">
                    {formatNumber(e.variant_a_count)} /{" "}
                    {formatNumber(e.variant_b_count)}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {e.started_at
                      ? `${daysRunning(e.started_at, e.concluded_at)}d`
                      : "—"}
                    {e.started_at && (
                      <div
                        className="text-[10px]"
                        title={e.started_at}
                      >
                        started {formatRelativeTime(e.started_at)}
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {items.length > 0 && (
        <div className="text-xs text-muted-foreground">
          Showing {items.length} experiment{items.length !== 1 ? "s" : ""}.
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border bg-card p-4">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}

/** Reusable "Create experiment" link — also used from PromptDetail. */
export function CreateExperimentLink({
  promptId,
  versionId,
  label = "Create experiment",
  className = "",
}: {
  promptId: string;
  versionId?: string;
  label?: string;
  className?: string;
}) {
  const qs = new URLSearchParams();
  qs.set("prompt_id", promptId);
  if (versionId) qs.set("variant_b_version_id", versionId);
  return (
    <Link
      to={`/vault/intelligence/experiments/new?${qs.toString()}`}
      className={
        className ||
        "inline-flex h-7 items-center rounded-md border border-input bg-background px-2 text-xs hover:bg-accent"
      }
      data-testid="create-experiment-link"
    >
      {label}
    </Link>
  );
}
