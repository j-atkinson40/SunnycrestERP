import { useMemo } from "react";
import type { DailyStatPoint } from "@/types/intelligence";

interface Props {
  data: DailyStatPoint[];
  height?: number;
  showCost?: boolean;
}

/**
 * Tiny inline SVG chart — bars for execution count, overlaid line for cost.
 * No external chart library; matches the codebase's no-extra-deps style.
 */
export function DailyChart({ data, height = 140, showCost = true }: Props) {
  const { bars, costPoints, maxCount, maxCost, xStep } = useMemo(() => {
    if (data.length === 0) {
      return { bars: [], costPoints: [] as string[], maxCount: 0, maxCost: 0, xStep: 0 };
    }
    const mc = Math.max(...data.map((d) => d.count), 1);
    const mco = Math.max(
      ...data.map((d) => parseFloat(d.cost_usd) || 0),
      0.00001
    );
    const step = data.length > 1 ? 100 / (data.length - 1) : 100;
    return {
      bars: data.map((d, i) => ({
        x: (i * 100) / Math.max(data.length, 1),
        w: 100 / Math.max(data.length, 1),
        hPct: (d.count / mc) * 100,
        count: d.count,
        cost: parseFloat(d.cost_usd) || 0,
        date: d.date,
        errors: d.error_count,
        avgLatency: d.avg_latency_ms,
      })),
      costPoints: data.map((d, i) => {
        const x = i * step;
        const c = parseFloat(d.cost_usd) || 0;
        const y = 100 - (c / mco) * 100;
        return `${x},${y}`;
      }),
      maxCount: mc,
      maxCost: mco,
      xStep: step,
    };
  }, [data]);

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-md border bg-muted/30 text-sm text-muted-foreground"
        style={{ height }}
      >
        No executions in this window
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="w-full rounded-md border bg-card"
        style={{ height }}
      >
        {bars.map((b) => {
          const costLabel =
            b.cost >= 1
              ? `$${b.cost.toFixed(2)}`
              : b.cost > 0
              ? `$${b.cost.toFixed(4)}`
              : "$0";
          const latencyLabel =
            b.avgLatency !== null && b.avgLatency !== undefined
              ? b.avgLatency < 1000
                ? `${Math.round(b.avgLatency)}ms avg latency`
                : `${(b.avgLatency / 1000).toFixed(2)}s avg latency`
              : null;
          const errorLabel =
            b.errors > 0 ? `${b.errors} error${b.errors !== 1 ? "s" : ""}` : null;
          // `<title>` inside SVG gives the browser's native hover tooltip —
          // multi-line via "\n" works in most browsers and degrades to a
          // single line elsewhere. Enough polish without a floating panel.
          const tooltip = [
            b.date,
            `${b.count} execution${b.count !== 1 ? "s" : ""}`,
            costLabel,
            errorLabel,
            latencyLabel,
          ]
            .filter(Boolean)
            .join(" · ");
          return (
            <g key={b.date}>
              <rect
                x={b.x + 0.1}
                y={100 - b.hPct}
                width={Math.max(b.w - 0.2, 0.1)}
                height={b.hPct}
                fill="currentColor"
                className="text-primary/70"
              >
                <title>{tooltip}</title>
              </rect>
              {b.errors > 0 && (
                <rect
                  x={b.x + 0.1}
                  y={100 - (b.errors / maxCount) * 100}
                  width={Math.max(b.w - 0.2, 0.1)}
                  height={(b.errors / maxCount) * 100}
                  fill="currentColor"
                  className="text-destructive/80"
                >
                  <title>{tooltip}</title>
                </rect>
              )}
            </g>
          );
        })}
        {showCost && costPoints.length > 1 && (
          <polyline
            points={costPoints.join(" ")}
            fill="none"
            stroke="currentColor"
            strokeWidth="0.5"
            className="text-amber-500"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Peak: {maxCount} execs/day</span>
        {showCost && <span>Peak cost: ${maxCost.toFixed(2)}/day</span>}
        <span>
          {data[0]?.date} → {data[data.length - 1]?.date}
        </span>
        <span className="sr-only">(step {xStep.toFixed(1)})</span>
      </div>
    </div>
  );
}
