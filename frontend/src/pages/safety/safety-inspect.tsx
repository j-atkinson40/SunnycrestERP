import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { safetyService } from "@/services/safety-service";
import type {
  InspectionTemplate,
  SafetyInspection,
} from "@/types/safety";

type Step = "select" | "inspect" | "review";

interface LocalResult {
  item_id: string;
  item_text: string;
  item_order: number;
  osha_reference: string | null;
  required: boolean;
  result: "pass" | "fail" | null;
  finding_notes: string;
  corrective_action_required: boolean;
}

export default function SafetyInspectPage() {
  const { inspectionId } = useParams<{ inspectionId: string }>();
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>("select");
  const [templates, setTemplates] = useState<InspectionTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [equipmentIdentifier, setEquipmentIdentifier] = useState("");
  const [loading, setLoading] = useState(false);

  // Active inspection state
  const [inspection, setInspection] = useState<SafetyInspection | null>(null);
  const [results, setResults] = useState<LocalResult[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  // Load templates on mount (unless resuming an existing inspection)
  useEffect(() => {
    if (inspectionId) {
      loadExistingInspection(inspectionId);
    } else {
      loadTemplates();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inspectionId]);

  async function loadTemplates() {
    try {
      const data = await safetyService.listInspectionTemplates(true);
      setTemplates(data);
    } catch {
      toast.error("Failed to load inspection templates");
    }
  }

  async function loadExistingInspection(id: string) {
    setLoading(true);
    try {
      const data = await safetyService.getInspection(id);
      setInspection(data);

      // Build local results from existing inspection results
      const localResults: LocalResult[] = data.results
        .sort((a, b) => (a.item_order ?? 0) - (b.item_order ?? 0))
        .map((r) => ({
          item_id: r.item_id,
          item_text: r.item_text ?? "",
          item_order: r.item_order ?? 0,
          osha_reference: null,
          required: r.required ?? false,
          result: r.result === "pass" || r.result === "fail" ? r.result : null,
          finding_notes: r.finding_notes ?? "",
          corrective_action_required: r.corrective_action_required,
        }));

      setResults(localResults);

      // If completed, go to review; otherwise go to first unanswered item
      if (data.status === "completed") {
        setStep("review");
      } else {
        const firstUnanswered = localResults.findIndex((r) => r.result === null);
        setCurrentIndex(firstUnanswered >= 0 ? firstUnanswered : 0);
        setStep("inspect");
      }
    } catch {
      toast.error("Failed to load inspection");
      navigate(-1);
    } finally {
      setLoading(false);
    }
  }

  async function handleStartInspection() {
    if (!selectedTemplateId) {
      toast.error("Please select an inspection template");
      return;
    }

    setLoading(true);
    try {
      const data = await safetyService.startInspection({
        template_id: selectedTemplateId,
        equipment_identifier: equipmentIdentifier || undefined,
        inspection_date: new Date().toISOString().split("T")[0],
      });

      setInspection(data);

      // Build local results from the returned inspection
      const template = templates.find((t) => t.id === selectedTemplateId);
      const localResults: LocalResult[] = data.results
        .sort((a, b) => (a.item_order ?? 0) - (b.item_order ?? 0))
        .map((r) => {
          const templateItem = template?.items.find((i) => i.id === r.item_id);
          return {
            item_id: r.item_id,
            item_text: r.item_text ?? templateItem?.item_text ?? "",
            item_order: r.item_order ?? templateItem?.item_order ?? 0,
            osha_reference: templateItem?.osha_reference ?? null,
            required: r.required ?? templateItem?.required ?? false,
            result: null,
            finding_notes: "",
            corrective_action_required: false,
          };
        });

      setResults(localResults);
      setCurrentIndex(0);
      setStep("inspect");
      toast.success("Inspection started");
    } catch {
      toast.error("Failed to start inspection");
    } finally {
      setLoading(false);
    }
  }

  function handleAnswer(answer: "pass" | "fail") {
    setResults((prev) => {
      const updated = [...prev];
      updated[currentIndex] = {
        ...updated[currentIndex],
        result: answer,
        // Clear corrective action fields if switching to pass
        ...(answer === "pass"
          ? { finding_notes: "", corrective_action_required: false }
          : {}),
      };
      return updated;
    });
  }

  function handleNotesChange(notes: string) {
    setResults((prev) => {
      const updated = [...prev];
      updated[currentIndex] = { ...updated[currentIndex], finding_notes: notes };
      return updated;
    });
  }

  function handleCorrectiveToggle() {
    setResults((prev) => {
      const updated = [...prev];
      updated[currentIndex] = {
        ...updated[currentIndex],
        corrective_action_required: !updated[currentIndex].corrective_action_required,
      };
      return updated;
    });
  }

  function handleNext() {
    const current = results[currentIndex];
    if (current.required && current.result === null) {
      toast.error("This item is required. Please select Pass or Fail.");
      return;
    }
    if (currentIndex < results.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      setStep("review");
    }
  }

  function handlePrev() {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  }

  function handleEditItem(index: number) {
    setCurrentIndex(index);
    setStep("inspect");
  }

  async function handleComplete() {
    if (!inspection) return;

    // Check all required items have answers
    const unanswered = results.filter((r) => r.required && r.result === null);
    if (unanswered.length > 0) {
      toast.error(
        `${unanswered.length} required item(s) have not been answered.`,
      );
      return;
    }

    setSubmitting(true);
    try {
      // Save each result to the server
      for (const r of results) {
        if (r.result) {
          await safetyService.updateInspectionResult(inspection.id, r.item_id, {
            result: r.result,
            finding_notes: r.finding_notes || undefined,
            corrective_action_required: r.corrective_action_required,
          });
        }
      }

      // Complete the inspection
      await safetyService.completeInspection(inspection.id);
      toast.success("Inspection completed successfully");
      navigate(-1);
    } catch {
      toast.error("Failed to complete inspection");
    } finally {
      setSubmitting(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  const passCount = results.filter((r) => r.result === "pass").length;
  const failCount = results.filter((r) => r.result === "fail").length;
  const answeredCount = passCount + failCount;
  const totalCount = results.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-muted-foreground text-lg">Loading...</p>
      </div>
    );
  }

  // ---- STEP 1: Template selection ----
  if (step === "select") {
    return (
      <div className="max-w-lg mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">New Safety Inspection</h1>

        <Card className="p-5 space-y-5">
          <div className="space-y-2">
            <label
              htmlFor="template-select"
              className="text-sm font-medium block"
            >
              Inspection Template
            </label>
            <select
              id="template-select"
              value={selectedTemplateId}
              onChange={(e) => setSelectedTemplateId(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-3 text-base shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">-- Select a template --</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.template_name} ({t.inspection_type})
                </option>
              ))}
            </select>
          </div>

          {selectedTemplateId && (
            <p className="text-sm text-muted-foreground">
              {templates.find((t) => t.id === selectedTemplateId)?.items.length ?? 0}{" "}
              checklist items
            </p>
          )}

          <div className="space-y-2">
            <label
              htmlFor="equipment-id"
              className="text-sm font-medium block"
            >
              Equipment Identifier{" "}
              <span className="text-muted-foreground">(optional)</span>
            </label>
            <input
              id="equipment-id"
              type="text"
              value={equipmentIdentifier}
              onChange={(e) => setEquipmentIdentifier(e.target.value)}
              placeholder="e.g., Forklift #3, Line A Mixer"
              className="w-full rounded-md border border-input bg-background px-3 py-3 text-base shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <Button
            onClick={handleStartInspection}
            disabled={!selectedTemplateId || loading}
            className="w-full h-14 text-lg font-semibold"
          >
            Start Inspection
          </Button>
        </Card>
      </div>
    );
  }

  // ---- STEP 2: Inspect items one-by-one ----
  if (step === "inspect" && results.length > 0) {
    const item = results[currentIndex];

    return (
      <div className="max-w-lg mx-auto px-4 py-6">
        {/* Header / Progress */}
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-lg font-bold truncate mr-2">
            {inspection?.template_name ?? "Inspection"}
          </h1>
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            Item {currentIndex + 1} of {totalCount}
          </span>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-muted rounded-full h-2 mb-6">
          <div
            className="bg-primary rounded-full h-2 transition-all duration-300"
            style={{
              width: `${((currentIndex + 1) / totalCount) * 100}%`,
            }}
          />
        </div>

        <Card className="p-5 space-y-5">
          {/* Item text */}
          <div>
            <p className="text-lg font-medium leading-snug">{item.item_text}</p>
            <div className="flex flex-wrap gap-2 mt-2">
              {item.osha_reference && (
                <span className="inline-block text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">
                  OSHA: {item.osha_reference}
                </span>
              )}
              {item.required && (
                <span className="inline-block text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full">
                  Required
                </span>
              )}
            </div>
          </div>

          {/* Pass / Fail buttons */}
          <div className="grid grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => handleAnswer("pass")}
              className={`h-20 rounded-xl text-xl font-bold transition-all border-2 ${
                item.result === "pass"
                  ? "bg-green-600 text-white border-green-700 shadow-lg scale-[1.02]"
                  : "bg-green-50 text-green-700 border-green-300 hover:bg-green-100 active:bg-green-200"
              }`}
            >
              Pass
            </button>
            <button
              type="button"
              onClick={() => handleAnswer("fail")}
              className={`h-20 rounded-xl text-xl font-bold transition-all border-2 ${
                item.result === "fail"
                  ? "bg-red-600 text-white border-red-700 shadow-lg scale-[1.02]"
                  : "bg-red-50 text-red-700 border-red-300 hover:bg-red-100 active:bg-red-200"
              }`}
            >
              Fail
            </button>
          </div>

          {/* Fail details */}
          {item.result === "fail" && (
            <div className="space-y-4 border-t pt-4">
              <div className="space-y-2">
                <label
                  htmlFor="finding-notes"
                  className="text-sm font-medium block"
                >
                  Finding Notes
                </label>
                <textarea
                  id="finding-notes"
                  rows={3}
                  value={item.finding_notes}
                  onChange={(e) => handleNotesChange(e.target.value)}
                  placeholder="Describe the issue found..."
                  className="w-full rounded-md border border-input bg-background px-3 py-3 text-base shadow-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                />
              </div>

              <label className="flex items-center gap-3 cursor-pointer select-none">
                <button
                  type="button"
                  role="switch"
                  aria-checked={item.corrective_action_required}
                  onClick={handleCorrectiveToggle}
                  className={`relative inline-flex h-7 w-12 shrink-0 rounded-full transition-colors ${
                    item.corrective_action_required
                      ? "bg-red-600"
                      : "bg-muted"
                  }`}
                >
                  <span
                    className={`pointer-events-none block h-5 w-5 rounded-full bg-white shadow-sm ring-0 transition-transform mt-1 ml-1 ${
                      item.corrective_action_required
                        ? "translate-x-5"
                        : "translate-x-0"
                    }`}
                  />
                </button>
                <span className="text-sm font-medium">
                  Corrective action required
                </span>
              </label>
            </div>
          )}
        </Card>

        {/* Navigation buttons */}
        <div className="flex gap-3 mt-6">
          <Button
            variant="outline"
            onClick={handlePrev}
            disabled={currentIndex === 0}
            className="flex-1 h-14 text-base"
          >
            Previous
          </Button>
          <Button
            onClick={handleNext}
            className="flex-1 h-14 text-base font-semibold"
          >
            {currentIndex === results.length - 1 ? "Review" : "Next"}
          </Button>
        </div>
      </div>
    );
  }

  // ---- STEP 3: Review summary ----
  if (step === "review") {
    return (
      <div className="max-w-lg mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-2">Review Inspection</h1>
        <p className="text-muted-foreground mb-6">
          {inspection?.template_name}
          {inspection?.equipment_identifier &&
            ` \u2014 ${inspection.equipment_identifier}`}
        </p>

        {/* Summary stats */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <Card className="p-3 text-center">
            <p className="text-2xl font-bold">{answeredCount}</p>
            <p className="text-xs text-muted-foreground">Answered</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-2xl font-bold text-green-600">{passCount}</p>
            <p className="text-xs text-muted-foreground">Passed</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-2xl font-bold text-red-600">{failCount}</p>
            <p className="text-xs text-muted-foreground">Failed</p>
          </Card>
        </div>

        {/* Item list */}
        <div className="space-y-2 mb-6">
          {results.map((r, idx) => (
            <button
              key={r.item_id}
              type="button"
              onClick={() => handleEditItem(idx)}
              className="w-full text-left"
            >
              <Card
                className={`p-3 flex items-start gap-3 transition-colors hover:bg-muted/50 ${
                  r.result === "fail" ? "border-red-300" : ""
                }`}
              >
                {/* Status indicator */}
                <span
                  className={`mt-0.5 shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                    r.result === "pass"
                      ? "bg-green-100 text-green-700"
                      : r.result === "fail"
                        ? "bg-red-100 text-red-700"
                        : "bg-muted text-muted-foreground"
                  }`}
                >
                  {r.result === "pass"
                    ? "\u2713"
                    : r.result === "fail"
                      ? "\u2717"
                      : idx + 1}
                </span>

                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium leading-snug truncate">
                    {r.item_text}
                  </p>
                  {r.result === "fail" && r.finding_notes && (
                    <p className="text-xs text-red-600 mt-1 truncate">
                      {r.finding_notes}
                    </p>
                  )}
                  {r.corrective_action_required && (
                    <p className="text-xs text-red-700 font-semibold mt-0.5">
                      Corrective action required
                    </p>
                  )}
                </div>
              </Card>
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={() => {
              setCurrentIndex(0);
              setStep("inspect");
            }}
            className="flex-1 h-14 text-base"
          >
            Back to Items
          </Button>
          <Button
            onClick={handleComplete}
            disabled={submitting}
            className="flex-1 h-14 text-base font-semibold"
          >
            {submitting ? "Submitting..." : "Complete Inspection"}
          </Button>
        </div>
      </div>
    );
  }

  return null;
}
