/**
 * `/tasks` — task list with status + priority filters.
 *
 * Primary action: "Triage my tasks" routes into the triage workspace
 * for the task_triage queue. The list itself is the backup path per
 * CLAUDE.md §1a — acting is intent-driven; this page exists for
 * deep browse + ad-hoc edits.
 */

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, ListChecks, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { SkeletonTable } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  completeTask,
  listTasks,
  type Task,
  type TaskPriority,
  type TaskStatus,
} from "@/services/task-service";

const ALL_STATUSES: TaskStatus[] = [
  "open",
  "in_progress",
  "blocked",
  "done",
  "cancelled",
];

const ALL_PRIORITIES: TaskPriority[] = ["urgent", "high", "normal", "low"];

export default function TasksList() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [status, setStatus] = useState<TaskStatus | "all">("open");
  const [priority, setPriority] = useState<TaskPriority | "all">("all");
  const [loading, setLoading] = useState(false);

  const load = useMemo(() => {
    return async () => {
      setLoading(true);
      try {
        const rows = await listTasks({
          status: status === "all" ? null : status,
          priority: priority === "all" ? null : priority,
          limit: 200,
        });
        setTasks(rows);
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Failed to load tasks",
        );
      } finally {
        setLoading(false);
      }
    };
  }, [status, priority]);

  useEffect(() => {
    void load();
  }, [load]);

  const onComplete = async (t: Task) => {
    try {
      await completeTask(t.id);
      toast.success(`${t.title} · marked done`);
      void load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Complete failed");
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Tasks</h1>
          <p className="text-sm text-muted-foreground">
            Your task inbox. Prefer keyboard triage?
            <Link to="/triage/task_triage" className="ml-1 text-primary hover:underline">
              Open the task triage workspace
            </Link>
            .
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link to="/triage/task_triage">
              <ListChecks className="mr-2 h-4 w-4" />
              Triage
            </Link>
          </Button>
          <Button asChild>
            <Link to="/tasks/new">
              <Plus className="mr-2 h-4 w-4" />
              New task
            </Link>
          </Button>
        </div>
      </header>

      <div className="flex flex-wrap gap-3">
        <Select value={status} onValueChange={(v) => setStatus(v as TaskStatus | "all")}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {ALL_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {s.replace(/_/g, " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={priority} onValueChange={(v) => setPriority(v as TaskPriority | "all")}>
          <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All priorities</SelectItem>
            {ALL_PRIORITIES.map((p) => (
              <SelectItem key={p} value={p}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {tasks === null || loading ? (
        <SkeletonTable rows={5} />
      ) : tasks.length === 0 ? (
        status === "all" && priority === "all" ? (
          <EmptyState
            icon={CheckCircle2}
            title="No open tasks"
            description={
              <>
                Nothing on your plate right now. Create a task with{" "}
                <kbd className="rounded border bg-muted px-1 text-xs">⌘K</kbd>{" "}
                or the button below.
              </>
            }
            action={
              <Button asChild size="sm">
                <Link to="/tasks/new">
                  <Plus className="mr-2 h-4 w-4" />
                  New task
                </Link>
              </Button>
            }
            tone="positive"
            data-testid="tasks-list-empty-all"
          />
        ) : (
          <EmptyState
            icon={ListChecks}
            title="No tasks match this filter"
            description="Try 'All statuses' or 'All priorities' to see everything."
            secondaryAction={
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setStatus("all");
                  setPriority("all");
                }}
              >
                Clear filters
              </Button>
            }
            tone="filtered"
            data-testid="tasks-list-empty-filtered"
          />
        )
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Due</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {tasks.map((t) => (
              <TableRow key={t.id}>
                <TableCell>
                  <Link to={`/tasks/${t.id}`} className="hover:underline">
                    {t.title}
                  </Link>
                </TableCell>
                <TableCell>
                  <PriorityBadge priority={t.priority} />
                </TableCell>
                <TableCell>
                  <StatusBadge status={t.status} />
                </TableCell>
                <TableCell>{t.due_date ?? "—"}</TableCell>
                <TableCell className="text-right">
                  {t.status === "open" || t.status === "in_progress" || t.status === "blocked" ? (
                    <Button size="sm" variant="ghost" onClick={() => onComplete(t)}>
                      Mark done
                    </Button>
                  ) : null}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function PriorityBadge({ priority }: { priority: TaskPriority }) {
  const cls =
    priority === "urgent"
      ? "bg-red-100 text-red-800 border-red-200"
      : priority === "high"
      ? "bg-orange-100 text-orange-800 border-orange-200"
      : priority === "low"
      ? "bg-slate-100 text-slate-600 border-slate-200"
      : "bg-blue-100 text-blue-800 border-blue-200";
  return <Badge variant="outline" className={cls}>{priority}</Badge>;
}

function StatusBadge({ status }: { status: TaskStatus }) {
  const cls =
    status === "done"
      ? "bg-green-100 text-green-800 border-green-200"
      : status === "cancelled"
      ? "bg-slate-100 text-slate-600 border-slate-200"
      : status === "blocked"
      ? "bg-amber-100 text-amber-800 border-amber-200"
      : "bg-blue-100 text-blue-800 border-blue-200";
  return <Badge variant="outline" className={cls}>{status.replace(/_/g, " ")}</Badge>;
}
