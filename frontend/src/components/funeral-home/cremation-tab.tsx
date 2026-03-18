import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Check, Clock, Circle } from "lucide-react";
import { funeralHomeService } from "@/services/funeral-home-service";
import type { FHCase, CremationAuthStatus, RemainsDisposition } from "@/types/funeral-home";

interface CremationTabProps {
  caseData: FHCase;
  onUpdate: () => void;
}

const DISPOSITION_LABELS: Record<RemainsDisposition, string> = {
  family_pickup: "Family Pickup",
  delivery: "Delivery",
  interment: "Interment",
  scattering: "Scattering",
  pending: "Pending",
};

const AUTH_STATUS_LABELS: Record<CremationAuthStatus, string> = {
  not_applicable: "N/A",
  pending: "Pending",
  signed: "Signed",
  received: "Received",
};

const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleDateString() : "");
const fmtDateTime = (d?: string | null) => (d ? new Date(d).toLocaleString() : "");

type MilestoneStatus = "complete" | "current" | "future";

interface Milestone {
  key: string;
  title: string;
  status: MilestoneStatus;
  detail?: string;
}

function getMilestones(c: FHCase): Milestone[] {
  const authDone = c.cremation_authorization_status === "signed" || c.cremation_authorization_status === "received";
  const scheduled = !!c.cremation_scheduled_date;
  const completed = !!c.cremation_completed_date;
  const dispositionSet = !!c.remains_disposition && c.remains_disposition !== "pending";
  const released = !!c.remains_released_at;

  const steps: Milestone[] = [];

  // 1. Authorization
  steps.push({
    key: "auth",
    title: "Authorization",
    status: authDone ? "complete" : "current",
    detail: authDone
      ? `${AUTH_STATUS_LABELS[c.cremation_authorization_status!]} by ${c.cremation_authorization_signed_by ?? "Unknown"} on ${fmtDateTime(c.cremation_authorization_signed_at)}`
      : c.cremation_authorization_status === "pending"
        ? "Awaiting signature"
        : undefined,
  });

  // 2. Scheduled
  steps.push({
    key: "scheduled",
    title: "Scheduled",
    status: !authDone ? "future" : scheduled ? "complete" : "current",
    detail: scheduled ? `Scheduled for ${fmtDate(c.cremation_scheduled_date)}` : "Not yet scheduled",
  });

  // 3. Cremation Complete
  steps.push({
    key: "completed",
    title: "Cremation Complete",
    status: !scheduled ? "future" : completed ? "complete" : "current",
    detail: completed ? `Completed on ${fmtDate(c.cremation_completed_date)}` : "Pending",
  });

  // 4. Remains Processing
  steps.push({
    key: "disposition",
    title: "Remains Processing",
    status: !completed ? "future" : dispositionSet ? "complete" : "current",
    detail: dispositionSet && c.remains_disposition ? DISPOSITION_LABELS[c.remains_disposition] : undefined,
  });

  // 5. Released
  steps.push({
    key: "released",
    title: "Released",
    status: !dispositionSet ? "future" : released ? "complete" : "current",
    detail: released
      ? `Released to ${c.remains_released_to ?? "Unknown"} on ${fmtDateTime(c.remains_released_at)}`
      : undefined,
  });

  return steps;
}

function MilestoneIcon({ status }: { status: MilestoneStatus }) {
  if (status === "complete") {
    return (
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-600 text-white shadow-sm">
        <Check className="h-5 w-5" />
      </div>
    );
  }
  if (status === "current") {
    return (
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-500 text-white shadow-sm animate-pulse">
        <Clock className="h-5 w-5" />
      </div>
    );
  }
  return (
    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-200 text-gray-400">
      <Circle className="h-5 w-5" />
    </div>
  );
}

