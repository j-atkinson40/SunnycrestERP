import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { driverService } from "@/services/driver-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { getDeliveryTypeBadgeClass, getDeliveryTypeName } from "@/lib/delivery-types";
import type { DeliveryRoute } from "@/types/delivery";

function routeStatusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    draft: { className: "bg-gray-100 text-gray-800", label: "Draft" },
    dispatched: { className: "bg-blue-100 text-blue-800", label: "Ready" },
    in_progress: { className: "bg-yellow-100 text-yellow-800", label: "In Progress" },
    completed: { className: "bg-green-100 text-green-800", label: "Completed" },
  };
  const info = map[status];
  if (info) return <Badge className={info.className}>{info.label}</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

export default function DriverHomePage() {
  const navigate = useNavigate();
  const [route, setRoute] = useState<DeliveryRoute | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [noProfile, setNoProfile] = useState(false);

  const loadRoute = useCallback(async () => {
    try {
      setLoading(true);
      const r = await driverService.getTodayRoute();
      setRoute(r);
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err);
      if (msg.toLowerCase().includes("no driver profile")) {
        setNoProfile(true);
      } else {
        toast.error(msg);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRoute();
  }, [loadRoute]);

  const handleStartRoute = async () => {
    try {
      setStarting(true);
      await driverService.startRoute();
      toast.success("Route started!");
      navigate("/driver/route");
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (noProfile) {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-xl font-bold">Driver Portal</h1>
        <Card className="p-6">
          <p className="text-muted-foreground">
            No driver profile is linked to your account. Please contact your dispatcher.
          </p>
        </Card>
      </div>
    );
  }

  if (!route) {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-xl font-bold">Today's Schedule</h1>
        <Card className="p-6">
          <p className="text-lg text-muted-foreground">No route scheduled for today</p>
          <p className="mt-1 text-sm text-muted-foreground">Check back later or contact dispatch.</p>
        </Card>
      </div>
    );
  }

  const completedStops = route.stops.filter((s) => s.status === "completed").length;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Today's Route</h1>

      {/* Summary Card */}
      <Card className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">
              {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
            </p>
            <div className="mt-1 flex items-center gap-2">
              {routeStatusBadge(route.status)}
              {route.vehicle_name && (
                <span className="text-sm text-muted-foreground">{route.vehicle_name}</span>
              )}
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold">{route.total_stops}</p>
            <p className="text-xs text-muted-foreground">stops</p>
          </div>
        </div>

        {/* Progress */}
        {route.stops.length > 0 && (
          <div className="mt-3">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{completedStops} completed</span>
              <span>{route.stops.length - completedStops} remaining</span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-green-500 transition-all"
                style={{
                  width: `${route.stops.length > 0 ? (completedStops / route.stops.length) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        )}
      </Card>

      {/* Action Button */}
      {route.status === "dispatched" && (
        <Button className="w-full py-6 text-lg" onClick={handleStartRoute} disabled={starting}>
          {starting ? "Starting..." : "Start Route"}
        </Button>
      )}
      {route.status === "in_progress" && (
        <Button className="w-full py-6 text-lg" onClick={() => navigate("/driver/route")}>
          Continue Route
        </Button>
      )}
      {route.status === "completed" && (
        <Card className="p-4 text-center">
          <p className="text-lg font-medium text-green-600">Route Complete!</p>
          <p className="text-sm text-muted-foreground">
            {route.total_mileage ? `${route.total_mileage} miles driven` : "Great work today."}
          </p>
        </Card>
      )}

      {/* Stop Preview */}
      {route.stops.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Stops</h2>
          <div className="space-y-2">
            {route.stops.map((stop, i) => (
              <Card
                key={stop.id}
                className={`p-3 ${stop.status === "completed" ? "opacity-50" : ""}`}
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {stop.delivery?.customer_name || "Delivery"}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {stop.delivery?.delivery_address || "No address"}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {stop.delivery && <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getDeliveryTypeBadgeClass(stop.delivery.delivery_type)}`}>{getDeliveryTypeName(stop.delivery.delivery_type)}</span>}
                    <Badge variant="outline" className="text-xs">
                      {stop.status}
                    </Badge>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
