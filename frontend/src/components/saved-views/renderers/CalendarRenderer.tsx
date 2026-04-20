/**
 * Calendar mode — DIY month grid.
 *
 * Phase 2 ships a lightweight month grid: 7-column week header,
 * 6-row day cells, previous/next month nav, "today" button. No
 * week/day view, no drag-drop, no external deps.
 *
 * If FH service scheduling needs more (overlapping time slots,
 * week-at-a-time, all-day bars) in a later phase, we swap the
 * body of this component for `react-big-calendar` without touching
 * the SavedViewRenderer dispatch.
 */

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import type {
  CalendarConfig,
  EntityTypeMetadata,
  SavedViewResult,
} from "@/types/saved-views";

export interface CalendarRendererProps {
  result: SavedViewResult;
  entity: EntityTypeMetadata;
  calendarConfig: CalendarConfig;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function addMonths(d: Date, delta: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + delta, 1);
}

function toDateKey(d: Date): string {
  // Local-timezone YYYY-MM-DD — used as a dict key to find events
  // for the day. Crosses DST boundaries correctly because Date
  // constructor gives midnight-local.
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function buildHref(template: string, row: Record<string, unknown>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    const v = row[key];
    return v === undefined || v === null ? "" : String(v);
  });
}

export function CalendarRenderer({
  result,
  entity,
  calendarConfig,
}: CalendarRendererProps) {
  const [cursor, setCursor] = useState<Date>(() => startOfMonth(new Date()));

  // Bucket rows by YYYY-MM-DD once per result change.
  const byDate = useMemo(() => {
    const out: Record<string, Record<string, unknown>[]> = {};
    for (const r of result.rows) {
      const raw = r[calendarConfig.date_field];
      if (typeof raw !== "string") continue;
      const d = new Date(raw);
      if (Number.isNaN(d.getTime())) continue;
      const key = toDateKey(d);
      (out[key] ??= []).push(r);
    }
    return out;
  }, [result.rows, calendarConfig.date_field]);

  // Six-row grid covering the target month plus leading/trailing
  // days from adjacent months.
  const gridDays = useMemo<Date[]>(() => {
    const first = startOfMonth(cursor);
    const startOffset = first.getDay(); // 0 = Sunday
    const grid: Date[] = [];
    for (let i = 0; i < 42; i += 1) {
      const day = new Date(first.getFullYear(), first.getMonth(), i - startOffset + 1);
      grid.push(day);
    }
    return grid;
  }, [cursor]);

  const today = new Date();
  const todayKey = toDateKey(today);
  const monthLabel = cursor.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  // Count events whose date falls inside the visible month.
  const monthStart = startOfMonth(cursor);
  const monthEnd = addMonths(monthStart, 1);
  const eventsInView = result.rows.reduce((acc, r) => {
    const raw = r[calendarConfig.date_field];
    if (typeof raw !== "string") return acc;
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return acc;
    return d >= monthStart && d < monthEnd ? acc + 1 : acc;
  }, 0);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCursor((c) => addMonths(c, -1))}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCursor(startOfMonth(new Date()))}
          >
            Today
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCursor((c) => addMonths(c, 1))}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <div className="text-sm font-medium">{monthLabel}</div>
      </div>

      <div
        className="grid grid-cols-7 gap-px rounded-md border bg-border text-xs overflow-x-auto"
        data-testid="calendar-grid"
      >
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            className="bg-muted/40 px-2 py-1 font-medium uppercase tracking-wide"
          >
            {d}
          </div>
        ))}
        {gridDays.map((d) => {
          const key = toDateKey(d);
          const inMonth = d.getMonth() === cursor.getMonth();
          const isToday = key === todayKey;
          const events = byDate[key] ?? [];
          return (
            <div
              key={key}
              className={`min-h-[70px] sm:min-h-[92px] bg-card p-1 ${
                inMonth ? "" : "bg-muted/20 text-muted-foreground"
              }`}
            >
              <div
                className={`mb-1 flex h-5 w-5 items-center justify-center rounded-full text-xs ${
                  isToday
                    ? "bg-primary text-primary-foreground font-semibold"
                    : ""
                }`}
              >
                {d.getDate()}
              </div>
              <div className="flex flex-col gap-0.5">
                {events.slice(0, 3).map((e, i) => {
                  const id = e.id as string | undefined;
                  const href = id
                    ? buildHref(entity.navigate_url_template, e)
                    : null;
                  const label = String(
                    e[calendarConfig.label_field] ?? "(untitled)",
                  );
                  const body = (
                    <div className="truncate rounded bg-primary/10 px-1 py-0.5 text-[11px] text-primary hover:bg-primary/20">
                      {label}
                    </div>
                  );
                  return (
                    <div key={id ?? i}>
                      {href ? <Link to={href}>{body}</Link> : body}
                    </div>
                  );
                })}
                {events.length > 3 && (
                  <div className="text-[11px] text-muted-foreground">
                    +{events.length - 3} more
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {eventsInView === 0 ? (
        <div
          className="rounded-md border border-dashed px-4 py-3 text-center text-xs text-muted-foreground"
          data-testid="calendar-renderer-empty"
        >
          No events in {monthLabel}. Use the arrows to change month, or
          adjust filters if this looks wrong.
        </div>
      ) : null}
    </div>
  );
}