export function CremationTab({ caseData, onUpdate }: CremationTabProps) {
  const [saving, setSaving] = useState(false);
  const [signedByName, setSignedByName] = useState("");
  const [scheduledDate, setScheduledDate] = useState("");
  const [disposition, setDisposition] = useState<RemainsDisposition>("pending");
  const [releasedToName, setReleasedToName] = useState("");

  const milestones = getMilestones(caseData);

  const save = async (payload: Record<string, unknown>) => {
    setSaving(true);
    try {
      await funeralHomeService.updateCremationStatus(caseData.id, payload as Record<string, string | null>);
      toast.success("Cremation status updated");
      onUpdate();
    } catch {
      toast.error("Failed to update cremation status");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Provider Info */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label className="text-xs text-muted-foreground">Cremation Provider</Label>
              <p className="text-sm font-medium">{caseData.cremation_provider || "Not set"}</p>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Provider Case Number</Label>
              <p className="text-sm font-medium">{caseData.cremation_provider_case_number || "Not set"}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Vertical Timeline */}
      <div className="relative pl-6">
        {milestones.map((m, i) => (
          <div key={m.key} className="relative pb-8 last:pb-0">
            {/* Connecting line */}
            {i < milestones.length - 1 && (
              <div
                className={cn(
                  "absolute left-5 top-10 w-0.5 h-full -translate-x-1/2",
                  m.status === "complete" ? "bg-green-300" : "bg-gray-200",
                )}
              />
            )}

            <div className="flex gap-4">
              <MilestoneIcon status={m.status} />
              <Card className={cn(
                "flex-1",
                m.status === "current" && "ring-1 ring-amber-300",
              )}>
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="font-semibold text-sm">{m.title}</h4>
                    {m.status === "complete" && (
                      <span className="text-xs text-green-700 font-medium bg-green-50 px-2 py-0.5 rounded-full">
                        Complete
                      </span>
                    )}
                    {m.status === "current" && (
                      <span className="text-xs text-amber-700 font-medium bg-amber-50 px-2 py-0.5 rounded-full">
                        Current
                      </span>
                    )}
                  </div>

                  {m.detail && (
                    <p className="text-sm text-muted-foreground mb-3">{m.detail}</p>
                  )}

                  {/* Action: Authorization */}
                  {m.key === "auth" && m.status === "current" && (
                    <div className="space-y-3 mt-2">
                      <div>
                        <Label htmlFor="signed-by" className="text-xs">Signed By</Label>
                        <Input
                          id="signed-by"
                          value={signedByName}
                          onChange={(e) => setSignedByName(e.target.value)}
                          placeholder="Name of person who signed"
                          className="mt-1"
                        />
                      </div>
                      <Button
                        size="sm"
                        disabled={saving || !signedByName.trim()}
                        onClick={() =>
                          save({
                            cremation_authorization_status: "signed",
                            cremation_authorization_signed_by: signedByName.trim(),
                            cremation_authorization_signed_at: new Date().toISOString(),
                          })
                        }
                      >
                        Mark as Signed
                      </Button>
                    </div>
                  )}

                  {/* Action: Schedule */}
                  {m.key === "scheduled" && m.status === "current" && (
                    <div className="space-y-3 mt-2">
                      <div>
                        <Label htmlFor="sched-date" className="text-xs">Cremation Date</Label>
                        <Input
                          id="sched-date"
                          type="date"
                          value={scheduledDate}
                          onChange={(e) => setScheduledDate(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                      <Button
                        size="sm"
                        disabled={saving || !scheduledDate}
                        onClick={() =>
                          save({ cremation_scheduled_date: scheduledDate })
                        }
                      >
                        Set Schedule
                      </Button>
                    </div>
                  )}

                  {/* Action: Mark Complete */}
                  {m.key === "completed" && m.status === "current" && (
                    <div className="mt-2">
                      <Button
                        size="sm"
                        disabled={saving}
                        onClick={() =>
                          save({ cremation_completed_date: new Date().toISOString().split("T")[0] })
                        }
                      >
                        Mark Complete
                      </Button>
                    </div>
                  )}

                  {/* Action: Remains Disposition */}
                  {m.key === "disposition" && m.status === "current" && (
                    <div className="space-y-3 mt-2">
                      <div>
                        <Label htmlFor="disposition" className="text-xs">Disposition Method</Label>
                        <select
                          id="disposition"
                          value={disposition}
                          onChange={(e) => setDisposition(e.target.value as RemainsDisposition)}
                          className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        >
                          <option value="pending">Select...</option>
                          <option value="family_pickup">Family Pickup</option>
                          <option value="delivery">Delivery</option>
                          <option value="interment">Interment</option>
                          <option value="scattering">Scattering</option>
                        </select>
                      </div>
                      <Button
                        size="sm"
                        disabled={saving || disposition === "pending"}
                        onClick={() => save({ remains_disposition: disposition })}
                      >
                        Set Disposition
                      </Button>
                    </div>
                  )}

                  {/* Action: Released */}
                  {m.key === "released" && m.status === "current" && (
                    <div className="space-y-3 mt-2">
                      <div>
                        <Label htmlFor="released-to" className="text-xs">Released To</Label>
                        <Input
                          id="released-to"
                          value={releasedToName}
                          onChange={(e) => setReleasedToName(e.target.value)}
                          placeholder="Name of person receiving remains"
                          className="mt-1"
                        />
                      </div>
                      <Button
                        size="sm"
                        disabled={saving || !releasedToName.trim()}
                        onClick={() =>
                          save({
                            remains_released_to: releasedToName.trim(),
                            remains_released_at: new Date().toISOString(),
                          })
                        }
                      >
                        Mark Released
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
