import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { qcService } from "@/services/qc-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  QCInspection,
  QCStepResult,
  QCDefectType,
  StepResult,
  DefectSeverity,
} from "@/types/qc";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

const SEVERITY_OPTIONS: { value: DefectSeverity; label: string }[] = [
  { value: "minor", label: "Minor" },
  { value: "major", label: "Major" },
  { value: "critical", label: "Critical" },
];

function ResultBadge({ result }: { result: string }) {
  switch (result) {
    case "pass":
      return <Badge className="bg-green-100 text-green-800 border-green-300">Pass</Badge>;
    case "fail":
      return <Badge className="bg-red-100 text-red-800 border-red-300">Fail</Badge>;
    case "na":
      return <Badge className="bg-gray-100 text-gray-800 border-gray-300">N/A</Badge>;
    default:
      return <Badge variant="outline">Pending</Badge>;
  }
}

export default function QCMobilePage() {
  const { inspectionId } = useParams<{ inspectionId: string }>();
  const navigate = useNavigate();

  const [inspection, setInspection] = useState<QCInspection | null>(null);
  const [defectTypes, setDefectTypes] = useState<QCDefectType[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentStep, setCurrentStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [overallNotes, setOverallNotes] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Local state for current step edits
  const [localNotes, setLocalNotes] = useState("");
  const [localDefectTypeId, setLocalDefectTypeId] = useState("");
  const [localSeverity, setLocalSeverity] = useState("");

  const sortedSteps = inspection?.step_results
    .slice()
    .sort((a, b) => a.step_number - b.step_number) ?? [];

  const totalSteps = sortedSteps.length;
  const step = sortedSteps[currentStep] ?? null;
  const isReview = currentStep >= totalSteps;

  const loadInspection = useCallback(async () => {
    if (!inspectionId) return;
    setLoading(true);
    try {
      const data = await qcService.getInspection(inspectionId);
      setInspection(data);
      setOverallNotes(data.overall_notes ?? "");
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

  // Sync local fields when step changes
  useEffect(() => {
    if (step) {
      setLocalNotes(step.notes ?? "");
      setLocalDefectTypeId(step.defect_type_id ?? "");
      setLocalSeverity(step.defect_severity ?? "");
    }
  }, [step?.id, step?.notes, step?.defect_type_id, step?.defect_severity]);

  async function handleResultSelect(result: StepResult) {
    if (!inspectionId || !step) return;
    setSaving(true);
    try {
      const updated = await qcService.updateStepResult(inspectionId, step.step_id, {
        result,
        defect_type_id: result === "fail" ? localDefectTypeId || undefined : undefined,
        defect_severity: result === "fail" ? (localSeverity as DefectSeverity) || undefined : undefined,
        notes: localNotes || undefined,
      });
      setInspection(updated);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to save result"));
    } finally {
      setSaving(false);
    }
  }

  async function saveCurrentStepFields() {
    if (!inspectionId || !step || step.result === "pending") return;
    setSaving(true);
    try {
      const updated = await qcService.updateStepResult(inspectionId, step.step_id, {
        result: step.result as StepResult,
        defect_type_id: step.result === "fail" ? localDefectTypeId || undefined : undefined,
        defect_severity: step.result === "fail" ? (localSeverity as DefectSeverity) || undefined : undefined,
        notes: localNotes || undefined,
      });
      setInspection(updated);
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  }

  async function handlePhotoCapture(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !inspectionId || !step) return;
    try {
      await qcService.uploadMedia(inspectionId, step.id, file);
      toast.success("Photo uploaded");
      loadInspection();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to upload photo"));
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleComplete() {
    if (!inspectionId) return;
    setCompleting(true);
    try {
      await qcService.completeInspection(inspectionId, overallNotes || undefined);
      toast.success("Inspection completed");
      navigate("/qc");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to complete inspection"));
    } finally {
      setCompleting(false);
    }
  }

  function goNext() {
    saveCurrentStepFields();
    setCurrentStep((s) => Math.min(s + 1, totalSteps));
  }

  function goPrev() {
    saveCurrentStepFields();
    setCurrentStep((s) => Math.max(s - 1, 0));
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <p className="text-muted-foreground text-lg">Loading inspection...</p>
      </div>
    );
  }

  if (!inspection) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <p className="text-muted-foreground text-lg">Inspection not found.</p>
      </div>
    );
  }

  const progress = totalSteps > 0 ? ((currentStep) / totalSteps) * 100 : 0;

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* Top bar */}
      <div className="sticky top-0 z-10 border-b bg-background p-4">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-lg font-bold">{inspection.inspection_number}</h1>
          <Badge variant="outline" className="text-xs">
            {inspection.product_category.replace(/_/g, " ")}
          </Badge>
        </div>
        {/* Progress bar */}
        <div className="w-full bg-muted rounded-full h-2">
          <div
            className="bg-primary h-2 rounded-full transition-all duration-300"
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
        <p className="text-xs text-muted-foreground mt-1 text-center">
          {isReview ? "Review" : `Step ${currentStep + 1} of ${totalSteps}`}
        </p>
      </div>

      {/* Content */}
      <div className="flex-1 p-4">
        {isReview ? (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-center">Review & Complete</h2>

            <div className="space-y-2">
              {sortedSteps.map((s, idx) => (
                <button
                  key={s.id}
                  className="flex items-center justify-between w-full rounded-lg border p-3 text-left"
                  onClick={() => setCurrentStep(idx)}
                >
                  <span className="text-sm font-medium">
                    {s.step_number}. {s.step_name}
                  </span>
                  <ResultBadge result={s.result} />
                </button>
              ))}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Overall Notes</label>
              <textarea
                className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                value={overallNotes}
                onChange={(e) => setOverallNotes(e.target.value)}
                placeholder="Any additional notes..."
              />
            </div>

            <Button
              className="w-full h-14 text-lg"
              onClick={handleComplete}
              disabled={completing}
            >
              {completing ? "Completing..." : "Complete Inspection"}
            </Button>
          </div>
        ) : step ? (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold">
                {step.step_number}. {step.step_name}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="secondary">
                  {step.inspection_type.replace(/_/g, " ")}
                </Badge>
                {step.photo_required && (
                  <Badge variant="outline" className="bg-pink-50 text-pink-700 border-pink-300">
                    Photo Required
                  </Badge>
                )}
              </div>
              {step.step_description && (
                <p className="text-muted-foreground mt-2">{step.step_description}</p>
              )}
            </div>

            {/* Large Pass / Fail / NA buttons */}
            <div className="grid grid-cols-3 gap-3">
              <button
                className={`flex flex-col items-center justify-center rounded-xl border-2 p-6 text-lg font-bold transition-colors ${
                  step.result === "pass"
                    ? "border-green-500 bg-green-100 text-green-800"
                    : "border-gray-200 bg-white text-gray-600"
                }`}
                onClick={() => handleResultSelect("pass")}
                disabled={saving}
              >
                <svg className="h-10 w-10 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                Pass
              </button>
              <button
                className={`flex flex-col items-center justify-center rounded-xl border-2 p-6 text-lg font-bold transition-colors ${
                  step.result === "fail"
                    ? "border-red-500 bg-red-100 text-red-800"
                    : "border-gray-200 bg-white text-gray-600"
                }`}
                onClick={() => handleResultSelect("fail")}
                disabled={saving}
              >
                <svg className="h-10 w-10 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
                Fail
              </button>
              <button
                className={`flex flex-col items-center justify-center rounded-xl border-2 p-6 text-lg font-bold transition-colors ${
                  step.result === "na"
                    ? "border-gray-500 bg-gray-100 text-gray-800"
                    : "border-gray-200 bg-white text-gray-600"
                }`}
                onClick={() => handleResultSelect("na")}
                disabled={saving}
              >
                <svg className="h-10 w-10 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 12H4" />
                </svg>
                N/A
              </button>
            </div>

            {/* Fail details */}
            {step.result === "fail" && (
              <div className="space-y-3 rounded-lg border bg-red-50/50 p-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Defect Type</label>
                  <select
                    className="flex h-11 w-full rounded-md border border-input bg-white px-3 py-1 text-base"
                    value={localDefectTypeId}
                    onChange={(e) => setLocalDefectTypeId(e.target.value)}
                  >
                    <option value="">Select defect...</option>
                    {defectTypes.map((dt) => (
                      <option key={dt.id} value={dt.id}>{dt.name}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Severity</label>
                  <select
                    className="flex h-11 w-full rounded-md border border-input bg-white px-3 py-1 text-base"
                    value={localSeverity}
                    onChange={(e) => setLocalSeverity(e.target.value)}
                  >
                    <option value="">Select severity...</option>
                    {SEVERITY_OPTIONS.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {/* Camera button */}
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={handlePhotoCapture}
              />
              <Button
                variant="outline"
                className="w-full h-12 text-base"
                onClick={() => fileInputRef.current?.click()}
              >
                <svg className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Take Photo
              </Button>
              {step.media.length > 0 && (
                <p className="text-xs text-muted-foreground mt-1 text-center">
                  {step.media.length} photo(s) attached
                </p>
              )}
            </div>

            {/* Notes */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Notes</label>
              <textarea
                className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-base"
                value={localNotes}
                onChange={(e) => setLocalNotes(e.target.value)}
                placeholder="Optional notes..."
              />
            </div>
          </div>
        ) : null}
      </div>

      {/* Bottom navigation */}
      {!isReview && (
        <div className="sticky bottom-0 border-t bg-background p-4">
          <div className="flex gap-3">
            <Button
              variant="outline"
              className="flex-1 h-12 text-base"
              disabled={currentStep <= 0}
              onClick={goPrev}
            >
              Previous
            </Button>
            <Button
              className="flex-1 h-12 text-base"
              onClick={goNext}
            >
              {currentStep >= totalSteps - 1 ? "Review" : "Next"}
            </Button>
          </div>
        </div>
      )}

      {isReview && (
        <div className="sticky bottom-0 border-t bg-background p-4">
          <Button
            variant="outline"
            className="w-full h-12 text-base"
            onClick={goPrev}
          >
            Back to Steps
          </Button>
        </div>
      )}
    </div>
  );
}
