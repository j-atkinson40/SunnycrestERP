import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle,
  Minus,
  MapPin,
  Package,
  Truck,
  ShieldAlert,
  Factory,
  ArrowUpDown,
} from "lucide-react";
import { useLocations } from "@/contexts/location-context";
import apiClient from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface LocationStats {
  active_orders: number;
  pending_deliveries: number;
  deliveries_today: number;
  overdue_compliance: number;
  production_scheduled: number;
}

interface LocationOverview {
  id: string;
  name: string;
  location_type: string;
  city?: string;
  state?: string;
  wilbert_territory_id?: string;
  status: "attention_needed" | "on_track" | "no_activity";
  stats: LocationStats;
}

interface OverviewResponse {
  locations: LocationOverview[];
  totals: {
    locations: number;
    orders: number;
    deliveries: number;
    overdue: number;
  };
}

type SortKey = "name" | "status" | "orders";

function StatusBadge({ status }: { status: LocationOverview["status"] }) {
  if (status === "attention_needed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
        <AlertTriangle className="size-3" />
        Attention needed
      </span>
    );
  }
  if (status === "on_track") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
        <CheckCircle className="size-3" />
        On track
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
      <Minus className="size-3" />
      No activity
    </span>
  );
}

function LocationTypeBadge({ type }: { type: string }) {
  const labels: Record<string, string> = {
    plant: "Plant",
    warehouse: "Warehouse",
    office: "Office",
    territory: "Territory",
  };
  return (
    <span className="rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
      {labels[type] ?? type}
    </span>
  );
}

export default function LocationsOverview() {
  const { isMultiLocation, setSelectedLocation } = useLocations();
  const navigate = useNavigate();
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("status");

  useEffect(() => {
    apiClient
      .get("/locations/overview")
      .then((r) => setData(r.data))
      .catch(() => setError("Failed to load locations"))
      .finally(() => setLoading(false));
  }, []);

  // If not multi-location, redirect to dashboard
  useEffect(() => {
    if (!loading && !isMultiLocation) {
      navigate("/dashboard", { replace: true });
    }
  }, [loading, isMultiLocation, navigate]);

  function sortedLocations(locations: LocationOverview[]): LocationOverview[] {
    const sorted = [...locations];
    switch (sortKey) {
      case "name":
        return sorted.sort((a, b) => a.name.localeCompare(b.name));
      case "status": {
        const order = { attention_needed: 0, on_track: 1, no_activity: 2 };
        return sorted.sort((a, b) => order[a.status] - order[b.status]);
      }
      case "orders":
        return sorted.sort(
          (a, b) => b.stats.active_orders - a.stats.active_orders
        );
    }
  }

  function handleViewLocation(loc: LocationOverview) {
    setSelectedLocation(loc.id);
    navigate("/dashboard");
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-sm text-muted-foreground">Loading locations...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6">
        <div className="rounded-md border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
          {error ?? "An unexpected error occurred."}
        </div>
      </div>
    );
  }

  const locations = sortedLocations(data.locations);
  const { totals } = data;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Locations</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Overview of all company locations and their current status.
        </p>
      </div>

      {/* Summary row */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/30 px-4 py-2.5">
        <span className="text-sm font-medium">
          {totals.locations} location{totals.locations !== 1 ? "s" : ""}
        </span>
        <span className="text-muted-foreground">·</span>
        <span className="text-sm text-muted-foreground">
          {totals.orders} active orders
        </span>
        <span className="text-muted-foreground">·</span>
        <span className="text-sm text-muted-foreground">
          {totals.deliveries} deliveries
        </span>
        {totals.overdue > 0 && (
          <>
            <span className="text-muted-foreground">·</span>
            <span className="inline-flex items-center gap-1 text-sm font-medium text-amber-600">
              <AlertTriangle className="size-3.5" />
              {totals.overdue} overdue
            </span>
          </>
        )}
      </div>

      {/* Sort controls */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Sort by:</span>
        {(["status", "name", "orders"] as SortKey[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setSortKey(key)}
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              sortKey === key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
            )}
          >
            <ArrowUpDown className="size-3" />
            {key === "status" ? "Status" : key === "name" ? "Name" : "Orders"}
          </button>
        ))}
      </div>

      {/* Location grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {locations.map((loc) => (
          <div
            key={loc.id}
            className={cn(
              "rounded-lg border bg-card p-5 shadow-sm transition-shadow hover:shadow-md",
              loc.status === "attention_needed" && "border-amber-200"
            )}
          >
            {/* Card header */}
            <div className="mb-3 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="truncate font-medium">{loc.name}</h3>
                  <LocationTypeBadge type={loc.location_type} />
                </div>
                {(loc.city || loc.state) && (
                  <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                    <MapPin className="size-3 shrink-0" />
                    {[loc.city, loc.state].filter(Boolean).join(", ")}
                  </p>
                )}
                {loc.wilbert_territory_id && (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Territory: {loc.wilbert_territory_id}
                  </p>
                )}
              </div>
              <StatusBadge status={loc.status} />
            </div>

            {/* Stats grid */}
            <div className="mb-4 grid grid-cols-2 gap-2">
              <div className="rounded-md bg-muted/40 p-2.5">
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <Package className="size-3.5" />
                  <span className="text-[11px]">Active orders</span>
                </div>
                <div className="mt-0.5 text-lg font-semibold">
                  {loc.stats.active_orders}
                </div>
              </div>
              <div className="rounded-md bg-muted/40 p-2.5">
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <Truck className="size-3.5" />
                  <span className="text-[11px]">Deliveries today</span>
                </div>
                <div className="mt-0.5 text-lg font-semibold">
                  {loc.stats.deliveries_today}
                </div>
              </div>
              <div className="rounded-md bg-muted/40 p-2.5">
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <ShieldAlert className="size-3.5" />
                  <span className="text-[11px]">Overdue compliance</span>
                </div>
                <div
                  className={cn(
                    "mt-0.5 text-lg font-semibold",
                    loc.stats.overdue_compliance > 0 && "text-amber-600"
                  )}
                >
                  {loc.stats.overdue_compliance}
                </div>
              </div>
              <div className="rounded-md bg-muted/40 p-2.5">
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <Factory className="size-3.5" />
                  <span className="text-[11px]">Production scheduled</span>
                </div>
                <div className="mt-0.5 text-lg font-semibold">
                  {loc.stats.production_scheduled}
                </div>
              </div>
            </div>

            {/* View button */}
            <button
              type="button"
              onClick={() => handleViewLocation(loc)}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted/50"
            >
              View Location →
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
