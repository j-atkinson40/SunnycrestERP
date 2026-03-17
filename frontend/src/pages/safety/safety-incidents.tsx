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
import type { SafetyIncident, IncidentCreate, IncidentUpdate } from "@/types/safety";

const INCIDENT_TYPES = [
  { value: "injury", label: "Injury" },
  { value: "illness", label: "Illness" },
  { value: "near_miss", label: "Near Miss" },
  { value: "property_damage", label: "Property Damage" },
  { value: "environmental", label: "Environmental" },
];

const STATUSES = [
  { value: "reported", label: "Reported" },
  { value: "investigating", label: "Investigating" },
  { value: "corrective_actions", label: "Corrective Actions" },
  { value: "closed", label: "Closed" },
];

const MEDICAL_TREATMENTS = [
  { value: "none", label: "None" },
  { value: "first_aid_only", label: "First Aid Only" },
  { value: "medical_treatment", label: "Medical Treatment" },
  { value: "hospitalization", label: "Hospitalization" },
  { value: "fatality", label: "Fatality" },
];

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

function incidentTypeBadge(type: string) {
  const map: Record<string, { label: string; className: string }> = {
    injury: { label: "Injury", className: "bg-red-100 text-red-800 border-red-300" },
    illness: { label: "Illness", className: "bg-purple-100 text-purple-800 border-purple-300" },
    near_miss: { label: "Near Miss", className: "bg-amber-100 text-amber-800 border-amber-300" },
    property_damage: { label: "Property Damage", className: "bg-orange-100 text-orange-800 border-orange-300" },
    environmental: { label: "Environmental", className: "bg-teal-100 text-teal-800 border-teal-300" },
  };
  const s = map[type] ?? { label: type.replace(/_/g, " "), className: "bg-gray-100 text-gray-800 border-gray-300" };
  return (
    <Badge variant="outline" className={s.className}>
      {s.label}
    </Badge>
  );
}

function statusBadge(status: string) {
  const map: Record<string, { label: string; className: string }> = {
    reported: { label: "Reported", className: "bg-blue-100 text-blue-800 border-blue-300" },
    investigating: { label: "Investigating", className: "bg-amber-100 text-amber-800 border-amber-300" },
    corrective_actions: { label: "Corrective Actions", className: "bg-orange-100 text-orange-800 border-orange-300" },
    closed: { label: "Closed", className: "bg-green-100 text-green-800 border-green-300" },
  };
  const s = map[status] ?? { label: status, className: "bg-gray-100 text-gray-800 border-gray-300" };
  return (
    <Badge variant="outline" className={s.className}>
      {s.label}
    </Badge>
  );
}

const emptyForm: IncidentCreate = {
  incident_type: "injury",
  incident_date: new Date().toISOString().slice(0, 10),
  incident_time: "",
  location: "",
  involved_employee_id: "",
  witnesses: "",
  description: "",
  immediate_cause: "",
  medical_treatment: "none",
};

