/**
 * Scheduling Board — Multi-panel Kanban view
 *
 * Shows today's full Kanban board stacked above the next delivery day's
 * Kanban board. On Saturdays, shows three panels (Sat + Sun + Mon) for
 * weekend planning. The "next delivery day" is context-aware — skips
 * weekends when delivery is disabled.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/auth-context";
import { KanbanPanel } from "@/components/delivery/kanban-panel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function addDays(d: Date, n: number): Date {
  const result = new Date(d);
  result.setDate(result.getDate() + n);
  return result;
}

function formatDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function parseDate(s: string): Date {
  return new Date(s + "T12:00:00");
}

function formatDisplayDate(dateStr: string): string {
  const d = parseDate(dateStr);
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function formatShortDate(dateStr: string): string {
  const d = parseDate(dateStr);
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

// ---------------------------------------------------------------------------
// getSchedulingPanels — returns panels array and context flags
// ---------------------------------------------------------------------------

interface SchedulingPanels {
  panels: string[];
  isSaturdayView: boolean;
}

function getSchedulingPanels(
  currentDateStr: string,
  saturdayEnabled: boolean,
  sundayEnabled: boolean,
): SchedulingPanels {
  const current = parseDate(currentDateStr);
  const dayOfWeek = current.getDay(); // 0=Sun, 1=Mon ... 6=Sat

  // Saturday — always show three panels: Sat + Sun + Mon
  // Sunday may have funerals even if not a standard delivery day
  // Monday always needs to be planned on Saturday
  if (dayOfWeek === 6) {
    return {
      panels: [
        currentDateStr,
        formatDate(addDays(current, 1)), // Sunday
        formatDate(addDays(current, 2)), // Monday
      ],
      isSaturdayView: true,
    };
  }

  // Friday — show Fri + Sat (or Mon if Saturday delivery disabled)
  if (dayOfWeek === 5) {
    const nextDay = saturdayEnabled
      ? formatDate(addDays(current, 1)) // Saturday
      : formatDate(addDays(current, 3)); // Monday
    return {
      panels: [currentDateStr, nextDay],
      isSaturdayView: false,
    };
  }

  // Sunday — show Sun + Mon
  if (dayOfWeek === 0) {
    return {
      panels: [currentDateStr, formatDate(addDays(current, 1))],
      isSaturdayView: false,
    };
  }

  // Monday through Thursday — show today + tomorrow
  // Skip Sunday if Sunday delivery disabled
  const tomorrow = addDays(current, 1);
  const tomorrowDay = tomorrow.getDay();

  if (tomorrowDay === 0 && !sundayEnabled) {
    return {
      panels: [currentDateStr, formatDate(addDays(current, 2))], // skip to Monday
      isSaturdayView: false,
    };
  }

  // TODO: check company holidays when holiday calendar is built

  return {
    panels: [currentDateStr, formatDate(tomorrow)],
    isSaturdayView: false,
  };
}

/** Get the next delivery day for navigation (shifting panel 1 forward). */
function getNextDeliveryDay(
  currentDateStr: string,
  saturdayEnabled: boolean,
  sundayEnabled: boolean,
): string {
  const current = parseDate(currentDateStr);
  const tomorrow = addDays(current, 1);
  const dayOfWeek = tomorrow.getDay();

  if (dayOfWeek === 6 && !saturdayEnabled) {
    return formatDate(addDays(current, 3));
  }
  if (dayOfWeek === 0 && !sundayEnabled) {
    return formatDate(addDays(current, 2));
  }

  return formatDate(tomorrow);
}

/** Get the previous delivery day for navigation. */
function getPrevDeliveryDay(
  currentDateStr: string,
  saturdayEnabled: boolean,
  sundayEnabled: boolean,
): string {
  const current = parseDate(currentDateStr);
  const yesterday = addDays(current, -1);
  const dayOfWeek = yesterday.getDay();

  if (dayOfWeek === 0 && !sundayEnabled) {
    if (saturdayEnabled) {
      return formatDate(addDays(current, -2)); // Saturday
    }
    return formatDate(addDays(current, -2)); // Friday
  }
  if (dayOfWeek === 6 && !saturdayEnabled) {
    return formatDate(addDays(current, -2)); // Friday
  }

  return formatDate(yesterday);
}

