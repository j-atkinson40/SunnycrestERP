import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import apiClient from "@/lib/api-client";
import type { SafetyProgram, SafetyProgramCreate, SafetyProgramUpdate } from "@/types/safety";
import {
  Sparkles,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Download,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Eye,
} from "lucide-react";

// ── Types ──

interface ProgramGeneration {
  id: string;
  year: number;
  month_number: number;
  topic_title: string | null;
  osha_standard: string | null;
  osha_scrape_status: string;
  generation_status: string;
  status: string;
  pdf_document_id: string | null;
  safety_program_id: string | null;
  generated_at: string | null;
  reviewed_at: string | null;
  created_at: string | null;
  error_message: string | null;
}

interface GenerationDetail {
  id: string;
  year: number;
  month_number: number;
  topic_title: string | null;
  osha_standard: string | null;
  osha_standard_label: string | null;
  osha_scrape_status: string;
  osha_scrape_url: string | null;
  generated_content: string | null;
  generated_html: string | null;
  generation_status: string;
  generation_model: string | null;
  generation_token_usage: Record<string, number> | null;
  generated_at: string | null;
  pdf_document_id: string | null;
  status: string;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  error_message: string | null;
}

// ── Tab type ──

type Tab = "generated" | "manual";

// ── Helpers ──

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

const MONTH_NAMES = [
  "", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function generationStatusBadge(status: string) {
  const map: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
    draft: { label: "Draft", className: "bg-gray-100 text-gray-800 border-gray-300", icon: <Clock className="h-3 w-3" /> },
    pending_review: { label: "Pending Review", className: "bg-amber-100 text-amber-800 border-amber-300", icon: <Eye className="h-3 w-3" /> },
    approved: { label: "Approved", className: "bg-green-100 text-green-800 border-green-300", icon: <CheckCircle className="h-3 w-3" /> },
    rejected: { label: "Rejected", className: "bg-red-100 text-red-800 border-red-300", icon: <XCircle className="h-3 w-3" /> },
  };
  const s = map[status] || map.draft;
  return (
    <Badge variant="outline" className={`${s.className} gap-1`}>
      {s.icon}
      {s.label}
    </Badge>
  );
}

function programStatusBadge(status: SafetyProgram["status"]) {
  const map: Record<SafetyProgram["status"], { label: string; className: string }> = {
    draft: { label: "Draft", className: "bg-gray-100 text-gray-800 border-gray-300" },
    active: { label: "Active", className: "bg-green-100 text-green-800 border-green-300" },
    under_review: { label: "Under Review", className: "bg-yellow-100 text-yellow-800 border-yellow-300" },
    archived: { label: "Archived", className: "bg-red-100 text-red-800 border-red-300" },
  };
  const s = map[status];
  return (
    <Badge variant="outline" className={s.className}>
      {s.label}
    </Badge>
  );
}

function reviewIndicator(nextReview: string | null) {
  if (!nextReview) return null;
  const daysUntil = Math.ceil(
    (new Date(nextReview).getTime() - Date.now()) / (1000 * 60 * 60 * 24),
  );
  if (daysUntil < 0) {
    return <span className="text-xs text-red-600 font-medium">Review overdue by {Math.abs(daysUntil)}d</span>;
  }
  if (daysUntil <= 30) {
    return <span className="text-xs text-amber-600 font-medium">Review due in {daysUntil}d</span>;
  }
  return <span className="text-xs text-muted-foreground">Review due {formatDate(nextReview)}</span>;
}

// ── Main Component ──

export default function SafetyProgramsPage() {
  const [tab, setTab] = useState<Tab>("generated");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Safety Programs</h1>
          <p className="text-muted-foreground">
            AI-generated and manual written safety programs
          </p>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === "generated"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("generated")}
        >
          <Sparkles className="h-4 w-4 inline mr-1.5" />
          AI Generated
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === "manual"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("manual")}
        >
          <FileText className="h-4 w-4 inline mr-1.5" />
          Manual Programs
        </button>
      </div>

      {tab === "generated" ? <GeneratedProgramsTab /> : <ManualProgramsTab />}
    </div>
  );
}

// ── AI Generated Programs Tab ──