export default function SafetyIncidentsPage() {
  const [incidents, setIncidents] = useState<SafetyIncident[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filterType, setFilterType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<IncidentCreate>({ ...emptyForm });
  const [creating, setCreating] = useState(false);

  // Expanded row
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedIncident, setExpandedIncident] = useState<SafetyIncident | null>(null);
  const [investigationForm, setInvestigationForm] = useState({
    root_cause: "",
    corrective_actions: "",
    investigated_by: "",
  });
  const [saving, setSaving] = useState(false);
  const [closing, setClosing] = useState(false);

  async function loadIncidents() {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = {};
      if (filterType) params.incident_type = filterType;
      if (filterStatus) params.status = filterStatus;
      const data = await safetyService.listIncidents(params);
      setIncidents(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load incidents";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadIncidents();
  }, [filterType, filterStatus]);

  async function handleCreate() {
    setCreating(true);
    try {
      const payload: IncidentCreate = {
        ...form,
        incident_time: form.incident_time || undefined,
        involved_employee_id: form.involved_employee_id || undefined,
        witnesses: form.witnesses || undefined,
        immediate_cause: form.immediate_cause || undefined,
      };
      await safetyService.createIncident(payload);
      toast.success("Incident reported successfully");
      setCreateOpen(false);
      setForm({ ...emptyForm });
      loadIncidents();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to report incident");
    } finally {
      setCreating(false);
    }
  }

  async function handleRowClick(incident: SafetyIncident) {
    if (expandedId === incident.id) {
      setExpandedId(null);
      setExpandedIncident(null);
      return;
    }
    try {
      const full = await safetyService.getIncident(incident.id);
      setExpandedIncident(full);
      setExpandedId(incident.id);
      setInvestigationForm({
        root_cause: full.root_cause || "",
        corrective_actions: full.corrective_actions || "",
        investigated_by: full.investigated_by || "",
      });
    } catch {
      toast.error("Failed to load incident details");
    }
  }

  async function handleSaveInvestigation() {
    if (!expandedId) return;
    setSaving(true);
    try {
      const payload: IncidentUpdate = {
        root_cause: investigationForm.root_cause || undefined,
        corrective_actions: investigationForm.corrective_actions || undefined,
        investigated_by: investigationForm.investigated_by || undefined,
      };
      const updated = await safetyService.updateIncident(expandedId, payload);
      setExpandedIncident(updated);
      toast.success("Investigation details saved");
      loadIncidents();
    } catch {
      toast.error("Failed to save investigation");
    } finally {
      setSaving(false);
    }
  }

  async function handleClose() {
    if (!expandedId) return;
    setClosing(true);
    try {
      await safetyService.closeIncident(expandedId);
      toast.success("Incident closed");
      setExpandedId(null);
      setExpandedIncident(null);
      loadIncidents();
    } catch {
      toast.error("Failed to close incident");
    } finally {
      setClosing(false);
    }
  }

  if (error && incidents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={() => loadIncidents()}>
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
          <h1 className="text-2xl font-bold tracking-tight">Safety Incidents</h1>
          <p className="text-muted-foreground">{total} incidents on record</p>
        </div>
        <Dialog
          open={createOpen}
          onOpenChange={(open) => {
            setCreateOpen(open);
            if (!open) setForm({ ...emptyForm });
          }}
        >
          <DialogTrigger render={<Button />}>Report Incident</DialogTrigger>
          <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Report Incident</DialogTitle>
              <DialogDescription>
                Record a new safety incident. All required fields are marked.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Incident Type *</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={form.incident_type}
                  onChange={(e) => setForm({ ...form, incident_type: e.target.value })}
                >
                  {INCIDENT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Date *</Label>
                  <Input
                    type="date"
                    value={form.incident_date}
                    onChange={(e) => setForm({ ...form, incident_date: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Time</Label>
                  <Input
                    type="time"
                    value={form.incident_time || ""}
                    onChange={(e) => setForm({ ...form, incident_time: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Location *</Label>
                <Input
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  placeholder="e.g. Warehouse Bay 3"
                />
              </div>
              <div className="space-y-2">
                <Label>Involved Employee ID</Label>
                <Input
                  value={form.involved_employee_id || ""}
                  onChange={(e) => setForm({ ...form, involved_employee_id: e.target.value })}
                  placeholder="Employee ID (optional)"
                />
              </div>
              <div className="space-y-2">
                <Label>Description *</Label>
                <textarea
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Describe what happened..."
                />
              </div>
              <div className="space-y-2">
                <Label>Immediate Cause</Label>
                <Input
                  value={form.immediate_cause || ""}
                  onChange={(e) => setForm({ ...form, immediate_cause: e.target.value })}
                  placeholder="What directly caused the incident?"
                />
              </div>
              <div className="space-y-2">
                <Label>Medical Treatment</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={form.medical_treatment || "none"}
                  onChange={(e) => setForm({ ...form, medical_treatment: e.target.value })}
                >
                  {MEDICAL_TREATMENTS.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Witnesses</Label>
                <Input
                  value={form.witnesses || ""}
                  onChange={(e) => setForm({ ...form, witnesses: e.target.value })}
                  placeholder="Witness names (optional)"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={creating || !form.incident_date || !form.location || !form.description}
              >
                {creating ? "Submitting..." : "Report Incident"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="">All Types</option>
          {INCIDENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
        >
          <option value="">All Statuses</option>
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Employee</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>OSHA</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8">
                  Loading incidents...
                </TableCell>
              </TableRow>
            ) : incidents.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No incidents found
                </TableCell>
              </TableRow>
            ) : (
              incidents.map((incident) => (
                <>
                  <TableRow
                    key={incident.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleRowClick(incident)}
                  >
                    <TableCell>{formatDate(incident.incident_date)}</TableCell>
                    <TableCell>{incidentTypeBadge(incident.incident_type)}</TableCell>
                    <TableCell className="text-muted-foreground">{incident.location}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {incident.involved_employee_name || "\u2014"}
                    </TableCell>
                    <TableCell>{statusBadge(incident.status)}</TableCell>
                    <TableCell>
                      {incident.osha_recordable ? (
                        <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300">
                          Recordable
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">No</span>
                      )}
                    </TableCell>
                  </TableRow>
                  {expandedId === incident.id && expandedIncident && (
                    <TableRow key={`${incident.id}-detail`}>
                      <TableCell colSpan={6} className="bg-muted/30 p-0">
                        <Card className="m-3 p-4">
                          <div className="space-y-4">
                            <div>
                              <h3 className="text-sm font-semibold mb-1">Description</h3>
                              <p className="text-sm text-muted-foreground">
                                {expandedIncident.description}
                              </p>
                            </div>
                            {expandedIncident.immediate_cause && (
                              <div>
                                <h3 className="text-sm font-semibold mb-1">Immediate Cause</h3>
                                <p className="text-sm text-muted-foreground">
                                  {expandedIncident.immediate_cause}
                                </p>
                              </div>
                            )}
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="font-medium">Medical Treatment:</span>{" "}
                                <span className="text-muted-foreground capitalize">
                                  {expandedIncident.medical_treatment.replace(/_/g, " ")}
                                </span>
                              </div>
                              <div>
                                <span className="font-medium">Days Away:</span>{" "}
                                <span className="text-muted-foreground">
                                  {expandedIncident.days_away_from_work}
                                </span>
                              </div>
                            </div>

                            <hr />

                            <h3 className="text-sm font-semibold">Investigation</h3>
                            <div className="space-y-3">
                              <div className="space-y-1">
                                <Label className="text-xs">Root Cause</Label>
                                <textarea
                                  className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                                  value={investigationForm.root_cause}
                                  onChange={(e) =>
                                    setInvestigationForm({
                                      ...investigationForm,
                                      root_cause: e.target.value,
                                    })
                                  }
                                  placeholder="Root cause analysis..."
                                />
                              </div>
                              <div className="space-y-1">
                                <Label className="text-xs">Corrective Actions</Label>
                                <textarea
                                  className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                                  value={investigationForm.corrective_actions}
                                  onChange={(e) =>
                                    setInvestigationForm({
                                      ...investigationForm,
                                      corrective_actions: e.target.value,
                                    })
                                  }
                                  placeholder="Actions taken to prevent recurrence..."
                                />
                              </div>
                              <div className="space-y-1">
                                <Label className="text-xs">Investigated By</Label>
                                <Input
                                  value={investigationForm.investigated_by}
                                  onChange={(e) =>
                                    setInvestigationForm({
                                      ...investigationForm,
                                      investigated_by: e.target.value,
                                    })
                                  }
                                  placeholder="Name of investigator"
                                />
                              </div>
                            </div>

                            <div className="flex items-center gap-2">
                              <Button
                                size="sm"
                                onClick={handleSaveInvestigation}
                                disabled={saving}
                              >
                                {saving ? "Saving..." : "Save Investigation"}
                              </Button>
                              {expandedIncident.status !== "closed" && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={handleClose}
                                  disabled={closing}
                                >
                                  {closing ? "Closing..." : "Close Incident"}
                                </Button>
                              )}
                            </div>
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
