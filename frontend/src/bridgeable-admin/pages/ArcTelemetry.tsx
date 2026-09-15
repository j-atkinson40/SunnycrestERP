/**
 * Phase 7 — Arc telemetry dashboard.
 *
 * Minimal single-page view of:
 *   - Per-endpoint p50 / p99 / request count / error rate (5 tracked
 *     arc endpoints) — from in-memory process counters
 *   - Intelligence call aggregations over 24h / 7d / 30d — persisted
 *     in intelligence_executions
 *   - Per-caller-module cost breakdown (24h)
 *
 * Honest expectation-setting: the top-of-page note tells the admin
 * that endpoint counters clear on process restart. For long-term
 * metrics, see post-arc observability roadmap.
 */

import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Clock, DollarSign } from "lucide-react";
import { adminApi } from "../lib/admin-api";

interface EndpointCounter {
  endpoint: string;
  request_count: number;
  error_count: number;
  error_rate: number;
  samples: number;
  p50_ms: number | null;
  // The slow-end value, and WHICH statistic it is. Below 99 samples a p99
  // cannot be computed from the buffer, so the backend reports the observed
  // maximum and says "max". The label travels with the value; the value is
  // never relabelled. See app/services/arc_telemetry.py::_tail.
  tail_ms: number | null;
  tail_stat: "p99" | "max" | null;
}

interface IntelWindow {
  total_calls: number;
  total_cost_usd: number;
  avg_latency_ms: number | null;
  error_rate: number;
}

interface ByCallerRow {
  caller_module: string;
  calls: number;
  cost_usd: number;
}

interface GcCounters {
  gen2_collections: number;
  gen2_pause_ms_max: number | null;
  gen2_pause_ms_total: number;
  // null until BOTH enough collections and a long enough window support a rate.
  // The basis string says which is missing — see arc_telemetry._gc_snapshot.
  gen2_per_hour: number | null;
  gen2_rate_basis: string;
}

interface TelemetryResponse {
  endpoint_counters: {
    process_uptime_seconds: number;
    endpoints: EndpointCounter[];
    gc: GcCounters;
  };
  intelligence: {
    windows: Record<string, IntelWindow>;
    by_caller_module_24h: ByCallerRow[];
  };
  notes: string[];
}

function formatMs(v: number | null): string {
  if (v == null) return "—";
  if (v < 1) return `${v.toFixed(2)}ms`;
  if (v < 10) return `${v.toFixed(1)}ms`;
  return `${Math.round(v)}ms`;
}

