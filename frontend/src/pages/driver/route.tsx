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

function stopStatusColor(status: string) {
  const map: Record<string, string> = {
    pending: "border-l-gray-300",
    en_route: "border-l-blue-500",
    arrived: "border-l-indigo-500",
    in_progress: "border-l-yellow-500",
    completed: "border-l-green-500",
    skipped: "border-l-red-400",
  };
  return map[status] || "border-l-gray-300";
}

export default function DriverRoutePage() {
  const navigate = useNavigate();
  const [route, setRoute] = useState<DeliveryRoute | null>(null);
  const [loading, setLoading] = useState(true);

  const loadRoute = useCallback(async () => {
    try {
      setLoading(true);
      const r = await driverService.getTodayRoute();
      setRoute(r);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRoute();
  }, [loadRoute]);

  const handleUpdateStop = async (stopId: string, newStatus: string) => {
    try {
      await driverService.updateStopStatus(stopId, newStatus);
      toast.success(`Stop marked as ${newStatus}`);
      loadRoute();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  };

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <p className="text-muted-foreground">Loading route...</p>
      </div>
    );
  }

  if (!route) {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-xl font-bold">Route</h1>
        <Card className="p-6">
          <p className="text-muted-foreground">No route for today.</p>
        </Card>
      </div>
    );
  }

  if (route.status === "draft" || route.status === "dispatched") {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-xl font-bold">Route</h1>
        <Card className="p-6">
          <p className="text-muted-foreground">
            Your route hasn't been started yet. Go to Home to start it.
          </p>
          <Button className="mt-3" onClick={() => navigate("/driver")}>
            Go to Home
          </Button>
        </Card>
      </div>
    );
  }

  const completedStops = route.stops.filter((s) => s.status === "completed").length;
  const nextStop = route.stops.find((s) => s.status !== "completed" && s.status !== "skipped");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Route Stops</h1>
        <span className="text-sm text-muted-foreground">
          {completedStops}/{route.stops.length}
        </span>
      </div>

      {/* Progress */}
      <div className="h-2 rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-green-500 transition-all"
          style={{
            width: `${route.stops.length > 0 ? (completedStops / route.stops.length) * 100 : 0}%`,
          }}
        />
      </div>

      {/* Stops */}
      <div className="space-y-3">
        {route.stops.map((stop, i) => {
          const isNext = nextStop?.id === stop.id;
          const isCompleted = stop.status === "completed";

          return (
            <Card
              key={stop.id}
              className={`border-l-4 p-4 ${stopStatusColor(stop.status)} ${isCompleted ? "opacity-50" : ""} ${isNext ? "ring-2 ring-primary/30" : ""}`}
            >
              <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold">
                      {i + 1}
                    </span>
                    <span className="font-medium">
                      {stop.delivery?.customer_name || "Delivery"}
                    </span>
                    {stop.delivery && <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getDeliveryTypeBadgeClass(stop.delivery.delivery_type)}`}>{getDeliveryTypeName(stop.delivery.delivery_type)}</span>}
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {stop.delivery?.delivery_address || "No address"}
                  </p>
                  {stop.delivery?.priority === "urgent" && (
                    <Badge variant="destructive" className="mt-1">Urgent</Badge>
                  )}
                  {stop.driver_notes && (
                    <p className="mt-1 text-xs italic text-muted-foreground">
                      Note: {stop.driver_notes}
                    </p>
                  )}
                </div>
                <Badge variant="outline" className="shrink-0 text-xs">
                  {stop.status}
                </Badge>
              </div>

              {/* Actions — only for non-completed stops */}
              {!isCompleted && (
                <div className="mt-3 flex gap-2">
                  {stop.status === "pending" && (
                    <Button
                      size="sm"
                      className="flex-1"
                      onClick={() => navigate(`/driver/stops/${stop.id}`)}
                    >
                      Start Stop
                    </Button>
                  )}
                  {stop.status === "en_route" && (
                    <Button
                      size="sm"
                      className="flex-1"
                      onClick={() => handleUpdateStop(stop.id, "arrived")}
                    >
                      Mark Arrived
                    </Button>
                  )}
                  {(stop.status === "arrived" || stop.status === "in_progress") && (
                    <Button
                      size="sm"
                      className="flex-1"
                      onClick={() => navigate(`/driver/stops/${stop.id}`)}
                    >
                      View Details
                    </Button>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {/* Complete Route */}
      {completedStops === route.stops.length && route.stops.length > 0 && (
        <Button
          className="w-full py-6 text-lg"
          onClick={() => navigate("/driver/mileage")}
        >
          Complete Route
        </Button>
      )}
    </div>
  );
}
