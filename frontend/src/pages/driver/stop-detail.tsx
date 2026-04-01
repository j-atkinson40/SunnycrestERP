import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { driverService } from "@/services/driver-service";
import { getApiErrorMessage } from "@/lib/api-error";
import apiClient from "@/lib/api-client";
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
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [showExceptionForm, setShowExceptionForm] = useState(false);
  const [exceptionItems, setExceptionItems] = useState<
    { item_description: string; checked: boolean; reason: string; notes: string }[]
  >([]);

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

  const handleMarkComplete = () => {
    // Show completion modal instead of completing directly
    // Initialize exception items from delivery line items
    const items = (stop?.delivery?.line_items || []).map((li: { description?: string }) => ({
      item_description: li.description || "Item",
      checked: false,
      reason: "other",
      notes: "",
    }));
    if (items.length === 0) {
      items.push({ item_description: "Delivery", checked: false, reason: "other", notes: "" });
    }
    setExceptionItems(items);
    setShowCompletionModal(true);
  };

  const handleCompleteWithNoIssues = async () => {
    setShowCompletionModal(false);
    await handleStatusUpdate("completed");
  };

  const handleSubmitExceptions = async () => {
    const checked = exceptionItems.filter((i) => i.checked);
    if (checked.length === 0) return;

    try {
      await apiClient.post(`/driver/stops/${stopId}/exception`, {
        exceptions: checked.map((i) => ({
          item_description: i.item_description,
          reason: i.reason,
          notes: i.notes || null,
        })),
      });
      toast.success("Exception report submitted");
    } catch {
      toast.error("Failed to submit exception report");
    }

    setShowCompletionModal(false);
    setShowExceptionForm(false);
    await handleStatusUpdate("completed");
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
              onClick={handleMarkComplete}
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

      {/* Delivery Completion Modal */}
      {showCompletionModal && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40">
          <div className="w-full max-w-md bg-white rounded-t-2xl sm:rounded-2xl p-6 space-y-4">
            {!showExceptionForm ? (
              <>
                <h2 className="text-lg font-bold text-center">
                  Was everything delivered as planned?
                </h2>
                <Button
                  className="w-full bg-green-600 hover:bg-green-700 py-6 text-base"
                  onClick={handleCompleteWithNoIssues}
                  disabled={updating}
                >
                  {updating ? "Completing..." : "Yes, all complete"}
                </Button>
                <Button
                  variant="outline"
                  className="w-full py-6 text-base text-amber-700 border-amber-300"
                  onClick={() => setShowExceptionForm(true)}
                >
                  Report an issue
                </Button>
                <Button
                  variant="ghost"
                  className="w-full"
                  onClick={() => setShowCompletionModal(false)}
                >
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <h2 className="text-lg font-bold">What couldn't be completed?</h2>
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {exceptionItems.map((item, idx) => (
                    <div
                      key={idx}
                      className={`rounded-lg border p-3 ${item.checked ? "border-amber-300 bg-amber-50" : "border-gray-200"}`}
                    >
                      <label className="flex items-center gap-2 text-sm font-medium">
                        <input
                          type="checkbox"
                          checked={item.checked}
                          onChange={(e) => {
                            const next = [...exceptionItems];
                            next[idx] = { ...next[idx], checked: e.target.checked };
                            setExceptionItems(next);
                          }}
                          className="accent-amber-600"
                        />
                        {item.item_description}
                      </label>
                      {item.checked && (
                        <div className="mt-2 space-y-2 pl-6">
                          <select
                            value={item.reason}
                            onChange={(e) => {
                              const next = [...exceptionItems];
                              next[idx] = { ...next[idx], reason: e.target.value };
                              setExceptionItems(next);
                            }}
                            className="w-full border rounded-md p-2 text-sm"
                          >
                            <option value="weather">Weather</option>
                            <option value="access_issue">Access issue</option>
                            <option value="family_request">Family request</option>
                            <option value="equipment_failure">Equipment failure</option>
                            <option value="other">Other</option>
                          </select>
                          <input
                            type="text"
                            value={item.notes}
                            onChange={(e) => {
                              const next = [...exceptionItems];
                              next[idx] = { ...next[idx], notes: e.target.value };
                              setExceptionItems(next);
                            }}
                            placeholder="Notes (optional)"
                            className="w-full border rounded-md p-2 text-sm"
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                <Button
                  className="w-full bg-amber-600 hover:bg-amber-700 py-4"
                  onClick={handleSubmitExceptions}
                  disabled={updating || exceptionItems.every((i) => !i.checked)}
                >
                  {updating ? "Submitting..." : "Submit Exception Report"}
                </Button>
                <Button
                  variant="ghost"
                  className="w-full"
                  onClick={() => setShowExceptionForm(false)}
                >
                  Back
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
