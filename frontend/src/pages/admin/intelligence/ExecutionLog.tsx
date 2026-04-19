import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { intelligenceService } from "@/services/intelligence-service";
import type {
  CallerModuleOption,
  ExecutionListItem,
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
  formatRelativeTime,
} from "@/components/intelligence/formatting";

const PAGE_SIZE = 50;
type SortKey = "created_desc" | "created_asc" | "cost_desc" | "latency_desc" | "tokens_desc";

export default function ExecutionLog() {
  const [params, setParams] = useSearchParams();
  const promptKey = params.get("prompt_key") ?? "";
  const callerModule = params.get("caller_module") ?? "";
  const company = params.get("company_id") ?? "";
  const statusFilter = params.get("status") ?? "";
  // Date range — explicit start/end wins over since_days. Phase 3a-polish:
  // links from PromptDetail pass a 30-day window so totals stay consistent.
  const startDate = params.get("start_date") ?? "";
  const endDate = params.get("end_date") ?? "";
  const hasExplicitRange = Boolean(startDate || endDate);
  const sinceDays = parseInt(params.get("since_days") ?? "7", 10);
  const sort = (params.get("sort") as SortKey) ?? "created_desc";
  const page = Math.max(1, parseInt(params.get("page") ?? "1", 10));

  const [executions, setExecutions] = useState<ExecutionListItem[]>([]);
  const [callerModules, setCallerModules] = useState<CallerModuleOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const offset = (page - 1) * PAGE_SIZE;
      const rows = await intelligenceService.listExecutions({
        prompt_key: promptKey || undefined,
        caller_module: callerModule || undefined,
        company_id: company || undefined,
        status: statusFilter || undefined,
        // If an explicit range is in the URL, pass it and skip since_days
        // (the backend's docstring: explicit dates take precedence).
        start_date: hasExplicitRange ? startDate || undefined : undefined,
        end_date: hasExplicitRange ? endDate || undefined : undefined,
        since_days: hasExplicitRange ? undefined : sinceDays,
        sort,
        limit: PAGE_SIZE + 1, // over-fetch to detect more
        offset,
      });
      setHasMore(rows.length > PAGE_SIZE);
      setExecutions(rows.slice(0, PAGE_SIZE));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [
    promptKey,
    callerModule,
    company,
    statusFilter,
    sinceDays,
    startDate,
    endDate,
    hasExplicitRange,
    sort,
    page,
  ]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    // Load caller modules once for the dropdown
    intelligenceService
      .listCallerModules(30)
      .then(setCallerModules)
      .catch(() => setCallerModules([]));
  }, []);

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

  const hasFilters = Boolean(
    promptKey ||
      callerModule ||
      company ||
      statusFilter ||
      (!hasExplicitRange && sinceDays !== 7) ||
      hasExplicitRange,
  );

  /** Switch from relative (since_days) to explicit window, or vice versa. */
  function setPreset(days: number) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("start_date");
      next.delete("end_date");
      next.set("since_days", String(days));
      next.delete("page");
      return next;
    });
  }

  function clearExplicitRange() {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("start_date");
      next.delete("end_date");
      next.delete("page");
      return next;
    });
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link
          to="/admin/intelligence/prompts"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Prompt Library
        </Link>
        <h1 className="mt-1 text-3xl font-bold">Execution Log</h1>
        <p className="text-muted-foreground">
          Every AI call — most recent first. Drill into any row for full detail.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Input
          className="w-56"
          placeholder="Filter by prompt_key"
          value={promptKey}
          onChange={(e) => updateParam("prompt_key", e.target.value)}
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={callerModule}
          onChange={(e) => updateParam("caller_module", e.target.value)}
        >
          <option value="">All caller modules</option>
          {callerModules.map((m) => (
            <option key={m.caller_module} value={m.caller_module}>
              {m.caller_module} ({m.execution_count})
            </option>
          ))}
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={company}
          onChange={(e) => updateParam("company_id", e.target.value)}
        >
          <option value="">All companies</option>
          <option value="platform">Platform-global only</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={statusFilter}
          onChange={(e) => updateParam("status", e.target.value)}
        >
          <option value="">Any status</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
        </select>
        {hasExplicitRange ? (
          <div
            className="flex h-9 items-center gap-2 rounded-md border border-primary/40 bg-primary/5 px-3 text-xs"
            title={`Filtered window: ${startDate || "…"} → ${endDate || "…"}`}
          >
            <span>
              {startDate ? new Date(startDate).toLocaleDateString() : "…"}{" "}
              →{" "}
              {endDate ? new Date(endDate).toLocaleDateString() : "…"}
            </span>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground"
              onClick={clearExplicitRange}
              aria-label="Clear explicit date range"
            >
              ✕
            </button>
          </div>
        ) : (
          <select
            className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            value={String(sinceDays)}
            onChange={(e) => setPreset(parseInt(e.target.value, 10))}
            aria-label="Date range"
          >
            <option value="1">Last 24h</option>
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </select>
        )}
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={sort}
          onChange={(e) => updateParam("sort", e.target.value)}
        >
          <option value="created_desc">Sort: Newest</option>
          <option value="created_asc">Sort: Oldest</option>
          <option value="cost_desc">Sort: Cost ↓</option>
          <option value="latency_desc">Sort: Latency ↓</option>
          <option value="tokens_desc">Sort: Tokens ↓</option>
        </select>
        {hasFilters && (
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
              <TableHead>Time</TableHead>
              <TableHead>Prompt</TableHead>
              <TableHead>Caller</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Model</TableHead>
              <TableHead className="text-right">Tokens (in/out)</TableHead>
              <TableHead className="text-right">Cost</TableHead>
              <TableHead className="text-right">Latency</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : executions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="py-6 text-center text-muted-foreground">
                  {hasFilters ? (
                    <>
                      No executions match your filters.{" "}
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
                      No executions yet. Trigger an AI call — e.g.{" "}
                      <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                        python scripts/seed_intelligence_dev_executions.py
                      </code>{" "}
                      — to populate this log.
                    </>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              executions.map((e) => (
                <TableRow key={e.id}>
                  <TableCell
                    className="text-xs text-muted-foreground"
                    title={e.created_at}
                  >
                    {formatRelativeTime(e.created_at)}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {e.prompt_key ? (
                      <Link
                        to={`/admin/intelligence/prompts/${e.prompt_id}`}
                        className="underline"
                      >
                        {e.prompt_key}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {e.caller_module ?? "—"}
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
                  <TableCell className="text-right text-xs">
                    {formatNumber(e.input_tokens)} / {formatNumber(e.output_tokens)}
                  </TableCell>
                  <TableCell className="text-right text-xs">
                    {formatCost(e.cost_usd)}
                  </TableCell>
                  <TableCell className="text-right text-xs">
                    {formatLatency(e.latency_ms)}
                  </TableCell>
                  <TableCell>
                    <Link
                      to={`/admin/intelligence/executions/${e.id}`}
                      className="text-xs underline"
                    >
                      View
                    </Link>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm">
        <div className="text-muted-foreground">
          Page {page} · Showing {executions.length} execution
          {executions.length !== 1 ? "s" : ""}
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
            disabled={!hasMore}
            onClick={() => updateParam("page", String(page + 1))}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
