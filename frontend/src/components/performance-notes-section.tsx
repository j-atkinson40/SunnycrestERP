import { useCallback, useEffect, useState } from "react";
import { PlusIcon, Trash2Icon } from "lucide-react";

import { Button } from "@/components/ui/button";
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
import { getApiErrorMessage } from "@/lib/api-error";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";

interface PerformanceNote {
  id: string;
  user_id: string;
  author_id: string;
  type: string;
  title: string;
  content: string | null;
  review_date: string | null;
  created_at: string;
}

const TYPE_BADGES: Record<string, string> = {
  review: "bg-blue-100 text-blue-800",
  note: "bg-gray-100 text-gray-800",
  goal: "bg-green-100 text-green-800",
  warning: "bg-red-100 text-red-800",
};

interface PerformanceNotesSectionProps {
  userId: string;
  canEdit: boolean;
}

export default function PerformanceNotesSection({
  userId,
  canEdit,
}: PerformanceNotesSectionProps) {
  const [notes, setNotes] = useState<PerformanceNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  // Form state
  const [noteType, setNoteType] = useState("note");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [reviewDate, setReviewDate] = useState("");

  const loadNotes = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiClient.get<PerformanceNote[]>(
        "/performance-notes",
        { params: { user_id: userId } }
      );
      setNotes(res.data);
    } catch {
      // Non-critical
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!noteTitle.trim()) return;
    setCreating(true);
    try {
      await apiClient.post("/performance-notes", {
        user_id: userId,
        type: noteType,
        title: noteTitle.trim(),
        content: noteContent.trim() || null,
        review_date: reviewDate || null,
      });
      toast.success("Performance note created");
      setDialogOpen(false);
      setNoteType("note");
      setNoteTitle("");
      setNoteContent("");
      setReviewDate("");
      await loadNotes();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to create note"));
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(noteId: string) {
    if (!confirm("Delete this performance note?")) return;
    try {
      await apiClient.delete(`/performance-notes/${noteId}`);
      toast.success("Note deleted");
      await loadNotes();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete note"));
    }
  }

  if (loading) {
    return (
      <p className="text-sm text-muted-foreground">
        Loading performance notes...
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {canEdit && (
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger
            render={<Button type="button" variant="outline" size="sm" />}
          >
            <PlusIcon className="mr-1.5 size-4" />
            Add Note
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>New Performance Note</DialogTitle>
              <DialogDescription>
                Add a performance review, note, goal, or warning.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Type</Label>
                  <select
                    value={noteType}
                    onChange={(e) => setNoteType(e.target.value)}
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  >
                    <option value="note">Note</option>
                    <option value="review">Review</option>
                    <option value="goal">Goal</option>
                    <option value="warning">Warning</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>Review Date (optional)</Label>
                  <Input
                    type="date"
                    value={reviewDate}
                    onChange={(e) => setReviewDate(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Title</Label>
                <Input
                  value={noteTitle}
                  onChange={(e) => setNoteTitle(e.target.value)}
                  placeholder="Brief summary"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Details (optional)</Label>
                <textarea
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  placeholder="Additional details..."
                />
              </div>
              <DialogFooter>
                <Button type="submit" disabled={creating}>
                  {creating ? "Creating..." : "Add Note"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}

      {notes.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No performance notes yet.
        </p>
      ) : (
        <div className="space-y-2">
          {notes.map((note) => (
            <div
              key={note.id}
              className="flex items-start justify-between rounded-md border p-3"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_BADGES[note.type] || TYPE_BADGES.note}`}
                  >
                    {note.type}
                  </span>
                  <span className="text-sm font-medium">{note.title}</span>
                </div>
                {note.content && (
                  <p className="text-sm text-muted-foreground">
                    {note.content}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  {new Date(note.created_at).toLocaleDateString()}
                  {note.review_date && ` · Review: ${note.review_date}`}
                </p>
              </div>
              {canEdit && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => handleDelete(note.id)}
                >
                  <Trash2Icon className="size-3.5 text-destructive" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
