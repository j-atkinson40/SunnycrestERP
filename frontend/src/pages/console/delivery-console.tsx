/**
 * Delivery Console — Mobile-optimized driver view
 *
 * Shows assigned deliveries for the current day with:
 * - Rich order cards with funeral-specific data
 * - "On My Way" / "Mark Delivered" status flow
 * - Two-tap confirmation for completion
 * - Native maps navigation via address link
 * - Next-day preview after cutoff time
 * - Time-aware greeting in empty states
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import api from "@/lib/api-client";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Milestone settings — loaded once on mount
// ---------------------------------------------------------------------------

interface MilestoneSettings {
  milestone_on_my_way_enabled: boolean;
  milestone_arrived_enabled: boolean;
  milestone_delivered_enabled: boolean;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ConsoleDelivery {
  delivery_id: string;
  delivery_type: string;
  status: string;
  priority: string;
  delivery_address: string | null;
  delivery_lat: string | null;
  delivery_lng: string | null;
  requested_date: string | null;
  required_window_start: string | null;
  required_window_end: string | null;
  special_instructions: string | null;
  customer_name: string | null;
  order_id: string | null;
  completed_at: string | null;
  // Funeral-specific
  family_name: string;
  cemetery_name: string;
  funeral_home_name: string;
  service_time: string;
  service_time_display: string;
  vault_type: string;
  vault_personalization: string;
  hours_until_service: number | null;
  is_critical: boolean;
  is_warning: boolean;
  // Stop
  stop_id: string | null;
  stop_status: string | null;
  sequence_number: number | null;
  actual_arrival: string | null;
  actual_departure: string | null;
  driver_notes: string | null;
}

interface AncillaryItem {
  delivery_id: string;
  delivery_type: string;
  order_type_label: string;
  funeral_home_name: string;
  product_summary: string;
  deceased_name: string;
  ancillary_fulfillment_status: string;
  special_instructions: string | null;
}

interface ConsoleResponse {
  date: string;
  driver_id: string;
  driver_name: string;
  route_id: string | null;
  route_status: string | null;
  deliveries: ConsoleDelivery[];
  ancillary_items?: AncillaryItem[];
  stats: {
    total: number;
    completed: number;
    remaining: number;
    in_progress: number;
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function formatDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function getDirectionsUrl(address: string, lat?: string | null, lng?: string | null): string {
  // Prefer coordinates for precision, fallback to address
  if (lat && lng) {
    // iOS Safari + Google Maps both support this format
    return `https://maps.google.com/maps?daddr=${lat},${lng}`;
  }
  return `https://maps.google.com/maps?daddr=${encodeURIComponent(address)}`;
}

function getStatusLabel(stopStatus: string | null, deliveryStatus: string): string {
  if (stopStatus === "completed" || deliveryStatus === "completed") return "Delivered";
  if (stopStatus === "arrived" || deliveryStatus === "arrived") return "On Site";
  if (stopStatus === "en_route" || deliveryStatus === "in_transit") return "En Route";
  if (deliveryStatus === "scheduled" || stopStatus === "pending") return "Scheduled";
  return deliveryStatus;
}

function getStatusColor(stopStatus: string | null, deliveryStatus: string): string {
  if (stopStatus === "completed" || deliveryStatus === "completed")
    return "bg-emerald-100 text-emerald-700 border-emerald-200";
  if (stopStatus === "arrived" || deliveryStatus === "arrived")
    return "bg-blue-100 text-blue-700 border-blue-200";
  if (stopStatus === "en_route" || deliveryStatus === "in_transit")
    return "bg-amber-100 text-amber-700 border-amber-200";
  return "bg-slate-100 text-slate-600 border-slate-200";
}

// ---------------------------------------------------------------------------
// DeliveryCard component
// ---------------------------------------------------------------------------

function DeliveryCard({
  card,
  onStatusUpdate,
  isUpdating,
  milestones,
}: {
  card: ConsoleDelivery;
  onStatusUpdate: (deliveryId: string, newStatus: string) => void;
  isUpdating: boolean;
  milestones: MilestoneSettings;
}) {
  const [confirmingComplete, setConfirmingComplete] = useState(false);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isCompleted = card.stop_status === "completed" || card.status === "completed";
  const isEnRoute = card.stop_status === "en_route" || card.status === "in_transit";
  const isArrived = card.stop_status === "arrived" || card.status === "arrived";

  // Auto-dismiss confirmation after 5 seconds
  useEffect(() => {
    if (confirmingComplete) {
      confirmTimerRef.current = setTimeout(() => {
        setConfirmingComplete(false);
      }, 5000);
    }
    return () => {
      if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    };
  }, [confirmingComplete]);

  // Determine the next available status based on milestone settings.
  // If a milestone is disabled, its step is skipped entirely.
  const getNextStatus = useCallback((): string | null => {
    if (isCompleted) return null;

    if (!isEnRoute && !isArrived) {
      // Scheduled → first enabled step
      if (milestones.milestone_on_my_way_enabled) return "en_route";
      if (milestones.milestone_arrived_enabled) return "arrived";
      if (milestones.milestone_delivered_enabled) return "completed";
      return null; // all disabled — no action available
    }
    if (isEnRoute) {
      if (milestones.milestone_arrived_enabled) return "arrived";
      if (milestones.milestone_delivered_enabled) return "completed";
      return null;
    }
    if (isArrived) {
      if (milestones.milestone_delivered_enabled) return "completed";
      return null;
    }
    return null;
  }, [isCompleted, isEnRoute, isArrived, milestones]);

  const handlePrimaryAction = useCallback(() => {
    const nextStatus = getNextStatus();
    if (!nextStatus) return;

    if (nextStatus === "completed") {
      if (!confirmingComplete) {
        setConfirmingComplete(true);
      } else {
        setConfirmingComplete(false);
        onStatusUpdate(card.delivery_id, "completed");
      }
    } else {
      onStatusUpdate(card.delivery_id, nextStatus);
    }
  }, [getNextStatus, confirmingComplete, card.delivery_id, onStatusUpdate]);

  const getPrimaryButtonText = (): string => {
    if (isCompleted) return "Delivered";
    const nextStatus = getNextStatus();
    if (!nextStatus) return "Delivered"; // fallback — shouldn't render
    if (nextStatus === "en_route") return "On My Way";
    if (nextStatus === "arrived") return isEnRoute ? "I've Arrived" : "I've Arrived";
    if (nextStatus === "completed" && confirmingComplete) return "Tap Again to Confirm";
    if (nextStatus === "completed") return isArrived ? "Mark Delivered" : "Mark Delivered";
    return "Update";
  };

  const getPrimaryButtonStyle = (): string => {
    if (isCompleted) return "bg-emerald-600 text-white opacity-60 cursor-not-allowed";
    const nextStatus = getNextStatus();
    if (nextStatus === "completed" && confirmingComplete) return "bg-red-600 text-white animate-pulse";
    if (nextStatus === "completed") return "bg-emerald-600 text-white active:bg-emerald-700";
    if (nextStatus === "arrived") return "bg-blue-600 text-white active:bg-blue-700";
    if (nextStatus === "en_route") return "bg-indigo-600 text-white active:bg-indigo-700";
    return "bg-indigo-600 text-white active:bg-indigo-700";
  };

  const hasAction = isCompleted || getNextStatus() !== null;

  return (
    <div
      className={cn(
        "rounded-xl border shadow-sm transition-all",
        isCompleted
          ? "border-emerald-200 bg-emerald-50/50 opacity-75"
          : card.is_critical
            ? "border-red-300 bg-red-50/30"
            : card.is_warning
              ? "border-amber-300 bg-amber-50/30"
              : "border-slate-200 bg-white",
      )}
    >
      {/* Card Header */}
      <div className="flex items-start justify-between gap-2 px-4 pt-4 pb-2">
        <div className="min-w-0 flex-1">
          {/* Sequence + Family */}
          <div className="flex items-center gap-2">
            {card.sequence_number && (
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-800 text-xs font-bold text-white">
                {card.sequence_number}
              </span>
            )}
            <h3 className="truncate text-base font-semibold text-slate-900">
              {card.family_name || card.customer_name || "Delivery"}
            </h3>
          </div>
          {/* Vault type */}
          {card.vault_type && (
            <p className="mt-0.5 text-sm text-slate-500">{card.vault_type}</p>
          )}
        </div>

        {/* Status badge */}
        <span
          className={cn(
            "shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-medium",
            getStatusColor(card.stop_status, card.status),
          )}
        >
          {getStatusLabel(card.stop_status, card.status)}
        </span>
      </div>

      {/* Card Body */}
      <div className="space-y-2 px-4 pb-3">
        {/* Service time + urgency */}
        {card.service_time_display && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-400">&#9716;</span>
            <span className="font-medium text-slate-700">
              Service at {card.service_time_display}
            </span>
            {card.hours_until_service !== null && !isCompleted && (
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-medium",
                  card.is_critical
                    ? "bg-red-100 text-red-700"
                    : card.is_warning
                      ? "bg-amber-100 text-amber-700"
                      : "bg-slate-100 text-slate-600",
                )}
              >
                {card.hours_until_service > 0
                  ? `${card.hours_until_service}h away`
                  : "Past due"}
              </span>
            )}
          </div>
        )}

        {/* Delivery window */}
        {(card.required_window_start || card.required_window_end) && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span>&#8987;</span>
            <span>
              {card.required_window_start && card.required_window_end
                ? `${card.required_window_start} - ${card.required_window_end}`
                : card.required_window_start
                  ? `After ${card.required_window_start}`
                  : `Before ${card.required_window_end}`}
            </span>
          </div>
        )}

        {/* Cemetery */}
        {card.cemetery_name && (
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <span className="text-slate-400">&#9961;</span>
            <span>{card.cemetery_name}</span>
          </div>
        )}

        {/* Funeral home */}
        {card.funeral_home_name && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span className="text-slate-400">&#9962;</span>
            <span>{card.funeral_home_name}</span>
          </div>
        )}

        {/* Personalization note */}
        {card.vault_personalization && (
          <div className="rounded-md bg-indigo-50 px-3 py-1.5 text-xs text-indigo-700">
            Personalization: {card.vault_personalization}
          </div>
        )}

        {/* Special instructions */}
        {card.special_instructions && (
          <div className="rounded-md bg-amber-50 px-3 py-1.5 text-xs text-amber-700">
            {card.special_instructions}
          </div>
        )}

        {/* Address + navigation */}
        {card.delivery_address && (
          <a
            href={getDirectionsUrl(card.delivery_address, card.delivery_lat, card.delivery_lng)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 active:bg-blue-100"
          >
            <span>&#128204;</span>
            <span className="flex-1 truncate">{card.delivery_address}</span>
            <span className="text-blue-500">&#8599;</span>
          </a>
        )}
      </div>

      {/* Action Button — only rendered when there's a valid next step */}
      {hasAction && (
        <div className="border-t px-4 py-3">
          <button
            onClick={handlePrimaryAction}
            disabled={isCompleted || isUpdating}
            className={cn(
              "w-full rounded-lg px-4 py-3 text-sm font-semibold transition-all",
              getPrimaryButtonStyle(),
              isUpdating && "opacity-50 cursor-wait",
            )}
          >
            {isUpdating ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Updating...
              </span>
            ) : (
              getPrimaryButtonText()
            )}
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stats Bar
// ---------------------------------------------------------------------------

function StatsBar({ stats }: { stats: ConsoleResponse["stats"] }) {
  if (stats.total === 0) return null;

  const progressPercent = stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      {/* Progress bar */}
      <div className="mb-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-500">
          {stats.completed} of {stats.total} completed
        </span>
        <span className="font-semibold text-slate-700">{progressPercent}%</span>
      </div>

      {stats.in_progress > 0 && (
        <p className="mt-1 text-xs text-blue-600">
          {stats.in_progress} in progress
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function EmptyState({ driverName }: { driverName: string }) {
  const firstName = driverName.split(" ")[0] || "there";
  const greeting = getGreeting();

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
      <div className="rounded-full bg-slate-100 p-5 text-4xl">
        &#128666;
      </div>
      <div>
        <h2 className="text-xl font-semibold text-slate-800">
          {greeting}, {firstName}!
        </h2>
        <p className="mt-1 max-w-xs text-sm text-slate-500">
          No deliveries scheduled for today. Enjoy the downtime!
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// All-Done State
// ---------------------------------------------------------------------------

function AllDoneState({ stats }: { stats: ConsoleResponse["stats"] }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 py-8 text-center">
      <div className="text-4xl">&#127881;</div>
      <h3 className="text-lg font-semibold text-emerald-800">All Done!</h3>
      <p className="text-sm text-emerald-600">
        All {stats.total} deliveries completed. Great work today!
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Next Day Preview
// ---------------------------------------------------------------------------

function NextDayPreview({
  nextDayData,
  isLoading,
}: {
  nextDayData: ConsoleResponse | null;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-4">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
          Loading tomorrow's schedule...
        </div>
      </div>
    );
  }

  if (!nextDayData || nextDayData.deliveries.length === 0) return null;

  return (
    <div className="mt-6 space-y-3">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
        Tomorrow's Preview
      </h3>
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/50 p-4">
        <p className="text-sm font-medium text-slate-600">
          {nextDayData.stats.total} delivery{nextDayData.stats.total !== 1 ? "ies" : "y"} scheduled
        </p>
        <div className="mt-2 space-y-1">
          {nextDayData.deliveries.slice(0, 3).map((d) => (
            <div key={d.delivery_id} className="flex items-center gap-2 text-xs text-slate-500">
              <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
              <span className="truncate">
                {d.family_name || d.customer_name || "Delivery"}{" "}
                {d.service_time_display && `@ ${d.service_time_display}`}
              </span>
            </div>
          ))}
          {nextDayData.deliveries.length > 3 && (
            <p className="text-xs text-slate-400">
              +{nextDayData.deliveries.length - 3} more
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function DeliveryConsolePage() {
  const { user } = useAuth();

  const [data, setData] = useState<ConsoleResponse | null>(null);
  const [nextDayData, setNextDayData] = useState<ConsoleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [nextDayLoading, setNextDayLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [milestones, setMilestones] = useState<MilestoneSettings>({
    milestone_on_my_way_enabled: true,
    milestone_arrived_enabled: true,
    milestone_delivered_enabled: true,
  });

  const todayStr = useMemo(() => formatDate(new Date()), []);

  // Fetch milestone settings once on mount
  useEffect(() => {
    api
      .get<MilestoneSettings>("/api/v1/driver/console/milestone-settings")
      .then((resp) => setMilestones(resp.data))
      .catch(() => {
        // Default to all enabled on error
      });
  }, []);

  // Fetch today's deliveries
  const fetchDeliveries = useCallback(async () => {
    try {
      const resp = await api.get<ConsoleResponse>("/api/v1/driver/console/deliveries", {
        params: { date: todayStr },
      });
      setData(resp.data);
      setError(null);
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? ((err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Failed to load deliveries")
          : "Failed to load deliveries";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [todayStr]);

  // Fetch next day preview
  const fetchNextDay = useCallback(async () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = formatDate(tomorrow);

    setNextDayLoading(true);
    try {
      const resp = await api.get<ConsoleResponse>("/api/v1/driver/console/deliveries", {
        params: { date: tomorrowStr },
      });
      setNextDayData(resp.data);
    } catch {
      // Non-critical — silently skip
    } finally {
      setNextDayLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDeliveries();
  }, [fetchDeliveries]);

  // Load next day preview after initial load if all done or after 3pm
  useEffect(() => {
    if (!data) return;
    const hour = new Date().getHours();
    const allDone = data.stats.total > 0 && data.stats.completed === data.stats.total;
    if (allDone || hour >= 15) {
      fetchNextDay();
    }
  }, [data, fetchNextDay]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(fetchDeliveries, 60_000);
    return () => clearInterval(interval);
  }, [fetchDeliveries]);

  // Status update handler
  const handleStatusUpdate = useCallback(
    async (deliveryId: string, newStatus: string) => {
      setUpdatingId(deliveryId);
      try {
        await api.patch(`/api/v1/driver/console/deliveries/${deliveryId}/status`, {
          status: newStatus,
        });
        // Refresh data
        await fetchDeliveries();
      } catch (err: unknown) {
        const msg =
          err && typeof err === "object" && "response" in err
            ? ((err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Update failed")
            : "Update failed";
        alert(msg);
      } finally {
        setUpdatingId(null);
      }
    },
    [fetchDeliveries],
  );

  // Ancillary delivery confirm handler
  const handleAncillaryConfirm = useCallback(
    async (deliveryId: string) => {
      setUpdatingId(deliveryId);
      try {
        await api.post(`/api/v1/driver/console/ancillary/${deliveryId}/confirm`);
        await fetchDeliveries();
      } catch {
        alert("Failed to confirm delivery");
      } finally {
        setUpdatingId(null);
      }
    },
    [fetchDeliveries],
  );

  // Loading state
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-3 border-slate-200 border-t-indigo-600" />
        <p className="text-sm text-slate-500">Loading your deliveries...</p>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <div className="rounded-full bg-red-100 p-4 text-3xl">&#9888;</div>
        <div>
          <h2 className="text-lg font-semibold text-slate-800">
            Couldn't load deliveries
          </h2>
          <p className="mt-1 max-w-xs text-sm text-slate-500">{error}</p>
        </div>
        <button
          onClick={() => {
            setLoading(true);
            setError(null);
            fetchDeliveries();
          }}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white active:bg-indigo-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const allDone = data.stats.total > 0 && data.stats.completed === data.stats.total;
  const driverName = data.driver_name || `${user?.first_name || ""} ${user?.last_name || ""}`;

  // Separate completed from active for ordering
  const activeCards = data.deliveries.filter(
    (d) => d.stop_status !== "completed" && d.status !== "completed",
  );
  const completedCards = data.deliveries.filter(
    (d) => d.stop_status === "completed" || d.status === "completed",
  );

  return (
    <div className="mx-auto max-w-lg space-y-4 pb-8">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-900">My Deliveries</h1>
        <p className="text-sm text-slate-500">
          {new Date().toLocaleDateString("en-US", {
            weekday: "long",
            month: "long",
            day: "numeric",
          })}
        </p>
      </div>

      {/* Stats */}
      {data.stats.total > 0 && <StatsBar stats={data.stats} />}

      {/* Empty state */}
      {data.stats.total === 0 && <EmptyState driverName={driverName} />}

      {/* All done banner */}
      {allDone && <AllDoneState stats={data.stats} />}

      {/* Active delivery cards */}
      {activeCards.length > 0 && (
        <div className="space-y-3">
          {activeCards.map((card) => (
            <DeliveryCard
              key={card.delivery_id}
              card={card}
              onStatusUpdate={handleStatusUpdate}
              isUpdating={updatingId === card.delivery_id}
              milestones={milestones}
            />
          ))}
        </div>
      )}

      {/* Ancillary items — "Also on your route today" */}
      {data.ancillary_items && data.ancillary_items.length > 0 && (
        <AncillarySection
          items={data.ancillary_items}
          onConfirm={handleAncillaryConfirm}
          updatingId={updatingId}
        />
      )}

      {/* Completed cards (collapsed section) */}
      {completedCards.length > 0 && !allDone && (
        <CompletedSection cards={completedCards} />
      )}

      {/* Next day preview */}
      <NextDayPreview nextDayData={nextDayData} isLoading={nextDayLoading} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ancillary Console Card — compact secondary item
// ---------------------------------------------------------------------------

function AncillaryConsoleCard({
  item,
  onConfirm,
  isUpdating,
}: {
  item: AncillaryItem;
  onConfirm: (deliveryId: string) => void;
  isUpdating: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isCompleted = item.ancillary_fulfillment_status === "completed";

  useEffect(() => {
    if (confirming) {
      confirmTimerRef.current = setTimeout(() => setConfirming(false), 5000);
    }
    return () => { if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current); };
  }, [confirming]);

  return (
    <div className={cn(
      "rounded-lg border px-3 py-2.5 space-y-1",
      isCompleted
        ? "border-emerald-200 bg-emerald-50/50 opacity-75"
        : "border-slate-200 bg-white",
    )}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900 truncate">
          {item.funeral_home_name || "Delivery"}
        </span>
        <span className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-500">
          {item.order_type_label}
        </span>
      </div>
      <p className="text-xs text-slate-600 truncate">
        {item.product_summary}
        {item.deceased_name ? ` \u00b7 ${item.deceased_name}` : ""}
      </p>
      {item.special_instructions && (
        <p className="text-[11px] text-amber-600 truncate">{item.special_instructions}</p>
      )}
      <div className="pt-1">
        {isCompleted ? (
          <span className="text-xs text-emerald-600 font-medium">&#10003; Dropped Off</span>
        ) : !confirming ? (
          <button
            onClick={() => setConfirming(true)}
            disabled={isUpdating}
            className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 active:bg-emerald-200 transition-colors"
          >
            &#10003; Dropped Off
          </button>
        ) : (
          <button
            onClick={() => {
              setConfirming(false);
              onConfirm(item.delivery_id);
            }}
            disabled={isUpdating}
            className="w-full rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white animate-pulse active:bg-emerald-700"
          >
            Tap Again to Confirm
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ancillary Section — "Also on your route today"
// ---------------------------------------------------------------------------

function AncillarySection({
  items,
  onConfirm,
  updatingId,
}: {
  items: AncillaryItem[];
  onConfirm: (deliveryId: string) => void;
  updatingId: string | null;
}) {
  const activeItems = items.filter((i) => i.ancillary_fulfillment_status !== "completed");
  const completedItems = items.filter((i) => i.ancillary_fulfillment_status === "completed");

  if (items.length === 0) return null;

  return (
    <div className="space-y-3">
      {/* Divider */}
      <div className="flex items-center gap-3 pt-2">
        <div className="h-px flex-1 bg-slate-300" />
        <span className="text-xs font-semibold text-slate-400 whitespace-nowrap">
          Also on your route today ({items.length} item{items.length !== 1 ? "s" : ""})
        </span>
        <div className="h-px flex-1 bg-slate-300" />
      </div>

      {/* Active ancillary items */}
      {activeItems.map((item) => (
        <AncillaryConsoleCard
          key={item.delivery_id}
          item={item}
          onConfirm={onConfirm}
          isUpdating={updatingId === item.delivery_id}
        />
      ))}

      {/* Completed ancillary items */}
      {completedItems.map((item) => (
        <AncillaryConsoleCard
          key={item.delivery_id}
          item={item}
          onConfirm={onConfirm}
          isUpdating={false}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Completed Section (collapsible)
// ---------------------------------------------------------------------------

function CompletedSection({ cards }: { cards: ConsoleDelivery[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="space-y-2">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between rounded-lg bg-slate-50 px-4 py-2.5 text-sm font-medium text-slate-500 active:bg-slate-100"
      >
        <span>Completed ({cards.length})</span>
        <span className="text-xs">{expanded ? "Hide" : "Show"}</span>
      </button>

      {expanded && (
        <div className="space-y-3">
          {cards.map((card) => (
            <DeliveryCard
              key={card.delivery_id}
              card={card}
              onStatusUpdate={() => {}}
              isUpdating={false}
              milestones={{ milestone_on_my_way_enabled: true, milestone_arrived_enabled: true, milestone_delivered_enabled: true }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
