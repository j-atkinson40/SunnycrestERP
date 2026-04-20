/**
 * `/tasks/:taskId` — task detail + transitions.
 *
 * Surfaces the current status and the allowed transitions from it
 * (mirrors backend `_ALLOWED_TRANSITIONS` in `task_service.py`). A
 * 409 from the backend surfaces as a toast.
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  cancelTask,
  completeTask,
  deleteTask,
  getTask,
  updateTask,
  type Task,
  type TaskStatus,
} from "@/services/task-service";

// Mirrors backend _ALLOWED_TRANSITIONS in task_service.py.
const _TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
  open: ["in_progress", "blocked", "done", "cancelled"],
  in_progress: ["blocked", "done", "cancelled", "open"],
  blocked: ["in_progress", "cancelled", "open"],
  done: [],
  cancelled: [],
};

export default function TaskDetail() {
  const { taskId = "" } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setTask(await getTask(taskId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load task");
    }
  };

  useEffect(() => {
    if (!taskId) return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  if (!taskId) {
    return <div className="p-6">Missing task id.</div>;
  }
  if (error) {
    return <div className="p-6 text-destructive">{error}</div>;
  }
  if (!task) {
    return <div className="p-6 text-muted-foreground">Loading…</div>;
  }

  const transition = async (status: TaskStatus) => {
    try {
      if (status === "done") {
        setTask(await completeTask(task.id));
      } else if (status === "cancelled") {
        setTask(await cancelTask(task.id));
      } else {
        setTask(await updateTask(task.id, { status }));
      }
      toast.success(`Moved to ${status.replace(/_/g, " ")}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Transition failed");
    }
  };

  const onDelete = async () => {
    if (!confirm("Delete this task?")) return;
    try {
      await deleteTask(task.id);
      toast.success("Task deleted");
      navigate("/tasks");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const allowed = _TRANSITIONS[task.status] ?? [];

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <Link to="/tasks" className="text-sm text-muted-foreground hover:underline">
        ← Tasks
      </Link>
      <Card>
        <CardHeader>
          <CardTitle>{task.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {task.description ? (
            <p className="whitespace-pre-wrap">{task.description}</p>
          ) : (
            <p className="text-muted-foreground">No description.</p>
          )}
          <div className="grid grid-cols-2 gap-2 pt-2">
            <div><span className="text-muted-foreground">Priority: </span>{task.priority}</div>
            <div><span className="text-muted-foreground">Status: </span>{task.status.replace(/_/g, " ")}</div>
            <div><span className="text-muted-foreground">Due: </span>{task.due_date ?? "—"}</div>
            <div><span className="text-muted-foreground">Created: </span>{new Date(task.created_at).toLocaleDateString()}</div>
          </div>
        </CardContent>
      </Card>

      {allowed.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {allowed.map((s) => (
            <Button
              key={s}
              variant={s === "done" ? "default" : s === "cancelled" ? "destructive" : "outline"}
              onClick={() => transition(s)}
            >
              Move to {s.replace(/_/g, " ")}
            </Button>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Terminal state — no further transitions available.
        </p>
      )}

      <div className="border-t pt-4">
        <Button variant="ghost" className="text-destructive" onClick={onDelete}>
          Delete task
        </Button>
      </div>
    </div>
  );
}