function formatCurrency(v: number): string {
  if (v < 0.01) return `$${v.toFixed(4)}`;
  if (v < 1) return `$${v.toFixed(3)}`;
  return `$${v.toFixed(2)}`;
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

export function ArcTelemetry() {
  const [data, setData] = useState<TelemetryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    adminApi
      .get<TelemetryResponse>("/api/platform/admin/arc-telemetry")
      .then((r) => setData(r.data))
      .catch((e) => setError(e?.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const id = window.setInterval(load, 30_000);
    return () => window.clearInterval(id);
  }, []);

  if (loading && !data) {
    return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  }
  if (error) {
    return <div className="p-6 text-sm text-destructive">{error}</div>;
  }
  if (!data) return null;

  const uptime = data.endpoint_counters.process_uptime_seconds;
  const intel24 = data.intelligence.windows["24h"];
  const intel7d = data.intelligence.windows["7d"];
  const intel30d = data.intelligence.windows["30d"];

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <Activity className="h-5 w-5" />
          Arc telemetry
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Phase 7 minimal surface. Endpoint counters are per-process
          and in-memory — they clear on restart. For long-term metrics,
          see the post-arc observability roadmap.
        </p>
      </header>

      <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900 flex items-start gap-2">
        <AlertTriangle className="h-3.5 w-3.5 mt-0.5" />
        <div>
          <div className="font-medium">Honest expectation-setting</div>
          <div>
            Endpoint counters cover the current backend process (uptime:{" "}
            <span className="font-mono">{formatUptime(uptime)}</span>).
            Intelligence aggregations below are persisted and survive
            restarts.
            <div className="mt-1">
              The buffer refills from empty on every deploy. A 99th percentile
              needs 99 samples, so below that the slow-end column shows the{" "}
              <span className="font-medium">slowest request so far</span>,
              marked{" "}
              <span className="rounded bg-amber-100 px-1 py-0.5 text-[10px] font-medium text-amber-800">
                max
              </span>
              . It is never a percentile wearing a percentile's name.
            </div>
          </div>
        </div>
      </div>

      <section>
        <h2 className="mb-2 text-sm font-semibold flex items-center gap-1.5">
          <Clock className="h-4 w-4" />
          Garbage collection (this process)
        </h2>
        <div className="rounded-md border px-4 py-3 text-sm">
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2">
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500">
                Gen-2 collections
              </div>
              <div className="tabular-nums text-lg">
                {data.endpoint_counters.gc.gen2_collections}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500">
                Longest pause
              </div>
              <div className="tabular-nums text-lg">
                {formatMs(data.endpoint_counters.gc.gen2_pause_ms_max)}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500">
                Rate
              </div>
              <div className="tabular-nums text-lg">
                {data.endpoint_counters.gc.gen2_per_hour == null ? (
                  <span className="text-gray-400">—</span>
                ) : (
                  <>
                    {data.endpoint_counters.gc.gen2_per_hour.toFixed(1)}
                    <span className="ml-1 text-xs text-gray-500">/hour</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="mt-2 text-xs text-gray-500">
            {data.endpoint_counters.gc.gen2_rate_basis}
          </div>
          <div className="mt-1 text-xs text-gray-500">
            A gen-2 collection walks the whole heap and blocks the process. This
            service runs a single worker, so a pause stalls every request in
            flight, not one worker&rsquo;s share. Measured locally at ~380&ndash;470&nbsp;ms
            over ~2.1M tracked objects; this panel is here to find out how often
            it actually happens in production.
          </div>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold flex items-center gap-1.5">
          <Clock className="h-4 w-4" />
          Arc endpoint latency (in-memory, current process)
        </h2>
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-3 py-2 text-left">Endpoint</th>
                <th className="px-3 py-2 text-right">Requests</th>
                <th className="px-3 py-2 text-right">p50</th>
                <th className="px-3 py-2 text-right">Slow end</th>
                <th className="px-3 py-2 text-right">Samples</th>
                <th className="px-3 py-2 text-right">Errors</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.endpoint_counters.endpoints.map((e) => (
                <tr key={e.endpoint}>
                  <td className="px-3 py-2 font-mono text-xs">{e.endpoint}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {e.request_count}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatMs(e.p50_ms)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    <span>{formatMs(e.tail_ms)}</span>
                    {e.tail_stat && (
                      <span
                        className={
                          "ml-1.5 rounded px-1 py-0.5 text-[10px] font-medium " +
                          (e.tail_stat === "p99"
                            ? "bg-gray-100 text-gray-600"
                            : "bg-amber-100 text-amber-800")
                        }
                        title={
                          e.tail_stat === "p99"
                            ? "99th percentile — a latency an actual request recorded"
                            : `Only ${e.samples} samples buffered; a p99 needs 99. ` +
                              "This is the slowest request so far, not a percentile."
                        }
                      >
                        {e.tail_stat}
                      </span>
                    )}
                  </td>
                  <td
                    className={
                      "px-3 py-2 text-right tabular-nums " +
                      (e.samples > 0 && e.samples < 99
                        ? "text-amber-800"
                        : "text-gray-500")
                    }
                    title="Samples in the rolling buffer. Below 99 the slow-end column reports a max, not a p99."
                  >
                    {e.samples}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {e.error_count > 0 ? (
                      <span className="text-red-600">
                        {e.error_count} ({(e.error_rate * 100).toFixed(1)}%)
                      </span>
                    ) : (
                      <span className="text-gray-400">0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold flex items-center gap-1.5">
          <DollarSign className="h-4 w-4" />
          Intelligence calls (persisted — intelligence_executions)
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <IntelCard window="24h" data={intel24} />
          <IntelCard window="7d" data={intel7d} />
          <IntelCard window="30d" data={intel30d} />
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold">
          Top Intelligence callers (24h)
        </h2>
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-3 py-2 text-left">Caller module</th>
                <th className="px-3 py-2 text-right">Calls</th>
                <th className="px-3 py-2 text-right">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.intelligence.by_caller_module_24h.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-3 py-4 text-center text-xs text-gray-400">
                    No Intelligence calls in the last 24 hours.
                  </td>
                </tr>
              ) : (
                data.intelligence.by_caller_module_24h.map((r) => (
                  <tr key={r.caller_module}>
                    <td className="px-3 py-2 font-mono text-xs">
                      {r.caller_module}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{r.calls}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatCurrency(r.cost_usd)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="text-xs text-gray-400">
        {data.notes.map((n, i) => (
          <p key={i}>· {n}</p>
        ))}
      </section>
    </div>
  );
}

function IntelCard({
  window,
  data,
}: {
  window: string;
  data: IntelWindow | undefined;
}) {
  if (!data) return null;
  return (
    <div className="rounded-md border bg-white p-3">
      <div className="text-xs uppercase tracking-wide text-gray-500">
        {window}
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <div className="text-2xl font-semibold tabular-nums">
          {data.total_calls}
        </div>
        <div className="text-xs text-gray-400">calls</div>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
        <div>
          <div className="text-gray-400">Cost</div>
          <div className="font-mono">{formatCurrency(data.total_cost_usd)}</div>
        </div>
        <div>
          <div className="text-gray-400">Avg latency</div>
          <div className="font-mono">{formatMs(data.avg_latency_ms)}</div>
        </div>
        {data.error_rate > 0 && (
          <div className="col-span-2">
            <div className="text-gray-400">Error rate</div>
            <div className="font-mono text-red-600">
              {(data.error_rate * 100).toFixed(1)}%
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
