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
import type { SafetyProgram, SafetyProgramCreate, SafetyProgramUpdate } from "@/types/safety";

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

function programStatusBadge(status: SafetyProgram["status"]) {
  const map: Record<SafetyProgram["status"], { label: string; className: string }> = {
    draft: { label: "Draft", className: "bg-gray-100 text-gray-800 border-gray-300" },
    active: { label: "Active", className: "bg-green-100 text-green-800 border-green-300" },
    under_review: {
      label: "Under Review",
      className: "bg-yellow-100 text-yellow-800 border-yellow-300",
    },
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
    return (
      <span className="text-xs text-red-600 font-medium">
        Review overdue by {Math.abs(daysUntil)}d
      </span>
    );
  }
  if (daysUntil <= 30) {
    return (
      <span className="text-xs text-amber-600 font-medium">
        Review due in {daysUntil}d
      </span>
    );
  }
  return (
    <span className="text-xs text-muted-foreground">
      Review due {formatDate(nextReview)}
    </span>
  );
}

interface FormState {
  program_name: string;
  osha_standard: string;
  osha_standard_code: string;
  description: string;
  applicable_roles: string;
  content: string;
}

const emptyForm: FormState = {
  program_name: "",
  osha_standard: "",
  osha_standard_code: "",
  description: "",
  applicable_roles: "",
  content: "",
};

export default function SafetyProgramsPage() {
  const [programs, setPrograms] = useState<SafetyProgram[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<FormState>({ ...emptyForm });
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
      setForm({ ...emptyForm });
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
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">Loading safety programs...</p>
      </div>
    );
  }

  if (error && programs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={() => loadPrograms()}>
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
          <h1 className="text-2xl font-bold tracking-tight">Safety Programs</h1>
          <p className="text-muted-foreground">{programs.length} programs</p>
        </div>
        <Dialog
          open={createOpen}
          onOpenChange={(open) => {
            setCreateOpen(open);
            if (!open) setForm({ ...emptyForm });
          }}
        >
          <DialogTrigger render={<Button />}>Add Program</DialogTrigger>
          <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Safety Program</DialogTitle>
              <DialogDescription>
                Create a new written safety program.
              </DialogDescription>
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
                  placeholder="Brief description of the program"
                />
              </div>
              <div className="space-y-2">
                <Label>Applicable Roles (comma-separated)</Label>
                <Input
                  value={form.applicable_roles}
                  onChange={(e) => setForm({ ...form, applicable_roles: e.target.value })}
                  placeholder="e.g. Operator, Maintenance, Lab Tech"
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
              <Button variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={creating || !form.program_name.trim()}
              >
                {creating ? "Creating..." : "Create Program"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Programs List */}
      <div className="space-y-3">
        {programs.length === 0 ? (
          <Card className="p-8 text-center text-muted-foreground">
            No safety programs yet. Click "Add Program" to create one.
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
                    <Badge variant="outline" className="text-xs">
                      v{program.version}
                    </Badge>
                  </div>
                  {program.osha_standard && (
                    <p className="text-sm text-muted-foreground">
                      {program.osha_standard}
                      {program.osha_standard_code && (
                        <span className="ml-1">({program.osha_standard_code})</span>
                      )}
                    </p>
                  )}
                  {program.description && (
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-1">
                      {program.description}
                    </p>
                  )}
                  <div className="flex items-center gap-4 mt-2">
                    {reviewIndicator(program.next_review_due_at)}
                    {program.applicable_job_roles && program.applicable_job_roles.length > 0 && (
                      <span className="text-xs text-muted-foreground">
                        Roles: {program.applicable_job_roles.join(", ")}
                      </span>
                    )}
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
                    <Button
                      size="sm"
                      onClick={() => handleSaveContent(program.id)}
                      disabled={savingContent}
                    >
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
