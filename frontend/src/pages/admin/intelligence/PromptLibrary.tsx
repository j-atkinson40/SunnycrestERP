import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { intelligenceService } from "@/services/intelligence-service";
import type {
  OverallStatsResponse,
  PromptListItem,
} from "@/types/intelligence";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  formatCost,
  formatLatency,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  formatTotalCost,
} from "@/components/intelligence/formatting";

const PAGE_SIZE = 50;

// Phase 3a-polish: simplified to 3 sort options per spec.
// "volume" is the default — matches the "what's happening right now" use case
// most admins land on first. "updated" surfaces newly-added prompts.
// "alpha" is the deterministic fallback for long scans.
type SortKey = "volume" | "updated" | "alpha";

export default function PromptLibrary() {
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const callerModule = params.get("caller_module") ?? "";
  const modelPreference = params.get("model_preference") ?? "";
  const status = params.get("status") ?? "active";
  const sort = (params.get("sort") as SortKey) ?? "volume";
  const page = Math.max(1, parseInt(params.get("page") ?? "1", 10));

  const [prompts, setPrompts] = useState<PromptListItem[]>([]);
  const [overall, setOverall] = useState<OverallStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [list, stats] = await Promise.all([
        intelligenceService.listPrompts({
          search: search || undefined,
          caller_module: callerModule || undefined,
          model_preference: modelPreference || undefined,
          is_active: status === "active" ? true : undefined,
          limit: 500,
        }),
        intelligenceService.getOverallStats(30),
      ]);
      setPrompts(list);
      setOverall(stats);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [search, callerModule, modelPreference, status]);

  useEffect(() => {
    load();
  }, [load]);

  const modelPrefOptions = useMemo(() => {
    const set = new Set<string>();
    for (const p of prompts) {
      if (p.active_model_preference) set.add(p.active_model_preference);
    }
    return Array.from(set).sort();
  }, [prompts]);

  const callerModuleOptions = useMemo(() => {
    const set = new Set<string>();
    for (const p of prompts) {
      if (p.caller_module) set.add(p.caller_module);
    }
    return Array.from(set).sort();
  }, [prompts]);

  const sorted = useMemo(() => {
    const arr = [...prompts];
    arr.sort((a, b) => {
      switch (sort) {
        case "alpha":
          return a.prompt_key.localeCompare(b.prompt_key);
        case "updated":
          return (
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
          );
        case "volume":
        default:
          return b.executions_30d - a.executions_30d;
      }
    });
    return arr;
  }, [prompts, sort]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageItems = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function updateParam(key: string, value: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      if (key !== "page") next.delete("page");
      return next;
    });
  }

  function resetFilters() {
    setParams({});
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">Prompt Library</h1>
        <p className="text-muted-foreground">
          Managed AI prompts visible to this tenant. Platform-global prompts
          unless overridden.
        </p>
      </div>

      {/* Overall stats — belong above a divider from the filter bar so
          the eye can scan them as a distinct block, then drop into search. */}
      {overall && (
        <section aria-label="Platform stats last 30 days" className="space-y-2">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard
              label="Executions (30d)"
              value={formatNumber(overall.total_executions)}
            />
            <StatCard
              label="Total cost (30d)"
              value={formatTotalCost(overall.total_cost_usd)}
            />
            <StatCard
              label="Error rate"
              value={formatPercent(overall.error_rate)}
              variant={overall.error_rate > 0.05 ? "warn" : "default"}
            />
            <StatCard
              label="Avg latency"
              value={formatLatency(overall.avg_latency_ms)}
            />
          </div>
        </section>
      )}

      {/* Filters — subtle top-border keeps "search/filter controls" visually
          distinct from the stats summary above. */}
      <div className="flex flex-wrap items-center gap-3 border-t pt-4">
        <Input
          className="w-64"
          placeholder="Search key / description"
          value={search}
          onChange={(e) => updateParam("search", e.target.value)}
          data-testid="prompt-search-input"
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={callerModule}
          onChange={(e) => updateParam("caller_module", e.target.value)}
        >
          <option value="">All caller modules</option>
          {callerModuleOptions.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={modelPreference}
          onChange={(e) => updateParam("model_preference", e.target.value)}
        >
          <option value="">All models</option>
          {modelPrefOptions.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={status}
          onChange={(e) => updateParam("status", e.target.value)}
        >
          <option value="active">Active</option>
          <option value="all">All</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={sort}
          onChange={(e) => updateParam("sort", e.target.value)}
          aria-label="Sort prompts"
        >
          <option value="volume">Volume (30d executions)</option>
          <option value="updated">Recently updated</option>
          <option value="alpha">Alphabetical</option>
        </select>
        {(search || callerModule || modelPreference || status !== "active") && (
          <Button variant="ghost" size="sm" onClick={resetFilters}>
            Reset
          </Button>
        )}
      </div>

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
      )}

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Key</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Model</TableHead>
              <TableHead className="text-right">30d execs</TableHead>
              <TableHead className="text-right">Error %</TableHead>
              <TableHead className="text-right">Avg latency</TableHead>
              <TableHead className="text-right">Avg cost</TableHead>
              <TableHead>Updated</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : pageItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="py-6 text-center text-muted-foreground">
                  {search || callerModule || modelPreference || status !== "active" ? (
                    <>
                      No prompts match your filters.{" "}
                      <button
                        className="underline"
                        onClick={resetFilters}
                        type="button"
                      >
                        Reset filters
                      </button>
                    </>
                  ) : (
                    <>
                      No prompts yet. Run{" "}
                      <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                        python scripts/seed_intelligence.py
                      </code>{" "}
                      to seed the platform library.
                    </>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              pageItems.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>
                    <Link
                      to={`/admin/intelligence/prompts/${p.id}`}
                      className="font-mono text-xs underline"
                    >
                      {p.prompt_key}
                    </Link>
                    <div className="mt-0.5 flex gap-1">
                      <Badge variant="outline" className="text-[10px]">
                        {p.domain}
                      </Badge>
                      {p.company_id === null && (
                        <Badge variant="secondary" className="text-[10px]">
                          platform
                        </Badge>
                      )}
                      {p.has_draft && (
                        <Badge
                          className="bg-amber-500/15 text-amber-900 text-[10px] hover:bg-amber-500/20"
                          variant="outline"
                          title="Draft version in progress"
                        >
                          draft
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell
                    className="max-w-[280px] truncate"
                    title={p.description ?? p.display_name}
                  >
                    <span className="font-medium">{p.display_name}</span>
                    {p.description && (
                      <div className="truncate text-xs text-muted-foreground">
                        {p.description}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {p.active_model_preference ?? "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    {formatNumber(p.executions_30d)}
                  </TableCell>
                  <TableCell className="text-right">
                    <span
                      className={
                        p.error_rate_30d > 0.05
                          ? "font-medium text-destructive"
                          : ""
                      }
                    >
                      {formatPercent(p.error_rate_30d)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    {formatLatency(p.avg_latency_ms_30d)}
                  </TableCell>
                  <TableCell className="text-right">
                    {formatCost(p.avg_cost_usd_30d)}
                  </TableCell>
                  <TableCell
                    className="text-xs text-muted-foreground"
                    title={p.updated_at}
                  >
                    {formatRelativeTime(p.updated_at)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <div className="text-muted-foreground">
            Page {page} of {totalPages} · {sorted.length} prompts
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => updateParam("page", String(page - 1))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => updateParam("page", String(page + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      )}
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
