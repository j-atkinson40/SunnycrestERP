/**
 * PortalDriverHome — Workflow Arc Phase 8e.2.
 *
 * Mounted at `/portal/:slug/driver` as the minimal portal-auth
 * driver home. Pulls the driver summary from the new portal-namespaced
 * endpoint (/api/v1/portal/drivers/me/summary) — thin router over
 * the existing delivery service layer.
 *
 * Phase 8e.2 scope: identity + today's stop count + a link into the
 * existing tenant-authed driver route UI (to keep scope bounded —
 * mounting the other 4 driver pages under portal routes lands in
 * Phase 8e.2.1).
 *
 * Phase 8e.2.1 will replace this with the full 5-page driver portal
 * stack (route view, stop detail, mileage, inspection).
 */

import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePortalAuth } from "@/contexts/portal-auth-context";
import { fetchPortalDriverSummary } from "@/services/portal-service";
import type { PortalDriverSummary } from "@/types/portal";

export default function PortalDriverHome() {
  const { me } = usePortalAuth();
  const [summary, setSummary] = useState<PortalDriverSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchPortalDriverSummary()
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load your driver summary.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      className="space-y-4 max-w-xl mx-auto"
      data-testid="portal-driver-home"
    >
      <div>
        <h1 className="text-h3 font-display font-medium text-content-strong">
          {summary ? `Hi, ${summary.driver_name.split(" ")[0]}` : `Hi${me ? `, ${me.first_name}` : ""}`}
        </h1>
        <p className="text-body-sm text-content-muted">
          Welcome to your {summary?.tenant_display_name ?? "driver"} portal.
        </p>
      </div>

      {error ? (
        <Alert variant="error">{error}</Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Today</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-body-sm text-content-muted">Loading…</div>
          ) : summary?.driver_id ? (
            <>
              <div
                className="flex items-baseline gap-2"
                data-testid="portal-driver-today-stops"
              >
                <span className="font-mono text-display-lg font-medium tabular-nums text-content-strong">
                  {summary.today_stops_count}
                </span>
                <span className="text-body-sm text-content-muted">
                  stop{summary.today_stops_count === 1 ? "" : "s"} scheduled
                </span>
              </div>
              <p className="mt-3 text-caption text-content-muted">
                Full route view + stop details coming in the next portal
                update. For now, reach out to dispatch if anything&rsquo;s
                unclear.
              </p>
            </>
          ) : (
            <Alert variant="info">
              Your account is set up but isn&rsquo;t linked to a driver
              record yet. Ask your dispatcher to finish provisioning — once
              linked, your route and stops will appear here.
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Placeholder for Phase 8e.2.1 — will mount the other 4 driver
          pages here via nav or inline content. For now, just a footer
          note. */}
      <p className="text-caption text-content-muted pt-4">
        Phase 8e.2 reconnaissance. Full driver portal experience
        (route, stop detail, mileage, vehicle inspection) lands in
        Phase 8e.2.1.
      </p>
    </div>
  );
}
