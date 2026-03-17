import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { safetyService } from "@/services/safety-service";
import type { LOTOProcedure, LOTOCreate, EnergySource, LOTOStep } from "@/types/safety";

const ENERGY_TYPES = [
  "electrical",
  "hydraulic",
  "pneumatic",
  "gravitational",
  "thermal",
  "chemical",
];

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

function reviewStatusBadge(nextReviewDue: string | null) {
  if (!nextReviewDue) {
    return (
      <Badge variant="outline" className="bg-gray-100 text-gray-800 border-gray-300">
        No Review Date
      </Badge>
    );
  }
  const isOverdue = new Date(nextReviewDue) < new Date();
  return isOverdue ? (
    <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300">
      Review Overdue
    </Badge>
  ) : (
    <Badge variant="outline" className="bg-green-100 text-green-800 border-green-300">
      Current
    </Badge>
  );
}

const emptyEnergySource: EnergySource = {
  type: "electrical",
  location: "",
  magnitude: "",
  isolation_device: "",
  verification_method: "",
};

const emptyStep: LOTOStep = {
  step_number: 1,
  action: "",
};

export default function SafetyLOTOPage() {
  const [procedures, setProcedures] = useState<LOTOProcedure[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create dialog & wizard
  const [createOpen, setCreateOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [machineName, setMachineName] = useState("");
  const [machineLocation, setMachineLocation] = useState("");
  const [procedureNumber, setProcedureNumber] = useState("");
  const [energySources, setEnergySources] = useState<EnergySource[]>([{ ...emptyEnergySource }]);
  const [steps, setSteps] = useState<LOTOStep[]>([{ ...emptyStep }]);
  const [creating, setCreating] = useState(false);

  // Detail view
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedProcedure, setSelectedProcedure] = useState<LOTOProcedure | null>(null);
  const [reviewing, setReviewing] = useState(false);

  async function loadProcedures() {
    setLoading(true);
    setError(null);
    try {
      const data = await safetyService.listLOTO(false);
      setProcedures(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load LOTO procedures";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProcedures();
  }, []);

  function resetWizard() {
    setWizardStep(1);
    setMachineName("");
    setMachineLocation("");
    setProcedureNumber("");
    setEnergySources([{ ...emptyEnergySource }]);
    setSteps([{ ...emptyStep }]);
  }

  function addEnergySource() {
    setEnergySources([...energySources, { ...emptyEnergySource }]);
  }

  function removeEnergySource(index: number) {
    if (energySources.length <= 1) return;
    setEnergySources(energySources.filter((_, i) => i !== index));
  }

  function updateEnergySource(index: number, field: keyof EnergySource, value: string) {
    const updated = [...energySources];
    updated[index] = { ...updated[index], [field]: value };
    setEnergySources(updated);
  }

  function addStep() {
    setSteps([...steps, { step_number: steps.length + 1, action: "" }]);
  }

  function removeStep(index: number) {
    if (steps.length <= 1) return;
    const updated = steps.filter((_, i) => i !== index).map((s, i) => ({
      ...s,
      step_number: i + 1,
    }));
    setSteps(updated);
  }

  function updateStep(index: number, action: string) {
    const updated = [...steps];
    updated[index] = { ...updated[index], action };
    setSteps(updated);
  }

  function moveStep(index: number, direction: -1 | 1) {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= steps.length) return;
    const updated = [...steps];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    setSteps(updated.map((s, i) => ({ ...s, step_number: i + 1 })));
  }

  async function handleCreate() {
    setCreating(true);
    try {
      const payload: LOTOCreate = {
        machine_name: machineName,
        machine_location: machineLocation || undefined,
        procedure_number: procedureNumber,
        energy_sources: energySources,
        steps: steps,
      };
      await safetyService.createLOTO(payload);
      toast.success("LOTO procedure created");
      setCreateOpen(false);
      resetWizard();
      loadProcedures();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to create procedure");
    } finally {
      setCreating(false);
    }
  }

  async function handleViewDetails(proc: LOTOProcedure) {
    if (selectedId === proc.id) {
      setSelectedId(null);
      setSelectedProcedure(null);
      return;
    }
    try {
      const full = await safetyService.getLOTO(proc.id);
      setSelectedProcedure(full);
      setSelectedId(proc.id);
    } catch {
      toast.error("Failed to load procedure details");
    }
  }

  async function handleReview(id: string) {
    setReviewing(true);
    try {
      const updated = await safetyService.reviewLOTO(id);
      setSelectedProcedure(updated);
      toast.success("Procedure marked as reviewed");
      loadProcedures();
    } catch {
      toast.error("Failed to mark as reviewed");
    } finally {
      setReviewing(false);
    }
  }

  const canAdvanceStep1 = machineName.trim() && procedureNumber.trim();
  const canAdvanceStep2 = energySources.every((es) => es.type);
  const canAdvanceStep3 = steps.every((s) => s.action.trim());

  if (error && procedures.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={() => loadProcedures()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">LOTO Procedures</h1>
          <p className="text-muted-foreground">
            {procedures.length} procedure{procedures.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Dialog
          open={createOpen}
          onOpenChange={(open) => {
            setCreateOpen(open);
            if (!open) resetWizard();
          }}
        >
          <DialogTrigger render={<Button />}>New Procedure</DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>New LOTO Procedure</DialogTitle>
              <DialogDescription>
                Step {wizardStep} of 4 &mdash;{" "}
                {wizardStep === 1
                  ? "Machine Information"
                  : wizardStep === 2
                    ? "Energy Sources"
                    : wizardStep === 3
                      ? "Procedure Steps"
                      : "Review & Save"}
              </DialogDescription>
            </DialogHeader>

            {/* Step 1: Machine Info */}
            {wizardStep === 1 && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Machine Name *</Label>
                  <Input
                    value={machineName}
                    onChange={(e) => setMachineName(e.target.value)}
                    placeholder="e.g. Hydraulic Press #2"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Machine Location</Label>
                  <Input
                    value={machineLocation}
                    onChange={(e) => setMachineLocation(e.target.value)}
                    placeholder="e.g. Building A, Bay 5"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Procedure Number *</Label>
                  <Input
                    value={procedureNumber}
                    onChange={(e) => setProcedureNumber(e.target.value)}
                    placeholder="e.g. LOTO-2024-001"
                  />
                </div>
              </div>
            )}

            {/* Step 2: Energy Sources */}
            {wizardStep === 2 && (
              <div className="space-y-4">
                {energySources.map((es, index) => (
                  <Card key={index} className="p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Energy Source {index + 1}</span>
                      {energySources.length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => removeEnergySource(index)}
                        >
                          Remove
                        </Button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Type *</Label>
                        <select
                          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                          value={es.type}
                          onChange={(e) => updateEnergySource(index, "type", e.target.value)}
                        >
                          {ENERGY_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t.charAt(0).toUpperCase() + t.slice(1)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Location</Label>
                        <Input
                          value={es.location || ""}
                          onChange={(e) => updateEnergySource(index, "location", e.target.value)}
                          placeholder="Where is this source?"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Magnitude</Label>
                        <Input
                          value={es.magnitude || ""}
                          onChange={(e) => updateEnergySource(index, "magnitude", e.target.value)}
                          placeholder="e.g. 480V, 3000 PSI"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Isolation Device</Label>
                        <Input
                          value={es.isolation_device || ""}
                          onChange={(e) =>
                            updateEnergySource(index, "isolation_device", e.target.value)
                          }
                          placeholder="e.g. Breaker #14"
                        />
                      </div>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Verification Method</Label>
                      <Input
                        value={es.verification_method || ""}
                        onChange={(e) =>
                          updateEnergySource(index, "verification_method", e.target.value)
                        }
                        placeholder="How to verify energy is isolated"
                      />
                    </div>
                  </Card>
                ))}
                <Button variant="outline" size="sm" onClick={addEnergySource}>
                  + Add Energy Source
                </Button>
              </div>
            )}

            {/* Step 3: Procedure Steps */}
            {wizardStep === 3 && (
              <div className="space-y-3">
                {steps.map((step, index) => (
                  <div key={index} className="flex items-start gap-2">
                    <span className="mt-2 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                      {step.step_number}
                    </span>
                    <textarea
                      className="flex min-h-[40px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                      value={step.action}
                      onChange={(e) => updateStep(index, e.target.value)}
                      placeholder="Describe this step..."
                    />
                    <div className="flex flex-col gap-0.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1 text-xs"
                        disabled={index === 0}
                        onClick={() => moveStep(index, -1)}
                      >
                        Up
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1 text-xs"
                        disabled={index === steps.length - 1}
                        onClick={() => moveStep(index, 1)}
                      >
                        Dn
                      </Button>
                      {steps.length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-1 text-xs text-destructive"
                          onClick={() => removeStep(index)}
                        >
                          X
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
                <Button variant="outline" size="sm" onClick={addStep}>
                  + Add Step
                </Button>
              </div>
            )}

            {/* Step 4: Review */}
            {wizardStep === 4 && (
              <div className="space-y-4">
                <Card className="p-4 space-y-2">
                  <h3 className="text-sm font-semibold">Machine</h3>
                  <p className="text-sm">
                    {machineName} {machineLocation && `(${machineLocation})`}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Procedure #: {procedureNumber}
                  </p>
                </Card>
                <Card className="p-4 space-y-2">
                  <h3 className="text-sm font-semibold">
                    Energy Sources ({energySources.length})
                  </h3>
                  {energySources.map((es, i) => (
                    <div key={i} className="text-sm text-muted-foreground">
                      {i + 1}. <span className="capitalize">{es.type}</span>
                      {es.magnitude && ` - ${es.magnitude}`}
                      {es.isolation_device && ` (${es.isolation_device})`}
                    </div>
                  ))}
                </Card>
                <Card className="p-4 space-y-2">
                  <h3 className="text-sm font-semibold">Steps ({steps.length})</h3>
                  {steps.map((s) => (
                    <div key={s.step_number} className="text-sm text-muted-foreground">
                      {s.step_number}. {s.action}
                    </div>
                  ))}
                </Card>
              </div>
            )}

            <DialogFooter>
              {wizardStep > 1 && (
                <Button variant="outline" onClick={() => setWizardStep(wizardStep - 1)}>
                  Back
                </Button>
              )}
              {wizardStep < 4 ? (
                <Button
                  onClick={() => setWizardStep(wizardStep + 1)}
                  disabled={
                    (wizardStep === 1 && !canAdvanceStep1) ||
                    (wizardStep === 2 && !canAdvanceStep2) ||
                    (wizardStep === 3 && !canAdvanceStep3)
                  }
                >
                  Next
                </Button>
              ) : (
                <Button onClick={handleCreate} disabled={creating}>
                  {creating ? "Creating..." : "Save Procedure"}
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Machine Name</TableHead>
              <TableHead>Procedure #</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Energy Sources</TableHead>
              <TableHead>Review Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  Loading procedures...
                </TableCell>
              </TableRow>
            ) : procedures.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                  No LOTO procedures found
                </TableCell>
              </TableRow>
            ) : (
              procedures.map((proc) => (
                <>
                  <TableRow
                    key={proc.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleViewDetails(proc)}
                  >
                    <TableCell className="font-medium">{proc.machine_name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {proc.procedure_number}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {proc.machine_location || "\u2014"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {proc.energy_sources.length} source
                        {proc.energy_sources.length !== 1 ? "s" : ""}
                      </Badge>
                    </TableCell>
                    <TableCell>{reviewStatusBadge(proc.next_review_due_at)}</TableCell>
                  </TableRow>
                  {selectedId === proc.id && selectedProcedure && (
                    <TableRow key={`${proc.id}-detail`}>
                      <TableCell colSpan={5} className="bg-muted/30 p-0">
                        <Card className="m-3 p-4 space-y-4">
                          <div className="flex items-center justify-between">
                            <h3 className="font-semibold">
                              {selectedProcedure.machine_name} &mdash;{" "}
                              {selectedProcedure.procedure_number}
                            </h3>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleReview(selectedProcedure.id)}
                              disabled={reviewing}
                            >
                              {reviewing ? "Reviewing..." : "Mark Reviewed"}
                            </Button>
                          </div>

                          <div className="text-sm text-muted-foreground">
                            Last reviewed: {formatDate(selectedProcedure.last_reviewed_at)} | Next
                            review: {formatDate(selectedProcedure.next_review_due_at)}
                          </div>

                          <div>
                            <h4 className="text-sm font-medium mb-2">Energy Sources</h4>
                            <div className="space-y-2">
                              {selectedProcedure.energy_sources.map((es, i) => (
                                <div
                                  key={i}
                                  className="rounded-md border p-2 text-sm grid grid-cols-2 gap-1"
                                >
                                  <div>
                                    <span className="font-medium">Type:</span>{" "}
                                    <span className="capitalize">{es.type}</span>
                                  </div>
                                  {es.magnitude && (
                                    <div>
                                      <span className="font-medium">Magnitude:</span>{" "}
                                      {es.magnitude}
                                    </div>
                                  )}
                                  {es.location && (
                                    <div>
                                      <span className="font-medium">Location:</span>{" "}
                                      {es.location}
                                    </div>
                                  )}
                                  {es.isolation_device && (
                                    <div>
                                      <span className="font-medium">Isolation:</span>{" "}
                                      {es.isolation_device}
                                    </div>
                                  )}
                                  {es.verification_method && (
                                    <div className="col-span-2">
                                      <span className="font-medium">Verification:</span>{" "}
                                      {es.verification_method}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>

                          <div>
                            <h4 className="text-sm font-medium mb-2">Procedure Steps</h4>
                            <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
                              {selectedProcedure.steps.map((s) => (
                                <li key={s.step_number}>{s.action}</li>
                              ))}
                            </ol>
                          </div>
                        </Card>
                      </TableCell>
                    </TableRow>
                  )}
                </>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
