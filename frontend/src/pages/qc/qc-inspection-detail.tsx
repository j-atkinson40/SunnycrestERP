import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { qcService } from "@/services/qc-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  QCInspection,
  QCStepResult,
  QCDefectType,
  StepResult,
  DefectSeverity,
  DispositionType,
  InspectionStatus,
  ProductCategory,
  InspectionType,
} from "@/types/qc";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";

function statusBadge(status: InspectionStatus) {
  const map: Record<InspectionStatus, { label: string; className: string }> = {
    pending: { label: "Pending", className: "bg-gray-100 text-gray-800 border-gray-300" },
    in_progress: { label: "In Progress", className: "bg-blue-100 text-blue-800 border-blue-300" },
    passed: { label: "Passed", className: "bg-green-100 text-green-800 border-green-300" },
    failed: { label: "Failed", className: "bg-red-100 text-red-800 border-red-300" },
    conditional_pass: { label: "Conditional Pass", className: "bg-yellow-100 text-yellow-800 border-yellow-300" },
    rework_required: { label: "Rework Required", className: "bg-orange-100 text-orange-800 border-orange-300" },
  };
  const s = map[status];
  return <Badge variant="outline" className={s.className}>{s.label}</Badge>;
}

function categoryBadge(category: ProductCategory) {
  const map: Record<ProductCategory, { label: string; className: string }> = {
    burial_vault: { label: "Burial Vault", className: "bg-purple-100 text-purple-800 border-purple-300" },
    columbarium: { label: "Columbarium", className: "bg-indigo-100 text-indigo-800 border-indigo-300" },
    monument: { label: "Monument", className: "bg-teal-100 text-teal-800 border-teal-300" },
    redi_rock: { label: "Redi Rock", className: "bg-amber-100 text-amber-800 border-amber-300" },
    precast_other: { label: "Precast Other", className: "bg-slate-100 text-slate-800 border-slate-300" },
  };
  const c = map[category];
  return <Badge variant="outline" className={c.className}>{c.label}</Badge>;
}

function inspectionTypeBadge(type: InspectionType) {
  const map: Record<InspectionType, string> = {
    visual: "Visual",
    pressure_test: "Pressure Test",
    dimensional: "Dimensional",
    photo_required: "Photo Required",
  };
  return <Badge variant="secondary">{map[type]}</Badge>;
}

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleString();
}

const SEVERITY_OPTIONS: { value: DefectSeverity; label: string }[] = [
  { value: "minor", label: "Minor" },
  { value: "major", label: "Major" },
  { value: "critical", label: "Critical" },
];

const DISPOSITION_OPTIONS: { value: DispositionType; label: string }[] = [
  { value: "scrap", label: "Scrap" },
  { value: "rework", label: "Rework" },
  { value: "conditional_pass", label: "Conditional Pass" },
  { value: "hold_pending_review", label: "Hold Pending Review" },
];