// ---------------------------------------------------------------------------
// Panel collapse persistence
// ---------------------------------------------------------------------------

function loadPanelCollapsed(key: string): boolean {
  try {
    return localStorage.getItem(key) === "true";
  } catch {
    return false;
  }
}

function savePanelCollapsed(key: string, collapsed: boolean): void {
  try {
    localStorage.setItem(key, String(collapsed));
  } catch {
    /* noop */
  }
}

/** Build localStorage key for panel collapse state. */
function collapseKey(
  panelType: string,
  tenantId: string,
  userId: string,
): string {
  return `scheduling_board_${panelType}_collapsed_${tenantId}_${userId}`;
}

// ---------------------------------------------------------------------------
// Panel label helpers
// ---------------------------------------------------------------------------

function getPanelLabel(
  dateStr: string,
  panelIndex: number,
  _primaryDate: string,
  isSaturdayView: boolean,
): string {
  const todayStr = formatDate(new Date());
  const tomorrowStr = formatDate(addDays(new Date(), 1));

  if (dateStr === todayStr) return "Today";
  if (dateStr === tomorrowStr) return "Tomorrow";

  if (isSaturdayView && panelIndex === 2) return "Plan ahead";

  return "Next delivery day";
}

function getPanelSubtitle(
  dateStr: string,
  panelIndex: number,
  primaryDate: string,
): string | undefined {
  if (panelIndex === 0) return undefined;

  // Check if this date is consecutive to the primary date
  const prevPanelDate =
    panelIndex === 1
      ? primaryDate
      : formatDate(addDays(parseDate(primaryDate), 1));
  const expectedNext = formatDate(addDays(parseDate(prevPanelDate), 1));

  if (dateStr !== expectedNext && panelIndex === 1) {
    const dayName = formatDisplayDate(dateStr).split(",")[0];
    return `Showing ${dayName} \u2014 next delivery day`;
  }

  return undefined;
}

// ---------------------------------------------------------------------------
// Main Scheduling Board Page
// ---------------------------------------------------------------------------

