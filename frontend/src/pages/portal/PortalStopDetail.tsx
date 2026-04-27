/**
 * PortalStopDetail — Workflow Arc Phase 8e.2.1.
 *
 * Per-stop detail for the portal-authed driver. Mounted at
 * `/portal/<slug>/driver/stops/:stopId`. Shows address + contacts,
 * lets driver mark status transitions + exceptions.
 *
 * Mobile-first: large action buttons, minimal chrome, clear status
 * indicators. Touch targets ≥ 44px per WCAG 2.2.
 */

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, MapPin, Phone } from "lucide-react";
import { toast } from "sonner";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusPill } from "@/components/ui/status-pill";
import { Textarea } from "@/components/ui/textarea";
import {
  fetchStop,
  markStopException,
  updateStopStatus,
} from "@/services/portal-service";
import type { PortalRouteStop } from "@/types/portal";

const EXCEPTION_REASONS: { value: string; label: string }[] = [
  { value: "customer_not_home", label: "Customer not home" },
  { value: "wrong_address", label: "Wrong address" },
  { value: "access_blocked", label: "Access blocked" },
  { value: "vehicle_issue", label: "Vehicle issue" },
  { value: "other", label: "Other" },
];

export default function PortalStopDetail() {
  const { slug, stopId } = useParams<{ slug: string; stopId: string }>();
  const navigate = useNavigate();
  const [stop, setStop] = useState<PortalRouteStop | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exceptionOpen, setExceptionOpen] = useState(false);
  const [reason, setReason] = useState<string>("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function reload() {
    if (!stopId) return;
    setLoading(true);
    setError(null);
    try {
      const s = await fetchStop(stopId);
      setStop(s);
    } catch (err) {
      if (!navigator.onLine) {
        setError("No connection. Try again when signal returns.");
      } else {
        setError("Couldn't load stop.");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stopId]);

  async function handleStatusUpdate(newStatus: string) {
    if (!stopId) return;
    setBusy(true);
    try {
      const updated = await updateStopStatus(stopId, { status: newStatus });
      setStop(updated);
      toast.success(`Stop marked ${newStatus}.`);
    } catch (err) {
      if (!navigator.onLine) {
        toast.error("No connection. Try again when signal returns.", {
          duration: 8000,
        });
      } else {
        toast.error("Couldn't save. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleExceptionSubmit() {
    if (!stopId || !reason) return;
    setBusy(true);
    try {
      await markStopException(stopId, {
        reason_code: reason,
        note: note.trim() || null,
      });
      toast.success("Exception recorded.");
      setExceptionOpen(false);
      setReason("");
      setNote("");
      await reload();
    } catch (err) {
      if (!navigator.onLine) {
        toast.error("No connection. Try again when signal returns.", {
          duration: 8000,
        });
      } else {
        toast.error("Couldn't save exception.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <div className="text-body-sm text-content-muted">Loading stop…</div>;
  }
  if (error || !stop) {
    return (
      <div className="space-y-3">
        <Alert variant="error">{error ?? "Stop not found."}</Alert>
        <Button
          variant="outline"
          className="h-11"
          onClick={() => navigate(`/portal/${slug}/driver/route`)}
        >
          <ArrowLeft className="mr-1.5 h-4 w-4" />
          Back to route
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="portal-stop-detail">
      <Button
        variant="ghost"
        size="sm"
        className="h-11 -ml-2"
        onClick={() => navigate(`/portal/${slug}/driver/route`)}
      >
        <ArrowLeft className="mr-1.5 h-4 w-4" />
        Back to route
      </Button>

      <div>
        <h1 className="text-h3 font-display font-medium text-content-strong">
          {stop.customer_name ?? "Stop"}
        </h1>
        <div className="mt-2">
          <StatusPill status={_stop_status_family(stop.status)}>
            {stop.status}
          </StatusPill>
        </div>
      </div>

      {stop.address && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-start gap-2">
              <MapPin className="h-4 w-4 mt-0.5 shrink-0 text-content-muted" />
              <div className="flex-1">
                <div className="text-body">{stop.address}</div>
                <a
                  href={`https://maps.google.com/?q=${encodeURIComponent(stop.address)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-block text-caption text-accent hover:underline"
                >
                  Open in Maps →
                </a>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {(stop.cemetery_contact || stop.funeral_home_contact) && (
        <Card>
          <CardContent className="p-4 space-y-2">
            {stop.cemetery_contact && (
              <div className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-content-muted" />
                <span className="text-body-sm">
                  <span className="text-content-muted">Cemetery:</span>{" "}
                  {stop.cemetery_contact}
                </span>
              </div>
            )}
            {stop.funeral_home_contact && (
              <div className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-content-muted" />
                <span className="text-body-sm">
                  <span className="text-content-muted">FH:</span>{" "}
                  {stop.funeral_home_contact}
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {stop.notes && (
        <Card>
          <CardContent className="p-4">
            <div className="text-caption text-content-muted uppercase tracking-wider mb-1">
              Notes
            </div>
            <div className="whitespace-pre-wrap text-body-sm">{stop.notes}</div>
          </CardContent>
        </Card>
      )}

      {/* Action buttons — large, mobile-first */}
      <div className="space-y-2 pt-4">
        <Button
          className="w-full h-12"
          onClick={() => handleStatusUpdate("delivered")}
          disabled={busy || stop.status === "delivered"}
          data-testid="mark-delivered-btn"
        >
          Mark delivered
        </Button>
        <Button
          variant="outline"
          className="w-full h-12"
          onClick={() => handleStatusUpdate("arrived")}
          disabled={busy || stop.status === "delivered"}
        >
          Mark arrived
        </Button>
        <Button
          variant="outline"
          className="w-full h-12 text-status-error border-status-error/30"
          onClick={() => setExceptionOpen(true)}
          disabled={busy}
          data-testid="mark-exception-btn"
        >
          Report exception
        </Button>
      </div>

      {/* Exception dialog */}
      <Dialog open={exceptionOpen} onOpenChange={setExceptionOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Report an exception</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label>Reason</Label>
              <Select value={reason} onValueChange={(v) => setReason(v ?? "")}>
                <SelectTrigger className="h-11">
                  <SelectValue placeholder="Pick a reason…" />
                </SelectTrigger>
                <SelectContent>
                  {EXCEPTION_REASONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Note (optional)</Label>
              <Textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setExceptionOpen(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              onClick={handleExceptionSubmit}
              disabled={busy || !reason}
              className="h-11"
              data-testid="submit-exception-btn"
            >
              Submit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}


function _stop_status_family(
  status: string,
): "success" | "warning" | "error" | "info" | "neutral" {
  const s = status.toLowerCase();
  if (s === "delivered" || s === "completed") return "success";
  if (s === "exception" || s === "failed") return "error";
  if (s === "arrived" || s === "in_progress" || s === "en_route") return "info";
  if (s === "pending" || s === "scheduled") return "warning";
  return "neutral";
}
