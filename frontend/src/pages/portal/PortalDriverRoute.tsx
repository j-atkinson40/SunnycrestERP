/**
 * PortalDriverRoute — Workflow Arc Phase 8e.2.1.
 *
 * Today's delivery route for the portal-authed driver. Mounted at
 * `/portal/<slug>/driver/route`. Mobile-first single-column list
 * with tap-to-detail on each stop.
 *
 * Data source: `/api/v1/portal/drivers/me/route` (thin router over
 * existing driver_mobile_service). See SPACES_ARCHITECTURE.md §10.7
 * for the canonical portal-over-existing-service pattern.
 */

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronRight, MapPin, Truck } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatusPill } from "@/components/ui/status-pill";
import { fetchTodayRoute } from "@/services/portal-service";
import type { PortalRoute } from "@/types/portal";

export default function PortalDriverRoute() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [route, setRoute] = useState<PortalRoute | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void fetchTodayRoute()
      .then((r) => {
        if (!cancelled) setRoute(r);
      })
      .catch((err) => {
        if (cancelled) return;
        const e = err as { response?: { status?: number; data?: { detail?: string } } };
        if (e?.response?.status === 404) {
          setError(e?.response?.data?.detail ?? "No route scheduled.");
        } else if (!navigator.onLine) {
          setError("No connection. Try again when signal returns.");
        } else {
          setError("Couldn't load today's route.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <div className="text-body-sm text-content-muted">Loading route…</div>;
  }

  if (error) {
    return <Alert variant="info" data-testid="portal-route-error">{error}</Alert>;
  }

  if (!route || route.stops.length === 0) {
    return (
      <Alert variant="info" data-testid="portal-route-empty">
        No stops scheduled for today.
      </Alert>
    );
  }

  return (
    <div className="space-y-4" data-testid="portal-driver-route">
      {/* Route summary header */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-body-sm text-content-muted">
            <Truck className="h-4 w-4" />
            <span>
              {route.vehicle_name ?? "No vehicle assigned"} — {route.total_stops}{" "}
              stop{route.total_stops === 1 ? "" : "s"}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Stop list */}
      <ul className="space-y-2">
        {route.stops.map((stop) => (
          <li key={stop.id}>
            <button
              type="button"
              onClick={() =>
                navigate(`/portal/${slug}/driver/stops/${stop.id}`)
              }
              className="block w-full rounded-md border border-border-subtle bg-surface-raised p-4 text-left shadow-level-1 transition-colors hover:bg-accent-subtle focus-ring-accent min-h-[88px]"
              data-testid={`portal-stop-${stop.id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-caption text-content-muted">
                      #{stop.sequence_number ?? "—"}
                    </span>
                    <span className="font-medium text-body text-content-strong truncate">
                      {stop.customer_name ?? "Stop"}
                    </span>
                  </div>
                  {stop.address && (
                    <div className="mt-1 flex items-center gap-1 text-body-sm text-content-muted">
                      <MapPin className="h-3 w-3 shrink-0" />
                      <span className="truncate">{stop.address}</span>
                    </div>
                  )}
                  <div className="mt-2">
                    <StatusPill
                      status={_statusToFamily(stop.status)}
                    >
                      {stop.status}
                    </StatusPill>
                  </div>
                </div>
                <ChevronRight className="h-5 w-5 shrink-0 text-content-muted" />
              </div>
            </button>
          </li>
        ))}
      </ul>

      {/* Mileage action */}
      <Button
        variant="outline"
        className="w-full h-11"
        onClick={() => navigate(`/portal/${slug}/driver/mileage`)}
        data-testid="portal-mileage-btn"
      >
        Log mileage
      </Button>
    </div>
  );
}


function _statusToFamily(
  status: string,
): "success" | "warning" | "error" | "info" | "neutral" {
  const s = status.toLowerCase();
  if (s === "delivered" || s === "completed") return "success";
  if (s === "exception" || s === "failed") return "error";
  if (s === "in_progress" || s === "en_route" || s === "arrived") return "info";
  if (s === "pending" || s === "scheduled") return "warning";
  return "neutral";
}
