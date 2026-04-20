/**
 * Chart mode — recharts-backed, lazy-loaded.
 *
 * Five chart types: bar, line, area, pie, donut. The parent
 * SavedViewRenderer wraps this component in `React.lazy` +
 * `Suspense` so the recharts chunk is code-split and never ships
 * in the initial bundle for non-chart callers.
 *
 * The executor returns pre-aggregated results:
 *   - `result.rows`: the primary data table
 *   - `result.aggregations`: { "agg_{func}_{field}": value } for
 *     stat-style scalars (handled by StatRenderer, not here)
 *
 * For chart aggregations (GROUP BY x_field, SUM(y_field)):
 * `result.rows` is the aggregated form — one row per x-axis tick —
 * with the y-axis column named per the Aggregation spec's alias
 * (default `{func}_{field}`, e.g. `sum_total`).
 */

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3 } from "lucide-react";

import type {
  ChartConfig,
  SavedViewResult,
} from "@/types/saved-views";
import { EmptyState } from "@/components/ui/empty-state";

export interface ChartRendererProps {
  result: SavedViewResult;
  chartConfig: ChartConfig;
}

// Tailwind-y palette — keep in sync with the stat renderer. Wraps
// at length so large group counts don't explode memory.
const PALETTE = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#06b6d4", "#84cc16",
];

function colorFor(i: number): string {
  return PALETTE[i % PALETTE.length]!;
}

/**
 * Resolve the y-axis series key. ChartConfig.y_field names the
 * underlying entity field; the executor emits the aggregation under
 * `{y_aggregation}_{y_field}`. This helper returns the actual row
 * key to plot.
 */
function resolveYKey(chartConfig: ChartConfig): string {
  if (!chartConfig.y_aggregation || !chartConfig.y_field) {
    return chartConfig.y_field ?? "value";
  }
  return `${chartConfig.y_aggregation}_${chartConfig.y_field}`;
}

export function ChartRenderer({ result, chartConfig }: ChartRendererProps) {
  const xKey = chartConfig.x_field;
  const yKey = resolveYKey(chartConfig);

  if (result.rows.length === 0) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No data for the selected period"
        description="Widen your filters or extend the date range to see values."
        tone="filtered"
        size="sm"
        data-testid="chart-renderer-empty"
      />
    );
  }

  const commonAxes = (
    <>
      <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
      <XAxis dataKey={xKey} fontSize={12} />
      <YAxis fontSize={12} />
      <Tooltip />
      <Legend />
    </>
  );

  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        {(() => {
          switch (chartConfig.chart_type) {
            case "bar":
              return (
                <BarChart data={result.rows}>
                  {commonAxes}
                  <Bar dataKey={yKey} fill={colorFor(0)} />
                </BarChart>
              );
            case "line":
              return (
                <LineChart data={result.rows}>
                  {commonAxes}
                  <Line
                    type="monotone"
                    dataKey={yKey}
                    stroke={colorFor(0)}
                    dot={false}
                  />
                </LineChart>
              );
            case "area":
              return (
                <AreaChart data={result.rows}>
                  {commonAxes}
                  <Area
                    type="monotone"
                    dataKey={yKey}
                    stroke={colorFor(0)}
                    fill={colorFor(0)}
                    fillOpacity={0.25}
                  />
                </AreaChart>
              );
            case "pie":
            case "donut":
              return (
                <PieChart>
                  <Tooltip />
                  <Legend />
                  <Pie
                    data={result.rows}
                    dataKey={yKey}
                    nameKey={xKey}
                    cx="50%"
                    cy="50%"
                    outerRadius={110}
                    innerRadius={chartConfig.chart_type === "donut" ? 55 : 0}
                    label
                  >
                    {result.rows.map((_row, idx) => (
                      <Cell key={idx} fill={colorFor(idx)} />
                    ))}
                  </Pie>
                </PieChart>
              );
            default:
              return (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  Unknown chart type: {chartConfig.chart_type}
                </div>
              );
          }
        })()}
      </ResponsiveContainer>
    </div>
  );
}

// Default export so React.lazy in the parent can import it directly.
export default ChartRenderer;