export default function SchedulingBoardPage() {
  const { user, company } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // Tenant settings for weekend delivery
  const tenantSettings =
    (company as unknown as Record<string, unknown>) ?? {};
  const saturdayEnabled =
    (tenantSettings.saturday_delivery_enabled as boolean) ?? true;
  const sundayEnabled =
    (tenantSettings.sunday_delivery_enabled as boolean) ?? false;

  // Date state
  const todayStr = formatDate(new Date());
  const dateParam = searchParams.get("date");
  const [primaryDate, setPrimaryDate] = useState<string>(
    dateParam || todayStr,
  );

  // Compute panels from primary date
  const { panels, isSaturdayView } = useMemo(
    () => getSchedulingPanels(primaryDate, saturdayEnabled, sundayEnabled),
    [primaryDate, saturdayEnabled, sundayEnabled],
  );

  // Whether we're viewing the default (today) pair
  const isDefaultView = primaryDate === todayStr;

  // Collapse state — keyed per panel type
  const tenantId = company?.id || "default";
  const userId = user?.id || "default";

  const tomorrowKey = collapseKey("tomorrow", tenantId, userId);
  const sundayKey = collapseKey("sunday", tenantId, userId);
  const mondaySatKey = collapseKey("monday_sat", tenantId, userId);

  const [collapseState, setCollapseState] = useState<Record<string, boolean>>(
    () => ({
      tomorrow: loadPanelCollapsed(tomorrowKey),
      sunday: loadPanelCollapsed(sundayKey),
      monday_sat: loadPanelCollapsed(mondaySatKey),
    }),
  );

  const toggleCollapse = useCallback(
    (panelType: string) => {
      setCollapseState((prev) => {
        const next = !prev[panelType];
        savePanelCollapsed(
          collapseKey(panelType, tenantId, userId),
          next,
        );
        return { ...prev, [panelType]: next };
      });
    },
    [tenantId, userId],
  );

  /** Get the collapse key type for a given panel index in the current view. */
  function getCollapsePanelType(panelIndex: number): string {
    if (panelIndex === 0) return ""; // Panel 1 never collapses
    if (isSaturdayView) {
      return panelIndex === 1 ? "sunday" : "monday_sat";
    }
    return "tomorrow";
  }

  // Navigation handlers
  const goNext = useCallback(() => {
    const next = getNextDeliveryDay(
      primaryDate,
      saturdayEnabled,
      sundayEnabled,
    );
    setPrimaryDate(next);
    setSearchParams(next === todayStr ? {} : { date: next });
  }, [primaryDate, saturdayEnabled, sundayEnabled, todayStr, setSearchParams]);

  const goPrev = useCallback(() => {
    const prev = getPrevDeliveryDay(
      primaryDate,
      saturdayEnabled,
      sundayEnabled,
    );
    setPrimaryDate(prev);
    setSearchParams(prev === todayStr ? {} : { date: prev });
  }, [primaryDate, saturdayEnabled, sundayEnabled, todayStr, setSearchParams]);

  const goToday = useCallback(() => {
    setPrimaryDate(todayStr);
    setSearchParams({});
  }, [todayStr, setSearchParams]);

  const handleDateChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      if (val) {
        setPrimaryDate(val);
        setSearchParams(val === todayStr ? {} : { date: val });
      }
    },
    [todayStr, setSearchParams],
  );

  // Sync with URL params on mount
  useEffect(() => {
    if (dateParam && dateParam !== primaryDate) {
      setPrimaryDate(dateParam);
    }
  }, [dateParam]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      {/* ── Page Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">
              Scheduling Board
            </h1>
            {isSaturdayView && isDefaultView && (
              <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200 text-xs font-medium">
                Weekend Planning View
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isDefaultView
              ? isSaturdayView
                ? `Saturday, ${formatShortDate(todayStr)} \u00b7 Today + Weekend Planning View`
                : `Today \u2014 ${formatShortDate(todayStr)}`
              : formatShortDate(primaryDate)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Back to today pill */}
          {!isDefaultView && (
            <button
              onClick={goToday}
              className="flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
            >
              <span>↩</span>
              Back to today
            </button>
          )}

          {/* Navigation arrows + date picker */}
          <button
            onClick={goPrev}
            className="rounded-md border px-2.5 py-1.5 text-sm hover:bg-slate-100 transition-colors"
            aria-label="Previous delivery day"
          >
            ←
          </button>
          <input
            type="date"
            value={primaryDate}
            onChange={handleDateChange}
            className="rounded-md border px-3 py-1.5 text-sm"
          />
          <button
            onClick={goNext}
            className="rounded-md border px-2.5 py-1.5 text-sm hover:bg-slate-100 transition-colors"
            aria-label="Next delivery day"
          >
            →
          </button>
        </div>
      </div>

      {/* ── Panels — dynamically rendered (2 or 3) ── */}
      {panels.map((dateStr, idx) => {
        const panelType = getCollapsePanelType(idx);
        const isFirst = idx === 0;
        const isOptionalDay = isSaturdayView && idx === 1; // Sunday in Saturday view
        const showPlanAheadBadge = isSaturdayView && idx === 2; // Monday in Saturday view

        return (
          <KanbanPanel
            key={dateStr}
            dateStr={dateStr}
            isToday={dateStr === todayStr}
            label={getPanelLabel(dateStr, idx, primaryDate, isSaturdayView)}
            subtitle={getPanelSubtitle(dateStr, idx, primaryDate)}
            collapsed={isFirst ? false : (collapseState[panelType] ?? false)}
            onToggleCollapse={
              isFirst ? undefined : () => toggleCollapse(panelType)
            }
            collapsible={!isFirst}
            isOptionalDay={isOptionalDay}
            showPlanAheadBadge={showPlanAheadBadge}
            panelPrefix={`panel${idx}`}
          />
        );
      })}
    </div>
  );
}
