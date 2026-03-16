import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { driverService } from "@/services/driver-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { getDeliveryTypeBadgeClass, getDeliveryTypeName, getDeliveryType } from "@/lib/delivery-types";
import type { DeliveryRoute, DeliveryStop } from "@/types/delivery";

export default function StopDetailPage() {
  const { stopId } = useParams<{ stopId: string }>();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [, setRoute] = useState<DeliveryRoute | null>(null);
  const [stop, setStop] = useState<DeliveryStop | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notes, setNotes] = useState("");
  const [issueText, setIssueText] = useState("");
  const [showIssue, setShowIssue] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const r = await driverService.getTodayRoute();
      if (r) {
        setRoute(r);
        const s = r.stops.find((s) => s.id === stopId);
        setStop(s || null);
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [stopId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleStatusUpdate = async (newStatus: string) => {
    if (!stopId) return;
    try {
      setUpdating(true);
      await driverService.updateStopStatus(stopId, newStatus, notes || undefined);
      toast.success(`Stop marked as ${newStatus}`);
      if (newStatus === "completed") {
        navigate("/driver/route");
      } else {
        loadData();
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setUpdating(false);
    }
  };

  const handlePostEvent = async (eventType: string, eventNotes?: string) => {
    if (!stop?.delivery_id) return;
    try {
      await driverService.postEvent({
        delivery_id: stop.delivery_id,
        event_type: eventType,
        source: "driver",
        notes: eventNotes,
      });
      toast.success(`Event "${eventType}" recorded`);
      loadData();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  };

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !stop?.delivery_id) return;
    try {
      setUploading(true);
      await driverService.uploadMedia(stop.delivery_id, "photo", file);
      toast.success("Photo uploaded");
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleReportIssue = async () => {
    if (!issueText.trim()) return;
    await handlePostEvent("issue_reported", issueText);
    setShowIssue(false);
    setIssueText("");
  };

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!stop || !stop.delivery) {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-xl font-bold">Stop Not Found</h1>
        <Button onClick={() => navigate("/driver/route")}>Back to Route</Button>
      </div>
    );
  }

  const deliveryType = stop.delivery.delivery_type;
  const dtConfig = getDeliveryType(deliveryType);
  const isFuneral = deliveryType === "funeral_vault";

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => navigate("/driver/route")}>
        &larr; Back to Route
      </Button>

      {/* Stop Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold">
            {stop.delivery.customer_name || "Delivery"}
          </h1>
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getDeliveryTypeBadgeClass(deliveryType)}`}>{getDeliveryTypeName(deliveryType)}</span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {stop.delivery.delivery_address || "No address"}
        </p>
        <div className="mt-1 flex items-center gap-2">
          <Badge variant="outline">{stop.status}</Badge>
          {stop.delivery.priority === "urgent" && (
            <Badge variant="destructive">Urgent</Badge>
          )}
        </div>
      </div>

      {/* Type-Specific Info */}
      {(() => {
        return dtConfig.driver_instructions ? (
          <section className="rounded-lg border p-4">
            <h3 className="mb-2 font-semibold">{dtConfig.name} Delivery</h3>
            <p className="text-sm text-gray-600 whitespace-pre-line">{dtConfig.driver_instructions}</p>
          </section>
        ) : null;
      })()}

      {/* Actions by Status */}
      <Card className="space-y-3 p-4">
        <h3 className="font-semibold">Actions</h3>

        {stop.status === "pending" && (
          <Button
            className="w-full"
            onClick={() => handleStatusUpdate("en_route")}
            disabled={updating}
          >
            Mark En Route
          </Button>
        )}

        {stop.status === "en_route" && (
          <Button
            className="w-full"
            onClick={() => handleStatusUpdate("arrived")}
            disabled={updating}
          >
            Mark Arrived
          </Button>
        )}

        {stop.status === "arrived" && (
          <>
            {/* Photo capture */}
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handlePhotoUpload}
                className="hidden"
              />
              <Button
                variant="outline"
                className="w-full"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? "Uploading..." : "Take Arrival Photo"}
              </Button>
            </div>

            {isFuneral && (
              <Button
                className="w-full"
                onClick={() => {
                  handlePostEvent("setup_started");
                  handleStatusUpdate("in_progress");
                }}
                disabled={updating}
              >
                Begin Setup
              </Button>
            )}

            {!isFuneral && (
              <Button
                className="w-full"
                onClick={() => handleStatusUpdate("in_progress")}
                disabled={updating}
              >
                Begin Delivery
              </Button>
            )}
          </>
        )}

        {stop.status === "in_progress" && (
          <>
            {/* Photo capture */}
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handlePhotoUpload}
                className="hidden"
              />
              <Button
                variant="outline"
                className="w-full"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? "Uploading..." : "Take Photo"}
              </Button>
            </div>

            {isFuneral && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => handlePostEvent("setup_complete")}
              >
                Confirm Setup Complete
              </Button>
            )}

            <div className="space-y-1.5">
              <Label className="text-xs">Driver Notes</Label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Optional notes"
              />
            </div>

            <Button
              className="w-full bg-green-600 hover:bg-green-700"
              onClick={() => handleStatusUpdate("completed")}
              disabled={updating}
            >
              {updating ? "Completing..." : "Mark Complete"}
            </Button>
          </>
        )}
      </Card>

      {/* Issue Reporting */}
      {stop.status !== "completed" && (
        <Card className="p-4">
          {!showIssue ? (
            <Button
              variant="outline"
              className="w-full text-red-600"
              onClick={() => setShowIssue(true)}
            >
              Report Issue
            </Button>
          ) : (
            <div className="space-y-3">
              <Label className="text-sm font-medium">Describe the issue</Label>
              <textarea
                value={issueText}
                onChange={(e) => setIssueText(e.target.value)}
                rows={3}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="What went wrong?"
              />
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setShowIssue(false);
                    setIssueText("");
                  }}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={handleReportIssue}
                  disabled={!issueText.trim()}
                >
                  Submit Issue
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