export default function QCInspectionDetailPage() {
  const { inspectionId } = useParams<{ inspectionId: string }>();
  const navigate = useNavigate();

  const [inspection, setInspection] = useState<QCInspection | null>(null);
  const [defectTypes, setDefectTypes] = useState<QCDefectType[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);

  // Disposition dialog
  const [dispDialogOpen, setDispDialogOpen] = useState(false);
  const [dispType, setDispType] = useState<DispositionType>("rework");
  const [dispReason, setDispReason] = useState("");
  const [dispInstructions, setDispInstructions] = useState("");
  const [dispSaving, setDispSaving] = useState(false);

  // Rework state
  const [reworkSaving, setReworkSaving] = useState(false);

  const loadInspection = useCallback(async () => {
    if (!inspectionId) return;
    setLoading(true);
    try {
      const data = await qcService.getInspection(inspectionId);
      setInspection(data);
      const dt = await qcService.listDefectTypes(data.product_category);
      setDefectTypes(dt);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to load inspection"));
    } finally {
      setLoading(false);
    }
  }, [inspectionId]);

  useEffect(() => {
    loadInspection();
  }, [loadInspection]);

  async function handleStepResultChange(step: QCStepResult, result: StepResult) {
    if (!inspectionId) return;
    setSaving(step.id);
    try {
      const updated = await qcService.updateStepResult(inspectionId, step.step_id, {
        result,
        defect_type_id: result === "fail" ? step.defect_type_id ?? undefined : undefined,
        defect_severity: result === "fail" ? step.defect_severity ?? undefined : undefined,
        notes: step.notes ?? undefined,
      });
      setInspection(updated);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to update step"));
    } finally {
      setSaving(null);
    }
  }

  async function handleStepFieldChange(
    step: QCStepResult,
    field: "defect_type_id" | "defect_severity" | "notes",
    value: string,
  ) {
    if (!inspectionId) return;
    setSaving(step.id);
    try {
      const payload = {
        result: step.result as StepResult,
        defect_type_id: step.defect_type_id ?? undefined,
        defect_severity: step.defect_severity ?? undefined,
        notes: step.notes ?? undefined,
        [field]: value || undefined,
      };
      const updated = await qcService.updateStepResult(inspectionId, step.step_id, payload);
      setInspection(updated);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to update step"));
    } finally {
      setSaving(null);
    }
  }

  async function handleComplete() {
    if (!inspectionId) return;
    setCompleting(true);
    try {
      const updated = await qcService.completeInspection(inspectionId, inspection?.overall_notes ?? undefined);
      setInspection(updated);
      toast.success("Inspection completed");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to complete inspection"));
    } finally {
      setCompleting(false);
    }
  }

  async function handleCreateDisposition() {
    if (!inspectionId) return;
    setDispSaving(true);
    try {
      const updated = await qcService.createDisposition(inspectionId, {
        disposition_type: dispType,
        reason: dispReason.trim() || undefined,
        rework_instructions: dispInstructions.trim() || undefined,
      });
      setInspection(updated);
      setDispDialogOpen(false);
      setDispReason("");
      setDispInstructions("");
      toast.success("Disposition created");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to create disposition"));
    } finally {
      setDispSaving(false);
    }
  }

  async function handleCreateRework() {
    if (!inspectionId || !inspection) return;
    const lastDisp = inspection.dispositions[inspection.dispositions.length - 1];
    if (!lastDisp) return;
    setReworkSaving(true);
    try {
      const updated = await qcService.createRework(inspectionId, {
        disposition_id: lastDisp.id,
        instructions: lastDisp.rework_instructions ?? undefined,
      });
      setInspection(updated);
      toast.success("Rework record created");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to create rework"));
    } finally {
      setReworkSaving(false);
    }
  }

  async function handleCompleteRework(reworkId: string) {
    if (!inspectionId) return;
    try {
      const updated = await qcService.completeRework(inspectionId, reworkId);
      setInspection(updated);
      toast.success("Rework completed");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to complete rework"));
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading inspection...</p>
      </div>
    );
  }

  if (!inspection) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Inspection not found.</p>
      </div>
    );
  }

  const allRequiredAnswered = inspection.step_results.every(
    (s) => s.result !== "pending",
  );

  const isEditable = inspection.status === "pending" || inspection.status === "in_progress";
  const needsDisposition = inspection.status === "failed" || inspection.status === "conditional_pass";
  const hasReworkDisposition = inspection.dispositions.some((d) => d.disposition_type === "rework");
  const hasActiveRework = inspection.rework_records.some((r) => r.status === "pending" || r.status === "in_progress");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={() => navigate("/qc")}>
          Back
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">
              {inspection.inspection_number}
            </h1>
            {statusBadge(inspection.status)}
            {categoryBadge(inspection.product_category)}
          </div>
          {inspection.status === "passed" && (
            <p className="text-sm text-muted-foreground mt-1">
              Certificate: {inspection.inspection_number}
            </p>
          )}
        </div>
      </div>

      {/* Info Section */}
      <Card>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-sm text-muted-foreground">Template</p>
            <p className="font-medium">{inspection.template_name}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Inspector</p>
            <p className="font-medium">{inspection.inspector_name}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Started</p>
            <p className="font-medium">{formatDate(inspection.started_at)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Completed</p>
            <p className="font-medium">{formatDate(inspection.completed_at)}</p>
          </div>
        </CardContent>
      </Card>

      {/* Steps */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Inspection Steps</h2>
        <div className="space-y-4">
          {inspection.step_results
            .sort((a, b) => a.step_number - b.step_number)
            .map((step) => (
              <StepCard
                key={step.id}
                step={step}
                defectTypes={defectTypes}
                saving={saving === step.id}
                editable={isEditable}
                onResultChange={(result) => handleStepResultChange(step, result)}
                onFieldChange={(field, value) => handleStepFieldChange(step, field, value)}
              />
            ))}
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex items-center gap-3 rounded-lg border bg-muted/50 p-4">
        {isEditable && (
          <Button
            onClick={handleComplete}
            disabled={!allRequiredAnswered || completing}
          >
            {completing ? "Completing..." : "Complete Inspection"}
          </Button>
        )}
        {needsDisposition && (
          <>
            <Button variant="outline" onClick={() => setDispDialogOpen(true)}>
              Add Disposition
            </Button>
            <Dialog open={dispDialogOpen} onOpenChange={setDispDialogOpen}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Disposition</DialogTitle>
                  <DialogDescription>
                    Decide how to handle this inspection result.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Disposition Type</Label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                      value={dispType}
                      onChange={(e) => setDispType(e.target.value as DispositionType)}
                    >
                      {DISPOSITION_OPTIONS.map((d) => (
                        <option key={d.value} value={d.value}>{d.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>Reason</Label>
                    <textarea
                      className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                      value={dispReason}
                      onChange={(e) => setDispReason(e.target.value)}
                      placeholder="Reason for this disposition..."
                    />
                  </div>
                  {dispType === "rework" && (
                    <div className="space-y-2">
                      <Label>Rework Instructions</Label>
                      <textarea
                        className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                        value={dispInstructions}
                        onChange={(e) => setDispInstructions(e.target.value)}
                        placeholder="Instructions for rework..."
                      />
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setDispDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateDisposition} disabled={dispSaving}>
                    {dispSaving ? "Saving..." : "Create Disposition"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        )}
        {hasReworkDisposition && !hasActiveRework && (
          <Button
            variant="outline"
            onClick={handleCreateRework}
            disabled={reworkSaving}
          >
            {reworkSaving ? "Creating..." : "Create Rework Record"}
          </Button>
        )}
      </div>

      {/* Dispositions */}
      {inspection.dispositions.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Dispositions</h2>
          <div className="space-y-3">
            {inspection.dispositions.map((d) => (
              <Card key={d.id}>
                <CardContent>
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{d.disposition_type.replace(/_/g, " ")}</Badge>
                        <span className="text-sm text-muted-foreground">
                          by {d.decided_by_name}
                        </span>
                      </div>
                      {d.reason && <p className="text-sm">{d.reason}</p>}
                      {d.rework_instructions && (
                        <p className="text-sm text-muted-foreground">
                          Rework: {d.rework_instructions}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(d.created_at)}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Rework Records */}
      {inspection.rework_records.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Rework Records</h2>
          <div className="space-y-3">
            {inspection.rework_records.map((r) => (
              <Card key={r.id}>
                <CardContent>
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className={
                            r.status === "completed"
                              ? "bg-green-100 text-green-800 border-green-300"
                              : r.status === "failed"
                                ? "bg-red-100 text-red-800 border-red-300"
                                : "bg-blue-100 text-blue-800 border-blue-300"
                          }
                        >
                          {r.status}
                        </Badge>
                        {r.assigned_to_name && (
                          <span className="text-sm text-muted-foreground">
                            Assigned: {r.assigned_to_name}
                          </span>
                        )}
                      </div>
                      {r.instructions && <p className="text-sm">{r.instructions}</p>}
                      {r.result_notes && (
                        <p className="text-sm text-muted-foreground">
                          Result: {r.result_notes}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {(r.status === "pending" || r.status === "in_progress") && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCompleteRework(r.id)}
                        >
                          Complete
                        </Button>
                      )}
                      <span className="text-xs text-muted-foreground">
                        {formatDate(r.created_at)}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Step Card Component

function StepCard({
  step,
  defectTypes,
  saving,
  editable,
  onResultChange,
  onFieldChange,
}: {
  step: QCStepResult;
  defectTypes: QCDefectType[];
  saving: boolean;
  editable: boolean;
  onResultChange: (result: StepResult) => void;
  onFieldChange: (field: "defect_type_id" | "defect_severity" | "notes", value: string) => void;
}) {
  const [localNotes, setLocalNotes] = useState(step.notes ?? "");

  useEffect(() => {
    setLocalNotes(step.notes ?? "");
  }, [step.notes]);

  return (
    <Card className={saving ? "opacity-60" : ""}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle>
              {step.step_number}. {step.step_name}
            </CardTitle>
            {inspectionTypeBadge(step.inspection_type)}
            {step.photo_required && (
              <Badge variant="outline" className="bg-pink-50 text-pink-700 border-pink-300">
                Photo Required
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {step.step_description && (
          <p className="text-sm text-muted-foreground">{step.step_description}</p>
        )}

        {/* Result buttons */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium mr-2">Result:</span>
          <Button
            size="sm"
            variant={step.result === "pass" ? "default" : "outline"}
            className={step.result === "pass" ? "bg-green-600 hover:bg-green-700" : ""}
            disabled={!editable}
            onClick={() => onResultChange("pass")}
          >
            Pass
          </Button>
          <Button
            size="sm"
            variant={step.result === "fail" ? "default" : "outline"}
            className={step.result === "fail" ? "bg-red-600 hover:bg-red-700" : ""}
            disabled={!editable}
            onClick={() => onResultChange("fail")}
          >
            Fail
          </Button>
          <Button
            size="sm"
            variant={step.result === "na" ? "default" : "outline"}
            className={step.result === "na" ? "bg-gray-600 hover:bg-gray-700" : ""}
            disabled={!editable}
            onClick={() => onResultChange("na")}
          >
            N/A
          </Button>
        </div>

        {/* Fail details */}
        {step.result === "fail" && (
          <div className="grid gap-4 sm:grid-cols-2 rounded-md border bg-red-50/50 p-4">
            <div className="space-y-2">
              <Label>Defect Type</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={step.defect_type_id ?? ""}
                onChange={(e) => onFieldChange("defect_type_id", e.target.value)}
                disabled={!editable}
              >
                <option value="">Select defect type...</option>
                {defectTypes.map((dt) => (
                  <option key={dt.id} value={dt.id}>{dt.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Severity</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={step.defect_severity ?? ""}
                onChange={(e) => onFieldChange("defect_severity", e.target.value)}
                disabled={!editable}
              >
                <option value="">Select severity...</option>
                {SEVERITY_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Notes */}
        <div className="space-y-2">
          <Label>Notes</Label>
          <textarea
            className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            value={localNotes}
            onChange={(e) => setLocalNotes(e.target.value)}
            onBlur={() => {
              if (localNotes !== (step.notes ?? "")) {
                onFieldChange("notes", localNotes);
              }
            }}
            disabled={!editable}
            placeholder="Optional notes for this step..."
          />
        </div>
      </CardContent>
    </Card>
  );
}