function GeneratedProgramsTab() {
  const [generations, setGenerations] = useState<ProgramGeneration[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<GenerationDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [rejectNotes, setRejectNotes] = useState("");
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [rejectTargetId, setRejectTargetId] = useState<string | null>(null);

  async function loadGenerations() {
    setLoading(true);
    try {
      const { data } = await apiClient.get("/safety/programs/generations");
      setGenerations(data);
    } catch {
      toast.error("Failed to load generated programs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadGenerations();
  }, []);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const { data } = await apiClient.post("/safety/programs/generate");
      if (data.status === "skipped") {
        toast.info(`Generation skipped: ${data.reason}`);
      } else if (data.status === "failed") {
        toast.error(`Generation failed: ${data.error || "Unknown error"}`);
      } else {
        toast.success(`Safety program generated for ${data.topic || "this month"}`);
      }
      loadGenerations();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Generation failed";
      toast.error(msg);
    } finally {
      setGenerating(false);
    }
  }

  async function handleExpand(gen: ProgramGeneration) {
    if (expandedId === gen.id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(gen.id);
    setLoadingDetail(true);
    try {
      const { data } = await apiClient.get(`/safety/programs/generations/${gen.id}`);
      setDetail(data);
    } catch {
      toast.error("Failed to load generation detail");
    } finally {
      setLoadingDetail(false);
    }
  }

  async function handleApprove(genId: string) {
    setApproving(true);
    try {
      await apiClient.post(`/safety/programs/generations/${genId}/approve`);
      toast.success("Program approved and published");
      loadGenerations();
      if (expandedId === genId) {
        const { data } = await apiClient.get(`/safety/programs/generations/${genId}`);
        setDetail(data);
      }
    } catch {
      toast.error("Failed to approve program");
    } finally {
      setApproving(false);
    }
  }

  async function handleReject() {
    if (!rejectTargetId || !rejectNotes.trim()) return;
    setRejecting(true);
    try {
      await apiClient.post(`/safety/programs/generations/${rejectTargetId}/reject`, null, {
        params: { notes: rejectNotes },
      });
      toast.success("Program rejected");
      setShowRejectDialog(false);
      setRejectNotes("");
      setRejectTargetId(null);
      loadGenerations();
    } catch {
      toast.error("Failed to reject program");
    } finally {
      setRejecting(false);
    }
  }

  if (loading) {
    return <div className="py-12 text-center text-muted-foreground">Loading generated programs...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {generations.length} generated program{generations.length !== 1 ? "s" : ""}
        </p>
        <Button onClick={handleGenerate} disabled={generating}>
          <Sparkles className="h-4 w-4 mr-2" />
          {generating ? "Generating..." : "Generate This Month's Program"}
        </Button>
      </div>

      {generations.length === 0 ? (
        <Card className="p-8 text-center text-muted-foreground">
          <Sparkles className="h-8 w-8 mx-auto mb-3 text-muted-foreground/50" />
          <p>No AI-generated safety programs yet.</p>
          <p className="text-sm mt-1">
            Click "Generate This Month's Program" to create one from your training calendar.
          </p>
        </Card>
      ) : (
        generations.map((gen) => (
          <Card key={gen.id} className="overflow-hidden">
            <div
              className="p-4 cursor-pointer hover:bg-muted/30 transition-colors"
              onClick={() => handleExpand(gen)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  {expandedId === gen.id ? (
                    <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-medium">
                        {MONTH_NAMES[gen.month_number]} {gen.year}
                      </h3>
                      {generationStatusBadge(gen.status)}
                      {gen.generation_status === "failed" && (
                        <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200 gap-1">
                          <AlertTriangle className="h-3 w-3" />
                          Failed
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground truncate">
                      {gen.topic_title || "Unknown topic"}
                      {gen.osha_standard && <span className="ml-1">({gen.osha_standard})</span>}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {gen.pdf_document_id && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation();
                        window.open(`/api/v1/documents/${gen.pdf_document_id}/download`, "_blank");
                      }}
                    >
                      <Download className="h-3.5 w-3.5 mr-1" />
                      PDF
                    </Button>
                  )}
                  {gen.status === "pending_review" && (
                    <Button
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleApprove(gen.id);
                      }}
                      disabled={approving}
                    >
                      <CheckCircle className="h-3.5 w-3.5 mr-1" />
                      Approve
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {expandedId === gen.id && (
              <div className="border-t p-4 space-y-4 bg-muted/10" onClick={(e) => e.stopPropagation()}>
                {loadingDetail ? (
                  <p className="text-sm text-muted-foreground">Loading details...</p>
                ) : detail ? (
                  <>
                    {/* Status summary */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div>
                        <span className="text-muted-foreground">OSHA Scrape:</span>{" "}
                        <Badge variant="outline" className="ml-1">
                          {detail.osha_scrape_status}
                        </Badge>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Generation:</span>{" "}
                        <Badge variant="outline" className="ml-1">
                          {detail.generation_status}
                        </Badge>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Model:</span>{" "}
                        <span>{detail.generation_model || "N/A"}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Generated:</span>{" "}
                        <span>{formatDate(detail.generated_at)}</span>
                      </div>
                    </div>

                    {detail.error_message && (
                      <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-800">
                        <AlertTriangle className="h-4 w-4 inline mr-1" />
                        {detail.error_message}
                      </div>
                    )}

                    {detail.review_notes && (
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded text-sm">
                        <strong>Review notes:</strong> {detail.review_notes}
                        {detail.reviewed_by_name && (
                          <span className="text-muted-foreground ml-2">
                            — {detail.reviewed_by_name}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Content preview */}
                    {detail.generated_content && (
                      <div>
                        <Label className="text-sm font-medium mb-2 block">Generated Content Preview</Label>
                        <div className="max-h-[400px] overflow-y-auto border rounded p-4 bg-background text-sm whitespace-pre-wrap">
                          {detail.generated_content.slice(0, 3000)}
                          {detail.generated_content.length > 3000 && (
                            <p className="text-muted-foreground mt-2 italic">
                              ... content truncated. Download PDF for full program.
                            </p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-2 pt-2">
                      {detail.status === "pending_review" && (
                        <>
                          <Button
                            size="sm"
                            onClick={() => handleApprove(gen.id)}
                            disabled={approving}
                          >
                            <CheckCircle className="h-4 w-4 mr-1" />
                            {approving ? "Approving..." : "Approve & Publish"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-red-600 border-red-200 hover:bg-red-50"
                            onClick={() => {
                              setRejectTargetId(gen.id);
                              setShowRejectDialog(true);
                            }}
                          >
                            <XCircle className="h-4 w-4 mr-1" />
                            Reject
                          </Button>
                        </>
                      )}
                      {detail.status === "rejected" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={async () => {
                            try {
                              await apiClient.post(`/safety/programs/generate-for-topic/${detail.id.split("-")[0]}`);
                              toast.success("Regenerating...");
                              loadGenerations();
                            } catch {
                              toast.error("Regeneration failed");
                            }
                          }}
                        >
                          <RefreshCw className="h-4 w-4 mr-1" />
                          Regenerate
                        </Button>
                      )}
                    </div>
                  </>
                ) : null}
              </div>
            )}
          </Card>
        ))
      )}

      {/* Reject dialog */}
      <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Safety Program</DialogTitle>
            <DialogDescription>
              Provide notes explaining why this program needs revision.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <textarea
              className="flex min-h-[100px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
              value={rejectNotes}
              onChange={(e) => setRejectNotes(e.target.value)}
              placeholder="Enter rejection notes..."
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRejectDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={rejecting || !rejectNotes.trim()}
            >
              {rejecting ? "Rejecting..." : "Reject Program"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Manual Programs Tab (existing functionality) ──

function ManualProgramsTab() {
  const [programs, setPrograms] = useState<SafetyProgram[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({
    program_name: "",
    osha_standard: "",
    osha_standard_code: "",
    description: "",
    applicable_roles: "",
    content: "",
  });
  const [creating, setCreating] = useState(false);

  // Expanded / editing
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [savingContent, setSavingContent] = useState(false);
  const [reviewingId, setReviewingId] = useState<string | null>(null);

  async function loadPrograms() {
    setLoading(true);
    setError(null);
    try {
      const data = await safetyService.listPrograms();
      setPrograms(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load programs";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPrograms();
  }, []);

  async function handleCreate() {
    setCreating(true);
    try {
      const roles = form.applicable_roles
        .split(",")
        .map((r) => r.trim())
        .filter(Boolean);
      const payload: SafetyProgramCreate = {
        program_name: form.program_name,
        osha_standard: form.osha_standard || undefined,
        osha_standard_code: form.osha_standard_code || undefined,
        description: form.description || undefined,
        content: form.content || undefined,
        applicable_job_roles: roles.length > 0 ? roles : undefined,
      };
      await safetyService.createProgram(payload);
      toast.success("Program created");
      setCreateOpen(false);
      setForm({
        program_name: "",
        osha_standard: "",
        osha_standard_code: "",
        description: "",
        applicable_roles: "",
        content: "",
      });
      loadPrograms();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to create program");
    } finally {
      setCreating(false);
    }
  }

  function handleExpand(program: SafetyProgram) {
    if (expandedId === program.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(program.id);
    setEditContent(program.content || "");
  }

  async function handleSaveContent(programId: string) {
    setSavingContent(true);
    try {
      const payload: SafetyProgramUpdate = { content: editContent };
      await safetyService.updateProgram(programId, payload);
      toast.success("Program content saved");
      loadPrograms();
    } catch {
      toast.error("Failed to save program content");
    } finally {
      setSavingContent(false);
    }
  }

  async function handleReview(programId: string) {
    setReviewingId(programId);
    try {
      await safetyService.reviewProgram(programId);
      toast.success("Program marked as reviewed");
      loadPrograms();
    } catch {
      toast.error("Failed to mark as reviewed");
    } finally {
      setReviewingId(null);
    }
  }

  if (loading) {
    return <div className="py-12 text-center text-muted-foreground">Loading safety programs...</div>;
  }

  if (error && programs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={() => loadPrograms()}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{programs.length} manual programs</p>
        <Dialog
          open={createOpen}
          onOpenChange={(open) => {
            setCreateOpen(open);
            if (!open) setForm({
              program_name: "",
              osha_standard: "",
              osha_standard_code: "",
              description: "",
              applicable_roles: "",
              content: "",
            });
          }}
        >
          <DialogTrigger render={<Button variant="outline" />}>Add Program</DialogTrigger>
          <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Safety Program</DialogTitle>
              <DialogDescription>Create a new written safety program.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Program Name *</Label>
                <Input
                  value={form.program_name}
                  onChange={(e) => setForm({ ...form, program_name: e.target.value })}
                  placeholder="e.g. Hazard Communication Program"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>OSHA Standard</Label>
                  <Input
                    value={form.osha_standard}
                    onChange={(e) => setForm({ ...form, osha_standard: e.target.value })}
                    placeholder="e.g. Hazard Communication"
                  />
                </div>
                <div className="space-y-2">
                  <Label>OSHA Code</Label>
                  <Input
                    value={form.osha_standard_code}
                    onChange={(e) => setForm({ ...form, osha_standard_code: e.target.value })}
                    placeholder="e.g. 29 CFR 1910.1200"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Brief description"
                />
              </div>
              <div className="space-y-2">
                <Label>Applicable Roles (comma-separated)</Label>
                <Input
                  value={form.applicable_roles}
                  onChange={(e) => setForm({ ...form, applicable_roles: e.target.value })}
                  placeholder="e.g. Operator, Maintenance"
                />
              </div>
              <div className="space-y-2">
                <Label>Program Content</Label>
                <textarea
                  className="flex min-h-[120px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                  value={form.content}
                  onChange={(e) => setForm({ ...form, content: e.target.value })}
                  placeholder="Write the program content here..."
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={creating || !form.program_name.trim()}>
                {creating ? "Creating..." : "Create Program"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-3">
        {programs.length === 0 ? (
          <Card className="p-8 text-center text-muted-foreground">
            No manual safety programs yet. Click "Add Program" to create one.
          </Card>
        ) : (
          programs.map((program) => (
            <Card
              key={program.id}
              className="p-4 cursor-pointer hover:bg-muted/30 transition-colors"
              onClick={() => handleExpand(program)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-medium truncate">{program.program_name}</h3>
                    {programStatusBadge(program.status)}
                    <Badge variant="outline" className="text-xs">v{program.version}</Badge>
                  </div>
                  {program.osha_standard && (
                    <p className="text-sm text-muted-foreground">
                      {program.osha_standard}
                      {program.osha_standard_code && <span className="ml-1">({program.osha_standard_code})</span>}
                    </p>
                  )}
                  {program.description && (
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-1">{program.description}</p>
                  )}
                  <div className="flex items-center gap-4 mt-2">
                    {reviewIndicator(program.next_review_due_at)}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleReview(program.id);
                    }}
                    disabled={reviewingId === program.id}
                  >
                    {reviewingId === program.id ? "..." : "Mark Reviewed"}
                  </Button>
                </div>
              </div>

              {expandedId === program.id && (
                <div className="mt-4 pt-4 border-t space-y-3" onClick={(e) => e.stopPropagation()}>
                  <Label className="text-sm font-medium">Program Content</Label>
                  <textarea
                    className="flex min-h-[200px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    placeholder="No content written yet..."
                  />
                  <div className="flex items-center gap-2">
                    <Button size="sm" onClick={() => handleSaveContent(program.id)} disabled={savingContent}>
                      {savingContent ? "Saving..." : "Save Content"}
                    </Button>
                    <span className="text-xs text-muted-foreground">
                      Last reviewed: {formatDate(program.last_reviewed_at)}
                    </span>
                  </div>
                </div>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
