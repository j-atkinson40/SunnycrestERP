import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { X, RefreshCw, Check, ChevronRight, Pin } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/api-client";

// ── Types ──

interface BriefingItem {
  number: number;
  text: string;
  priority: "critical" | "warning" | "info";
  related_entity_type?: string;
  related_entity_hint?: string;
}

interface BriefingResponse {
  content: string | null;
  items: BriefingItem[];
  tier: "primary_area" | "executive" | "role_based";
  primary_area: string | null;
  was_cached: boolean;
  generated_at: string;
  briefing_date: string;
  reason?: string;
}

interface AnnouncementItem {
  id: string;
  title: string;
  body: string | null;
  priority: "info" | "warning" | "critical";
  pin_to_top: boolean;
  created_at: string | null;
  expires_at: string | null;
  created_by_name: string | null;
  is_read: boolean;
  is_dismissed: boolean;
}

// ── Action link inference ──

function inferActionLink(
  item: BriefingItem,
  primaryArea: string | null,
): { label: string; route: string } | null {
  const text = item.text.toLowerCase();

  if (primaryArea === "funeral_scheduling") {
    if (text.includes("unassigned") || text.includes("no driver"))
      return { label: "Schedule", route: "/scheduling" };
    if (text.includes("vault not") || text.includes("inventory"))
      return { label: "Check inventory", route: "/inventory" };
    if (text.includes("spring burial"))
      return { label: "Spring burials", route: "/orders?tab=spring-burials" };
    if (text.includes("unscheduled order"))
      return { label: "View orders", route: "/orders?filter=unscheduled" };
  }

  if (primaryArea === "invoicing_ar") {
    if (text.includes("overdue") || text.includes("unpaid") || text.includes("past due"))
      return { label: "View invoices", route: "/invoices?filter=overdue" };
    if (text.includes("sync error") || text.includes("not syncing"))
      return { label: "Fix sync", route: "/settings/integrations/accounting" };
    if (text.includes("uninvoiced") || text.includes("not sent"))
      return { label: "Send invoices", route: "/invoices?filter=unsent" };
  }

  if (primaryArea === "safety_compliance") {
    if (text.includes("inspection") || text.includes("overdue"))
      return { label: "View safety", route: "/safety" };
    if (text.includes("incident"))
      return { label: "View incidents", route: "/safety/incidents" };
  }

  if (primaryArea === "full_admin") {
    if (text.includes("overdue") || text.includes("unpaid"))
      return { label: "View AR", route: "/invoices?filter=overdue" };
    if (text.includes("sync"))
      return { label: "Fix sync", route: "/settings/integrations/accounting" };
  }

  return null;
}

// ── Helpers ──

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function isAfterNoon(): boolean {
  return new Date().getHours() >= 12;
}

function todayDateString(): string {
  return new Date().toISOString().slice(0, 10);
}

function isAllClear(data: BriefingResponse): boolean {
  if (data.content?.toLowerCase().startsWith("all clear")) return true;
  if (data.content?.startsWith("✓")) return true;
  if (data.items.length <= 1 && data.items.every((i) => i.priority === "info")) return true;
  return false;
}

function relativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays === 1) return "yesterday";
  return `${diffDays}d ago`;
}

// ── Component ──

