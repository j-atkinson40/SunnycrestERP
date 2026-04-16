import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Popover } from "@base-ui/react/popover";
import { MapPin, ChevronDown, Check, AlertTriangle } from "lucide-react";
import { useLocations } from "@/contexts/location-context";
import apiClient from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface LocationStat {
  location_id: string;
  status: "attention_needed" | "on_track" | "no_activity";
  active_orders: number;
  pending_deliveries: number;
}

function StatusDot({ status }: { status: "attention_needed" | "on_track" | "no_activity" | undefined }) {
  if (!status || status === "no_activity") {
    return <span className="inline-block size-1.5 rounded-full bg-muted-foreground/30" title="No activity" />;
  }
  if (status === "attention_needed") {
    return <AlertTriangle className="size-3 text-amber-500 shrink-0" />;
  }
  return <Check className="size-3 text-green-500 shrink-0" />;
}

// Renders null for single-location companies — critical rule
export function LocationSelector() {
  const { accessibleLocations, selectedLocationId, isMultiLocation, setSelectedLocation, loading } =
    useLocations();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [stats, setStats] = useState<LocationStat[]>([]);
  const [statsLoading, setStatsLoading] = useState(false);

  // Single-location or loading: render nothing
  if (loading || !isMultiLocation) return null;

  const selectedLocation = accessibleLocations.find((l) => l.id === selectedLocationId) ?? null;

  function handleOpen(nextOpen: boolean) {
    setOpen(nextOpen);
    if (nextOpen && stats.length === 0) {
      setStatsLoading(true);
      apiClient
        .get("/locations/overview")
        .then((r) => {
          const items: LocationStat[] = (r.data?.locations ?? []).map(
            (loc: { id: string; status: string; stats?: { active_orders?: number; pending_deliveries?: number } }) => ({
              location_id: loc.id,
              status: loc.status as LocationStat["status"],
              active_orders: loc.stats?.active_orders ?? 0,
              pending_deliveries: loc.stats?.pending_deliveries ?? 0,
            })
          );
          setStats(items);
        })
        .catch(() => setStats([]))
        .finally(() => setStatsLoading(false));
    }
  }

  function statFor(id: string): LocationStat | undefined {
    return stats.find((s) => s.location_id === id);
  }

  return (
    <Popover.Root open={open} onOpenChange={handleOpen}>
      <Popover.Trigger
        render={
          <button
            type="button"
            className={cn(
              "flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-sm",
              "text-sidebar-foreground/80 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
              "border border-transparent hover:border-sidebar-border transition-colors",
              "cursor-pointer",
            )}
          />
        }
      >
        <MapPin className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="flex-1 truncate text-left text-xs">
          {selectedLocation ? selectedLocation.name : "All Locations"}
        </span>
        <ChevronDown className="size-3 shrink-0 text-muted-foreground/50" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner
          className="z-50 outline-none"
          side="bottom"
          align="start"
          sideOffset={4}
        >
          <Popover.Popup className="w-60 rounded-lg border bg-popover text-popover-foreground shadow-md">
            <div className="border-b px-3 py-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Location
              </span>
            </div>
            <div className="max-h-64 overflow-y-auto py-1">
              {/* All Locations option */}
              <button
                type="button"
                onClick={() => {
                  setSelectedLocation(null);
                  setOpen(false);
                  navigate("/locations");
                }}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-1.5 text-sm text-left hover:bg-muted/50 transition-colors",
                  selectedLocationId === null && "font-medium text-foreground",
                )}
              >
                <MapPin className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate">All Locations</span>
                {selectedLocationId === null && (
                  <Check className="size-3.5 text-primary shrink-0" />
                )}
              </button>

              {/* Divider */}
              <div className="my-1 border-t" />

              {/* Individual locations */}
              {statsLoading ? (
                <div className="px-3 py-2 text-xs text-muted-foreground">Loading...</div>
              ) : (
                accessibleLocations.map((loc) => {
                  const stat = statFor(loc.id);
                  const isSelected = selectedLocationId === loc.id;
                  return (
                    <button
                      key={loc.id}
                      type="button"
                      onClick={() => {
                        setSelectedLocation(loc.id);
                        setOpen(false);
                      }}
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-1.5 text-sm text-left hover:bg-muted/50 transition-colors",
                        isSelected && "font-medium text-foreground",
                      )}
                    >
                      <StatusDot status={stat?.status} />
                      <div className="flex-1 min-w-0">
                        <div className="truncate text-sm">{loc.name}</div>
                        {(loc.city || loc.state) && (
                          <div className="truncate text-xs text-muted-foreground">
                            {[loc.city, loc.state].filter(Boolean).join(", ")}
                          </div>
                        )}
                      </div>
                      {isSelected && (
                        <Check className="size-3.5 text-primary shrink-0" />
                      )}
                    </button>
                  );
                })
              )}
            </div>
            <div className="border-t">
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  navigate("/locations");
                }}
                className="w-full px-3 py-2 text-center text-xs text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
              >
                View all locations
              </button>
            </div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
