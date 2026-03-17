import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { workOrderService } from "@/services/work-order-service";
import type { WorkOrder, MixDesign, CureSchedule } from "@/types/work-order";

interface SelectedWO {
  wo: WorkOrder;
  quantity: number;
}

export default function PourEventCreatePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);

  // Data
  const [openWOs, setOpenWOs] = useState<WorkOrder[]>([]);
  const [mixDesigns, setMixDesigns] = useState<MixDesign[]>([]);
  const [cureSchedules, setCureSchedules] = useState<CureSchedule[]>([]);
  const [loading, setLoading] = useState(true);

  // Selections
  const [selected, setSelected] = useState<Map<string, SelectedWO>>(new Map());

  // Pour details
  const [pourDate, setPourDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [pourTime, setPourTime] = useState("");
  const [mixDesignId, setMixDesignId] = useState("");
  const [cureScheduleId, setCureScheduleId] = useState("");
  const [crewNotes, setCrewNotes] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [woRes, mixes, schedules] = await Promise.all([
          workOrderService.list({ status: "open" }),
          workOrderService.listMixDesigns(),
          workOrderService.listCureSchedules(),
        ]);
        setOpenWOs(woRes.items);
        setMixDesigns(mixes.filter((m) => m.is_active));
        setCureSchedules(schedules);
      } catch {
        toast.error("Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // When mix design changes, auto-select its cure schedule
  useEffect(() => {
    if (mixDesignId) {
      const mix = mixDesigns.find((m) => m.id === mixDesignId);
      if (mix?.cure_schedule_id) {
        setCureScheduleId(mix.cure_schedule_id);
      }
    }
  }, [mixDesignId, mixDesigns]);

  const toggleWO = (wo: WorkOrder) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(wo.id)) {
        next.delete(wo.id);
      } else {
        const remaining = wo.quantity_ordered - wo.quantity_produced;
        next.set(wo.id, { wo, quantity: remaining > 0 ? remaining : 1 });
      }
      return next;
    });
  };

  const updateQuantity = (woId: string, qty: number) => {
    setSelected((prev) => {
      const next = new Map(prev);
      const entry = next.get(woId);
      if (entry) {
        const remaining = entry.wo.quantity_ordered - entry.wo.quantity_produced;
        next.set(woId, { ...entry, quantity: Math.max(1, Math.min(qty, remaining)) });
      }
      return next;
    });
  };

  const totalQuantity = Array.from(selected.values()).reduce((sum, s) => sum + s.quantity, 0);

  const selectedCure = cureSchedules.find((c) => c.id === cureScheduleId);
  const selectedMix = mixDesigns.find((m) => m.id === mixDesignId);

  const estimatedRelease = (() => {
    if (!pourDate || !selectedCure) return null;
    const base = pourTime ? new Date(`${pourDate}T${pourTime}`) : new Date(`${pourDate}T08:00`);
    base.setHours(base.getHours() + selectedCure.duration_hours);
    return base;
  })();

  const handleSubmit = async () => {
    if (selected.size === 0) {
      toast.error("Select at least one work order");
      return;
    }
    setSubmitting(true);
    try {
      await workOrderService.createPourEvent({
        pour_date: pourDate,
        pour_time: pourTime || undefined,
        cure_schedule_id: cureScheduleId || undefined,
        crew_notes: crewNotes || undefined,
        work_order_items: Array.from(selected.values()).map((s) => ({
          work_order_id: s.wo.id,
          quantity_in_this_pour: s.quantity,
        })),
      });
      toast.success("Pour event created");
      navigate("/production");
    } catch {
      toast.error("Failed to create pour event");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-2xl font-bold">New Pour Event</h1>

      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {[1, 2, 3].map((s) => (
          <button
            key={s}
            onClick={() => {
              if (s < step) setStep(s);
            }}
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-colors",
              s === step
                ? "bg-primary text-primary-foreground"
                : s < step
                  ? "bg-primary/20 text-primary cursor-pointer"
                  : "bg-muted text-muted-foreground",
            )}
          >
            {s}
          </button>
        ))}
        <span className="ml-2 text-sm text-muted-foreground">
          {step === 1 && "Select Work Orders"}
          {step === 2 && "Pour Details"}
          {step === 3 && "Review & Confirm"}
        </span>
      </div>

      {/* Step 1: Select Work Orders */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Select Work Orders</CardTitle>
          </CardHeader>
          <CardContent>
            {openWOs.length === 0 ? (
              <p className="py-8 text-center text-muted-foreground">No open work orders available</p>
            ) : (
              <div className="space-y-1">
                {/* Table header */}
                <div className="grid grid-cols-[auto_1fr_120px_120px_120px] items-center gap-3 px-3 py-2 text-xs font-medium text-muted-foreground">
                  <span className="w-5" />
                  <span>Work Order / Product</span>
                  <span className="text-right">Remaining</span>
                  <span className="text-right">Needed By</span>
                  <span className="text-right">Qty in Pour</span>
                </div>

                {openWOs.map((wo) => {
                  const isSelected = selected.has(wo.id);
                  const remaining = wo.quantity_ordered - wo.quantity_produced;
                  return (
                    <div
                      key={wo.id}
                      className={cn(
                        "grid grid-cols-[auto_1fr_120px_120px_120px] items-center gap-3 rounded-lg px-3 py-2 transition-colors",
                        isSelected ? "bg-primary/5 ring-1 ring-primary/20" : "hover:bg-muted/50",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleWO(wo)}
                        className="h-4 w-4 rounded border-border"
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">
                          {wo.work_order_number} — {wo.product_name ?? "Product"}
                        </p>
                        {wo.customer_name && (
                          <p className="text-xs text-muted-foreground truncate">{wo.customer_name}</p>
                        )}
                      </div>
                      <span className="text-right text-sm">{remaining}</span>
                      <span className="text-right text-sm">{new Date(wo.needed_by_date).toLocaleDateString()}</span>
                      <div className="flex justify-end">
                        {isSelected ? (
                          <Input
                            type="number"
                            min={1}
                            max={remaining}
                            value={selected.get(wo.id)!.quantity}
                            onChange={(e) => updateQuantity(wo.id, parseInt(e.target.value) || 1)}
                            className="h-8 w-20 text-right"
                          />
                        ) : (
                          <span className="text-sm text-muted-foreground">-</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="mt-4 flex items-center justify-between border-t pt-4">
              <p className="text-sm text-muted-foreground">
                {selected.size} work order{selected.size !== 1 ? "s" : ""} selected — {totalQuantity} total units
              </p>
              <Button onClick={() => setStep(2)} disabled={selected.size === 0}>
                Next
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Pour Details */}
      {step === 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Pour Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="pour-date">Pour Date</Label>
                <Input
                  id="pour-date"
                  type="date"
                  value={pourDate}
                  onChange={(e) => setPourDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pour-time">Pour Time (optional)</Label>
                <Input
                  id="pour-time"
                  type="time"
                  value={pourTime}
                  onChange={(e) => setPourTime(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="mix-design">Mix Design</Label>
              <select
                id="mix-design"
                value={mixDesignId}
                onChange={(e) => setMixDesignId(e.target.value)}
                className="flex h-8 w-full rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Select mix design...</option>
                {mixDesigns.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.mix_design_code} — {m.name} ({m.design_strength_psi} PSI)
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="cure-schedule">Cure Schedule</Label>
              <select
                id="cure-schedule"
                value={cureScheduleId}
                onChange={(e) => setCureScheduleId(e.target.value)}
                className="flex h-8 w-full rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">Select cure schedule...</option>
                {cureSchedules.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.duration_hours}h)
                  </option>
                ))}
              </select>
              {selectedMix?.cure_schedule_id && (
                <p className="text-xs text-muted-foreground">Auto-filled from mix design default</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="crew-notes">Crew Notes (optional)</Label>
              <textarea
                id="crew-notes"
                value={crewNotes}
                onChange={(e) => setCrewNotes(e.target.value)}
                rows={3}
                className="flex w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div className="flex items-center justify-between border-t pt-4">
              <Button variant="outline" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button onClick={() => setStep(3)}>
                Next
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Review */}
      {step === 3 && (
        <Card>
          <CardHeader>
            <CardTitle>Review Pour Event</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* WO Summary */}
            <div>
              <h3 className="mb-2 text-sm font-semibold">Work Orders</h3>
              <div className="rounded-lg border">
                <div className="grid grid-cols-[1fr_100px] gap-2 border-b px-3 py-2 text-xs font-medium text-muted-foreground">
                  <span>Work Order / Product</span>
                  <span className="text-right">Quantity</span>
                </div>
                {Array.from(selected.values()).map((s) => (
                  <div key={s.wo.id} className="grid grid-cols-[1fr_100px] gap-2 border-b last:border-0 px-3 py-2 text-sm">
                    <span>
                      {s.wo.work_order_number} — {s.wo.product_name ?? "Product"}
                    </span>
                    <span className="text-right font-medium">{s.quantity}</span>
                  </div>
                ))}
                <div className="grid grid-cols-[1fr_100px] gap-2 bg-muted/50 px-3 py-2 text-sm font-semibold">
                  <span>Total</span>
                  <span className="text-right">{totalQuantity}</span>
                </div>
              </div>
            </div>

            {/* Details */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Pour Date</p>
                <p className="text-sm font-medium">{new Date(pourDate).toLocaleDateString()}</p>
              </div>
              {pourTime && (
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Pour Time</p>
                  <p className="text-sm font-medium">{pourTime}</p>
                </div>
              )}
              {selectedMix && (
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Mix Design</p>
                  <p className="text-sm font-medium">
                    {selectedMix.mix_design_code} — {selectedMix.name}
                  </p>
                </div>
              )}
              {selectedCure && (
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Cure Schedule</p>
                  <p className="text-sm font-medium">
                    {selectedCure.name} ({selectedCure.duration_hours}h)
                  </p>
                </div>
              )}
              {estimatedRelease && (
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Est. Release</p>
                  <p className="text-sm font-medium">{estimatedRelease.toLocaleString()}</p>
                </div>
              )}
            </div>

            {crewNotes && (
              <div>
                <h3 className="mb-1 text-sm font-semibold">Crew Notes</h3>
                <p className="text-sm text-muted-foreground">{crewNotes}</p>
              </div>
            )}

            <div className="flex items-center justify-between border-t pt-4">
              <Button variant="outline" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button onClick={handleSubmit} disabled={submitting}>
                {submitting ? "Creating..." : "Create Pour Event"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