export function MorningBriefingCard() {
  const { user } = useAuth();
  const [data, setData] = useState<BriefingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [autoDismissProgress, setAutoDismissProgress] = useState(100);
  const [userInteracted, setUserInteracted] = useState(false);
  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([]);
  const [announcementsLoading, setAnnouncementsLoading] = useState(true);
  const autoDismissTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoDismissTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const dismissKey = `briefing_dismissed_${user?.id ?? "anon"}_${todayDateString()}`;

  // Check sessionStorage on mount
  useEffect(() => {
    if (sessionStorage.getItem(dismissKey) === "true") {
      setDismissed(true);
    }
  }, [dismissKey]);

  // Fetch briefing
  const fetchBriefing = useCallback(async () => {
    try {
      const res = await apiClient.get<BriefingResponse>("/briefings/briefing");
      setData(res.data);
    } catch {
      // Fail silently — don't show card
      setData(null);
    }
  }, []);

  // Fetch announcements
  const fetchAnnouncements = useCallback(async () => {
    try {
      const res = await apiClient.get<AnnouncementItem[]>("/announcements/my");
      setAnnouncements(res.data);
    } catch {
      setAnnouncements([]);
    } finally {
      setAnnouncementsLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      await Promise.all([fetchBriefing(), fetchAnnouncements()]);
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchBriefing, fetchAnnouncements]);

  // Mark unread announcements as read (fire-and-forget)
  useEffect(() => {
    if (announcementsLoading) return;
    announcements.forEach((a) => {
      if (!a.is_read) {
        apiClient.post(`/announcements/${a.id}/read`).catch(() => {});
      }
    });
  }, [announcements, announcementsLoading]);

  const handleDismissAnnouncement = async (id: string) => {
    try {
      await apiClient.post(`/announcements/${id}/dismiss`);
    } catch {
      // continue removing from UI
    }
    setAnnouncements((prev) => prev.filter((a) => a.id !== id));
  };

  // Auto-dismiss for all-clear
  useEffect(() => {
    if (!data || userInteracted || dismissed) return;
    if (!isAllClear(data)) return;

    const duration = 10_000;
    const interval = 50;
    let elapsed = 0;

    autoDismissTimer.current = setInterval(() => {
      elapsed += interval;
      setAutoDismissProgress(Math.max(0, 100 - (elapsed / duration) * 100));
    }, interval);

    autoDismissTimeout.current = setTimeout(() => {
      sessionStorage.setItem(dismissKey, "true");
      setDismissed(true);
    }, duration);

    return () => {
      if (autoDismissTimer.current) clearInterval(autoDismissTimer.current);
      if (autoDismissTimeout.current) clearTimeout(autoDismissTimeout.current);
    };
  }, [data, userInteracted, dismissed, dismissKey]);

  // Stop auto-dismiss on user interaction
  const handleInteraction = useCallback(() => {
    if (userInteracted) return;
    setUserInteracted(true);
    setAutoDismissProgress(100);
    if (autoDismissTimer.current) clearInterval(autoDismissTimer.current);
    if (autoDismissTimeout.current) clearTimeout(autoDismissTimeout.current);
  }, [userInteracted]);

  const handleDismiss = () => {
    sessionStorage.setItem(dismissKey, "true");
    setDismissed(true);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await apiClient.post<BriefingResponse>("/briefings/briefing/refresh");
      setData(res.data);
    } catch {
      // Silently fail
    } finally {
      setRefreshing(false);
    }
  };

  const hasAnnouncements = announcements.length > 0;

  // Don't render conditions
  if (dismissed && !hasAnnouncements) return null;
  if (loading) {
    return (
      <Card className="relative overflow-hidden">
        <CardContent className="p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="h-5 w-16 bg-gray-200 rounded animate-pulse" />
            <div className="h-4 w-14 bg-gray-200 rounded animate-pulse" />
          </div>
          <div className="space-y-3">
            <div className="h-4 w-full bg-gray-200 rounded animate-pulse" />
            <div className="h-4 w-4/5 bg-gray-200 rounded animate-pulse" />
            <div className="h-4 w-3/5 bg-gray-200 rounded animate-pulse" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const briefingDisabled = data?.content === null && data?.reason === "disabled";
  const hasBriefing = data && !briefingDisabled && !dismissed;

  if (!hasBriefing && !hasAnnouncements) return null;

  // ── Announcements section (reused across variants) ──
  const announcementsSection = hasAnnouncements ? (
    <div>
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Announcements
      </h4>
      <div className="space-y-2">
        {announcements.map((a) => (
          <div
            key={a.id}
            className={cn(
              "pl-3 pr-2 py-2 rounded-sm border-l-2",
              a.priority === "critical" && "border-l-red-500 bg-red-50/50",
              a.priority === "warning" && "border-l-amber-500 bg-amber-50/50",
              a.priority === "info" && "border-l-blue-400 bg-blue-50/50",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  {a.pin_to_top && (
                    <Pin className="h-3 w-3 text-gray-400 shrink-0" />
                  )}
                  <span className="text-sm font-semibold text-gray-900">
                    {a.title}
                  </span>
                </div>
                {a.body && (
                  <p className="text-sm text-gray-700 mt-0.5 leading-relaxed">
                    {a.body}
                  </p>
                )}
                <p className="text-xs text-gray-400 mt-1">
                  {a.created_by_name && <>from {a.created_by_name} &middot; </>}
                  {a.created_at ? relativeTime(a.created_at) : ""}
                </p>
              </div>
              <button
                onClick={() => handleDismissAnnouncement(a.id)}
                className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors shrink-0 mt-0.5"
                aria-label="Dismiss announcement"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  ) : null;

  const allClear = hasBriefing ? isAllClear(data!) : false;
  const afternoon = isAfterNoon();
  const headerTitle = data?.tier === "role_based" ? "Your day" : afternoon ? "Current Status" : "Today";
  const timeLabel = data
    ? afternoon
      ? `as of ${formatTime(data.generated_at)}`
      : formatTime(data.generated_at)
    : "";

  // ── Announcements-only (no briefing to show) ──
  if (!hasBriefing && hasAnnouncements) {
    return (
      <Card ref={cardRef} className="relative overflow-hidden">
        <CardContent className="p-5">
          {announcementsSection}
        </CardContent>
      </Card>
    );
  }

  // ── Driver / role_based paragraph variant ──
  if (data!.tier === "role_based") {
    return (
      <Card
        ref={cardRef}
        className="relative overflow-hidden"
        onMouseEnter={handleInteraction}
        onClick={handleInteraction}
      >
        <CardContent className="p-5">
          {announcementsSection}
          {hasAnnouncements && (
            <div className="my-3 border-t border-gray-100" />
          )}
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900">{headerTitle}</h3>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">{timeLabel}</span>
              <button
                onClick={handleDismiss}
                className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Dismiss briefing"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">
            {data!.content ?? data!.items.map((i) => i.text).join(" ")}
          </p>
        </CardContent>
      </Card>
    );
  }

  // ── All-clear variant ──
  if (allClear) {
    const displayText = data!.content ?? data!.items[0]?.text ?? "All clear. No flags.";
    return (
      <Card
        ref={cardRef}
        className="relative overflow-hidden"
        onMouseEnter={handleInteraction}
        onClick={handleInteraction}
      >
        <CardContent className="p-5">
          {announcementsSection}
          {hasAnnouncements && (
            <div className="my-3 border-t border-gray-100" />
          )}
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900">{headerTitle}</h3>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">{timeLabel}</span>
              <button
                onClick={handleDismiss}
                className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Dismiss briefing"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <Check className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
            <p className="text-sm text-gray-700 leading-relaxed">{displayText}</p>
          </div>
        </CardContent>
        {/* Auto-dismiss progress bar */}
        {!userInteracted && (
          <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gray-100">
            <div
              className="h-full bg-green-500 transition-all duration-50 ease-linear"
              style={{ width: `${autoDismissProgress}%` }}
            />
          </div>
        )}
      </Card>
    );
  }

  // ── Standard numbered items variant ──
  return (
    <Card
      ref={cardRef}
      className="relative overflow-hidden"
      onMouseEnter={handleInteraction}
      onClick={handleInteraction}
    >
      <CardContent className="p-5">
        {/* Announcements */}
        {announcementsSection}
        {hasAnnouncements && data!.items.length > 0 && (
          <div className="my-3 border-t border-gray-100" />
        )}

        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">{headerTitle}</h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">{timeLabel}</span>
            <button
              onClick={handleDismiss}
              className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Dismiss briefing"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Items */}
        <div className="space-y-3">
          {data!.items.map((item) => {
            const action = inferActionLink(item, data!.primary_area);
            return (
              <div
                key={item.number}
                className={cn(
                  "flex items-start gap-3 pl-2 py-1",
                  item.priority === "critical" && "border-l-2 border-l-red-500",
                  item.priority === "warning" && "border-l-2 border-l-amber-500",
                )}
              >
                <span className="text-xs font-medium text-gray-400 mt-0.5 shrink-0 w-4 text-right">
                  {item.number}.
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {item.text}
                    {item.priority === "info" &&
                      item.text.toLowerCase().includes("assigned") &&
                      !action && (
                        <span className="ml-1 text-green-600">
                          <Check className="inline h-3.5 w-3.5" />
                        </span>
                      )}
                  </p>
                </div>
                {action && (
                  <Link
                    to={action.route}
                    className="shrink-0 text-xs font-medium text-blue-600 hover:text-blue-800 flex items-center gap-0.5 mt-0.5 whitespace-nowrap"
                  >
                    {action.label}
                    <ChevronRight className="h-3 w-3" />
                  </Link>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer / Refresh */}
        <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
          <div className="text-xs text-gray-400">
            {data!.was_cached && (
              <span>Generated at {formatTime(data!.generated_at)} &middot; </span>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
            className="h-7 text-xs text-gray-500 hover:text-gray-700 gap-1.5"
          >
            <RefreshCw className={cn("h-3 w-3", refreshing && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
