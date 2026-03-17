import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeftIcon } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { projectService } from "@/services/project-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  Project,
  ProjectTask,
  ProjectMilestone,
  ProjectStatus,
  ProjectType,
  TaskStatus,
  Priority,
} from "@/types/project";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
} from "@/components/ui/dialog";
import { toast } from "sonner";

function statusBadge(status: ProjectStatus) {
  switch (status) {
    case "planning":
      return <Badge variant="outline">Planning</Badge>;
    case "in_progress":
      return <Badge variant="default" className="bg-blue-600">In Progress</Badge>;
    case "on_hold":
      return <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-700">On Hold</Badge>;
    case "completed":
      return <Badge variant="default" className="bg-green-600">Completed</Badge>;
    case "cancelled":
      return <Badge variant="destructive">Cancelled</Badge>;
  }
}

function priorityBadge(priority: Priority) {
  switch (priority) {
    case "low":
      return <Badge variant="outline">Low</Badge>;
    case "medium":
      return <Badge variant="default">Medium</Badge>;
    case "high":
      return <Badge variant="secondary" className="bg-orange-500/20 text-orange-700">High</Badge>;
    case "critical":
      return <Badge variant="destructive">Critical</Badge>;
  }
}

function taskStatusBadge(status: TaskStatus) {
  switch (status) {
    case "todo":
      return <Badge variant="outline">To Do</Badge>;
    case "in_progress":
      return <Badge variant="default" className="bg-blue-600">In Progress</Badge>;
    case "blocked":
      return <Badge variant="destructive">Blocked</Badge>;
    case "review":
      return <Badge variant="secondary" className="bg-purple-500/20 text-purple-700">Review</Badge>;
    case "done":
      return <Badge variant="default" className="bg-green-600">Done</Badge>;
  }
}

function projectTypeLabel(type: ProjectType): string {
  switch (type) {
    case "columbarium":
      return "Columbarium";
    case "monument":
      return "Monument";
    case "redi_rock":
      return "Redi-Rock";
    case "custom":
      return "Custom";
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString();
}

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `$${Number(value).toFixed(2)}`;
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("projects.edit");
  const canDelete = hasPermission("projects.delete");

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Active tab
  const [activeTab, setActiveTab] = useState<"tasks" | "milestones">("tasks");

  // Edit project dialog
  const [editOpen, setEditOpen] = useState(false);
  const [editData, setEditData] = useState({
    name: "",
    description: "",
    project_type: "custom" as ProjectType,
    status: "planning" as ProjectStatus,
    priority: "medium" as Priority,
    start_date: "",
    target_date: "",
    budget: "",
    actual_cost: "",
    notes: "",
  });
  const [editError, setEditError] = useState("");

  // Add task dialog
  const [addTaskOpen, setAddTaskOpen] = useState(false);
  const [newTask, setNewTask] = useState({
    title: "",
    description: "",
    priority: "medium" as Priority,
    assigned_to_name: "",
    estimated_hours: "",
    start_date: "",
    due_date: "",
  });
  const [addTaskError, setAddTaskError] = useState("");

  // Edit task dialog
  const [editTaskOpen, setEditTaskOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<ProjectTask | null>(null);
  const [editTask, setEditTask] = useState({
    title: "",
    description: "",
    status: "todo" as TaskStatus,
    priority: "medium" as Priority,
    estimated_hours: "",
    actual_hours: "",
    start_date: "",
    due_date: "",
  });
  const [editTaskError, setEditTaskError] = useState("");

  // Add milestone dialog
  const [addMilestoneOpen, setAddMilestoneOpen] = useState(false);
  const [newMilestone, setNewMilestone] = useState({
    title: "",
    description: "",
    due_date: "",
  });
  const [addMilestoneError, setAddMilestoneError] = useState("");

  // Edit milestone dialog
  const [editMilestoneOpen, setEditMilestoneOpen] = useState(false);
  const [editingMilestone, setEditingMilestone] = useState<ProjectMilestone | null>(null);
  const [editMilestoneData, setEditMilestoneData] = useState({
    title: "",
    description: "",
    due_date: "",
  });
  const [editMilestoneError, setEditMilestoneError] = useState("");

  const loadProject = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError("");
    try {
      const data = await projectService.getProject(projectId);
      setProject(data);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to load project"));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  // -----------------------------------------------------------------------
  // Project Actions
  // -----------------------------------------------------------------------

  function openEditProject() {
    if (!project) return;
    setEditData({
      name: project.name,
      description: project.description || "",
      project_type: project.project_type,
      status: project.status,
      priority: project.priority,
      start_date: project.start_date || "",
      target_date: project.target_date || "",
      budget: project.budget !== null ? String(project.budget) : "",
      actual_cost: project.actual_cost !== null ? String(project.actual_cost) : "",
      notes: project.notes || "",
    });
    setEditError("");
    setEditOpen(true);
  }

  async function handleUpdateProject() {
    if (!project) return;
    setEditError("");
    try {
      const updated = await projectService.updateProject(project.id, {
        name: editData.name.trim(),
        description: editData.description.trim() || undefined,
        project_type: editData.project_type,
        status: editData.status,
        priority: editData.priority,
        start_date: editData.start_date || undefined,
        target_date: editData.target_date || undefined,
        budget: editData.budget ? parseFloat(editData.budget) : undefined,
        actual_cost: editData.actual_cost ? parseFloat(editData.actual_cost) : undefined,
        notes: editData.notes.trim() || undefined,
      });
      setProject(updated);
      setEditOpen(false);
      toast.success("Project updated");
    } catch (err: unknown) {
      setEditError(getApiErrorMessage(err, "Failed to update project"));
    }
  }

  async function handleCompleteProject() {
    if (!project) return;
    if (!confirm("Mark this project as completed?")) return;
    try {
      const updated = await projectService.updateProject(project.id, {
        status: "completed",
      });
      setProject(updated);
      toast.success("Project completed");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to complete project"));
    }
  }

  async function handleCancelProject() {
    if (!project) return;
    if (!confirm("Cancel this project?")) return;
    try {
      const updated = await projectService.updateProject(project.id, {
        status: "cancelled",
      });
      setProject(updated);
      toast.success("Project cancelled");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to cancel project"));
    }
  }

  async function handleDeleteProject() {
    if (!project) return;
    if (!confirm(`Delete project "${project.name}"? This cannot be undone.`)) return;
    try {
      await projectService.deleteProject(project.id);
      toast.success("Project deleted");
      navigate("/projects");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete project"));
    }
  }

  // -----------------------------------------------------------------------
  // Task Actions
  // -----------------------------------------------------------------------

  function resetNewTask() {
    setNewTask({
      title: "",
      description: "",
      priority: "medium",
      assigned_to_name: "",
      estimated_hours: "",
      start_date: "",
      due_date: "",
    });
    setAddTaskError("");
  }

  async function handleAddTask() {
    if (!project) return;
    setAddTaskError("");
    try {
      const updated = await projectService.addTask(project.id, {
        title: newTask.title.trim(),
        description: newTask.description.trim() || undefined,
        priority: newTask.priority,
        estimated_hours: newTask.estimated_hours
          ? parseFloat(newTask.estimated_hours)
          : undefined,
        start_date: newTask.start_date || undefined,
        due_date: newTask.due_date || undefined,
      });
      setProject(updated);
      setAddTaskOpen(false);
      resetNewTask();
      toast.success("Task added");
    } catch (err: unknown) {
      setAddTaskError(getApiErrorMessage(err, "Failed to add task"));
    }
  }

  function openEditTask(task: ProjectTask) {
    setEditingTask(task);
    setEditTask({
      title: task.title,
      description: task.description || "",
      status: task.status,
      priority: task.priority,
      estimated_hours: task.estimated_hours !== null ? String(task.estimated_hours) : "",
      actual_hours: task.actual_hours !== null ? String(task.actual_hours) : "",
      start_date: task.start_date || "",
      due_date: task.due_date || "",
    });
    setEditTaskError("");
    setEditTaskOpen(true);
  }

  async function handleUpdateTask() {
    if (!project || !editingTask) return;
    setEditTaskError("");
    try {
      const updated = await projectService.updateTask(project.id, editingTask.id, {
        title: editTask.title.trim(),
        description: editTask.description.trim() || undefined,
        status: editTask.status,
        priority: editTask.priority,
        estimated_hours: editTask.estimated_hours
          ? parseFloat(editTask.estimated_hours)
          : undefined,
        actual_hours: editTask.actual_hours
          ? parseFloat(editTask.actual_hours)
          : undefined,
        start_date: editTask.start_date || undefined,
        due_date: editTask.due_date || undefined,
      });
      setProject(updated);
      setEditTaskOpen(false);
      setEditingTask(null);
      toast.success("Task updated");
    } catch (err: unknown) {
      setEditTaskError(getApiErrorMessage(err, "Failed to update task"));
    }
  }

  async function handleCompleteTask(task: ProjectTask) {
    if (!project) return;
    try {
      const updated = await projectService.completeTask(project.id, task.id);
      setProject(updated);
      toast.success("Task completed");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to complete task"));
    }
  }

  async function handleDeleteTask(task: ProjectTask) {
    if (!project) return;
    if (!confirm(`Delete task "${task.title}"?`)) return;
    try {
      const updated = await projectService.deleteTask(project.id, task.id);
      setProject(updated);
      toast.success("Task deleted");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete task"));
    }
  }

  // -----------------------------------------------------------------------
  // Milestone Actions
  // -----------------------------------------------------------------------

  function resetNewMilestone() {
    setNewMilestone({ title: "", description: "", due_date: "" });
    setAddMilestoneError("");
  }

  async function handleAddMilestone() {
    if (!project) return;
    setAddMilestoneError("");
    try {
      const updated = await projectService.addMilestone(project.id, {
        title: newMilestone.title.trim(),
        description: newMilestone.description.trim() || undefined,
        due_date: newMilestone.due_date || undefined,
      });
      setProject(updated);
      setAddMilestoneOpen(false);
      resetNewMilestone();
      toast.success("Milestone added");
    } catch (err: unknown) {
      setAddMilestoneError(getApiErrorMessage(err, "Failed to add milestone"));
    }
  }

  function openEditMilestone(milestone: ProjectMilestone) {
    setEditingMilestone(milestone);
    setEditMilestoneData({
      title: milestone.title,
      description: milestone.description || "",
      due_date: milestone.due_date || "",
    });
    setEditMilestoneError("");
    setEditMilestoneOpen(true);
  }

  async function handleUpdateMilestone() {
    if (!project || !editingMilestone) return;
    setEditMilestoneError("");
    try {
      const updated = await projectService.updateMilestone(
        project.id,
        editingMilestone.id,
        {
          title: editMilestoneData.title.trim(),
          description: editMilestoneData.description.trim() || undefined,
          due_date: editMilestoneData.due_date || undefined,
        },
      );
      setProject(updated);
      setEditMilestoneOpen(false);
      setEditingMilestone(null);
      toast.success("Milestone updated");
    } catch (err: unknown) {
      setEditMilestoneError(getApiErrorMessage(err, "Failed to update milestone"));
    }
  }

  async function handleCompleteMilestone(milestone: ProjectMilestone) {
    if (!project) return;
    try {
      const updated = await projectService.completeMilestone(project.id, milestone.id);
      setProject(updated);
      toast.success("Milestone completed");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to complete milestone"));
    }
  }

  async function handleDeleteMilestone(milestone: ProjectMilestone) {
    if (!project) return;
    if (!confirm(`Delete milestone "${milestone.title}"?`)) return;
    try {
      const updated = await projectService.deleteMilestone(project.id, milestone.id);
      setProject(updated);
      toast.success("Milestone deleted");
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete milestone"));
    }
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading project...</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="space-y-4">
        <Link to="/projects" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeftIcon className="mr-1 size-4" />
          Back to Projects
        </Link>
        <div className="rounded-md bg-destructive/10 p-4 text-sm text-destructive">
          {error || "Project not found"}
        </div>
      </div>
    );
  }

  const isEditable = !["completed", "cancelled"].includes(project.status);

  // Sort tasks: active statuses first, then done; within groups by sort_order
  const sortedTasks = [...project.tasks].sort((a, b) => {
    const statusOrder: Record<TaskStatus, number> = {
      blocked: 0,
      in_progress: 1,
      review: 2,
      todo: 3,
      done: 4,
    };
    const aOrder = statusOrder[a.status] ?? 5;
    const bOrder = statusOrder[b.status] ?? 5;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return a.sort_order - b.sort_order;
  });

  const sortedMilestones = [...project.milestones].sort((a, b) => {
    // Incomplete first, then by sort_order
    if (a.completed_at && !b.completed_at) return 1;
    if (!a.completed_at && b.completed_at) return -1;
    return a.sort_order - b.sort_order;
  });

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link to="/projects" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="mr-1 size-4" />
        Back to Projects
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">{project.name}</h1>
            <Badge variant="outline">{project.project_number}</Badge>
            {statusBadge(project.status)}
            {priorityBadge(project.priority)}
          </div>
          {project.description && (
            <p className="text-muted-foreground mt-1">{project.description}</p>
          )}
        </div>
        <div className="flex gap-2">
          {canEdit && isEditable && (
            <Button variant="outline" size="sm" onClick={openEditProject}>
              Edit
            </Button>
          )}
          {canEdit && isEditable && project.status !== "completed" && (
            <Button size="sm" onClick={handleCompleteProject}>
              Complete
            </Button>
          )}
          {canEdit && isEditable && project.status !== "cancelled" && (
            <Button variant="outline" size="sm" onClick={handleCancelProject}>
              Cancel
            </Button>
          )}
          {canDelete && project.status === "planning" && (
            <Button variant="destructive" size="sm" onClick={handleDeleteProject}>
              Delete
            </Button>
          )}
        </div>
      </div>

      {/* Info Card */}
      <div className="rounded-md border p-4">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Customer</p>
            <p className="text-sm">{project.customer_name || "—"}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Type</p>
            <p className="text-sm">{projectTypeLabel(project.project_type)}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Start Date</p>
            <p className="text-sm">{formatDate(project.start_date)}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Target Date</p>
            <p className="text-sm">{formatDate(project.target_date)}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Budget</p>
            <p className="text-sm">{formatCurrency(project.budget)}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Actual Cost</p>
            <p className="text-sm">{formatCurrency(project.actual_cost)}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Tasks</p>
            <p className="text-sm">{project.tasks.length}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-muted-foreground">Milestones</p>
            <p className="text-sm">{project.milestones.length}</p>
          </div>
        </div>
        {project.notes && (
          <div className="mt-4 border-t pt-4">
            <p className="text-sm font-medium text-muted-foreground">Notes</p>
            <p className="text-sm">{project.notes}</p>
          </div>
        )}
      </div>

      {/* Progress Bar */}
      <div className="rounded-md border p-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium">Progress</p>
          <p className="text-sm font-bold">{project.completion_pct}%</p>
        </div>
        <div className="h-3 w-full rounded-full bg-muted">
          <div
            className="h-3 rounded-full bg-primary transition-all"
            style={{ width: `${project.completion_pct}%` }}
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b">
        <button
          className={`pb-2 text-sm font-medium transition-colors ${
            activeTab === "tasks"
              ? "border-b-2 border-primary text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setActiveTab("tasks")}
        >
          Tasks ({project.tasks.length})
        </button>
        <button
          className={`pb-2 text-sm font-medium transition-colors ${
            activeTab === "milestones"
              ? "border-b-2 border-primary text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setActiveTab("milestones")}
        >
          Milestones ({project.milestones.length})
        </button>
      </div>

      {/* Tasks Tab */}
      {activeTab === "tasks" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Tasks</h2>
            {canEdit && isEditable && (
              <Button
                size="sm"
                onClick={() => {
                  resetNewTask();
                  setAddTaskOpen(true);
                }}
              >
                Add Task
              </Button>
            )}
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Assignee</TableHead>
                  <TableHead>Est. Hours</TableHead>
                  <TableHead>Actual Hours</TableHead>
                  <TableHead>Due Date</TableHead>
                  {canEdit && isEditable && (
                    <TableHead className="text-right">Actions</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedTasks.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={canEdit && isEditable ? 8 : 7}
                      className="text-center"
                    >
                      No tasks added yet
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedTasks.map((task) => (
                    <TableRow key={task.id} className={task.status === "done" ? "opacity-60" : ""}>
                      <TableCell className="font-medium">
                        {task.title}
                        {task.description && (
                          <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                            {task.description}
                          </p>
                        )}
                      </TableCell>
                      <TableCell>{taskStatusBadge(task.status)}</TableCell>
                      <TableCell>{priorityBadge(task.priority)}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {task.assigned_to_name || "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {task.estimated_hours !== null ? `${task.estimated_hours}h` : "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {task.actual_hours !== null ? `${task.actual_hours}h` : "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(task.due_date)}
                      </TableCell>
                      {canEdit && isEditable && (
                        <TableCell className="text-right space-x-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditTask(task)}
                          >
                            Edit
                          </Button>
                          {task.status !== "done" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleCompleteTask(task)}
                            >
                              Done
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteTask(task)}
                          >
                            Delete
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Milestones Tab */}
      {activeTab === "milestones" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Milestones</h2>
            {canEdit && isEditable && (
              <Button
                size="sm"
                onClick={() => {
                  resetNewMilestone();
                  setAddMilestoneOpen(true);
                }}
              >
                Add Milestone
              </Button>
            )}
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Due Date</TableHead>
                  <TableHead>Status</TableHead>
                  {canEdit && isEditable && (
                    <TableHead className="text-right">Actions</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedMilestones.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={canEdit && isEditable ? 5 : 4}
                      className="text-center"
                    >
                      No milestones added yet
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedMilestones.map((milestone) => (
                    <TableRow
                      key={milestone.id}
                      className={milestone.completed_at ? "opacity-60" : ""}
                    >
                      <TableCell className="font-medium">{milestone.title}</TableCell>
                      <TableCell className="text-muted-foreground max-w-[200px] truncate">
                        {milestone.description || "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(milestone.due_date)}
                      </TableCell>
                      <TableCell>
                        {milestone.completed_at ? (
                          <Badge variant="default" className="bg-green-600">
                            Completed {formatDate(milestone.completed_at)}
                          </Badge>
                        ) : (
                          <Badge variant="outline">Pending</Badge>
                        )}
                      </TableCell>
                      {canEdit && isEditable && (
                        <TableCell className="text-right space-x-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditMilestone(milestone)}
                          >
                            Edit
                          </Button>
                          {!milestone.completed_at && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleCompleteMilestone(milestone)}
                            >
                              Complete
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteMilestone(milestone)}
                          >
                            Delete
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Edit Project Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Project</DialogTitle>
            <DialogDescription>
              Update the project details.
            </DialogDescription>
          </DialogHeader>
          {editError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {editError}
            </div>
          )}
          <div className="space-y-4 max-h-[60vh] overflow-y-auto">
            <div className="space-y-2">
              <Label>Project Name</Label>
              <Input
                value={editData.name}
                onChange={(e) => setEditData({ ...editData, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={editData.description}
                onChange={(e) => setEditData({ ...editData, description: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Type</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={editData.project_type}
                  onChange={(e) =>
                    setEditData({ ...editData, project_type: e.target.value as ProjectType })
                  }
                >
                  <option value="columbarium">Columbarium</option>
                  <option value="monument">Monument</option>
                  <option value="redi_rock">Redi-Rock</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={editData.status}
                  onChange={(e) =>
                    setEditData({ ...editData, status: e.target.value as ProjectStatus })
                  }
                >
                  <option value="planning">Planning</option>
                  <option value="in_progress">In Progress</option>
                  <option value="on_hold">On Hold</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Priority</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={editData.priority}
                  onChange={(e) =>
                    setEditData({ ...editData, priority: e.target.value as Priority })
                  }
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Start Date</Label>
                <Input
                  type="date"
                  value={editData.start_date}
                  onChange={(e) => setEditData({ ...editData, start_date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Target Date</Label>
                <Input
                  type="date"
                  value={editData.target_date}
                  onChange={(e) => setEditData({ ...editData, target_date: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Budget</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={editData.budget}
                  onChange={(e) => setEditData({ ...editData, budget: e.target.value })}
                  placeholder="0.00"
                />
              </div>
              <div className="space-y-2">
                <Label>Actual Cost</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  value={editData.actual_cost}
                  onChange={(e) => setEditData({ ...editData, actual_cost: e.target.value })}
                  placeholder="0.00"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Notes</Label>
              <Input
                value={editData.notes}
                onChange={(e) => setEditData({ ...editData, notes: e.target.value })}
                placeholder="Optional notes"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateProject} disabled={!editData.name.trim()}>
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Task Dialog */}
      <Dialog
        open={addTaskOpen}
        onOpenChange={(open) => {
          setAddTaskOpen(open);
          if (!open) resetNewTask();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Task</DialogTitle>
            <DialogDescription>
              Add a new task to this project.
            </DialogDescription>
          </DialogHeader>
          {addTaskError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {addTaskError}
            </div>
          )}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Title</Label>
              <Input
                value={newTask.title}
                onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                placeholder="Task title"
              />
            </div>
            <div className="space-y-2">
              <Label>Description (optional)</Label>
              <Input
                value={newTask.description}
                onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                placeholder="Task description"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Priority</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={newTask.priority}
                  onChange={(e) =>
                    setNewTask({ ...newTask, priority: e.target.value as Priority })
                  }
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Estimated Hours</Label>
                <Input
                  type="number"
                  step="0.5"
                  min="0"
                  value={newTask.estimated_hours}
                  onChange={(e) =>
                    setNewTask({ ...newTask, estimated_hours: e.target.value })
                  }
                  placeholder="0"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Start Date (optional)</Label>
                <Input
                  type="date"
                  value={newTask.start_date}
                  onChange={(e) => setNewTask({ ...newTask, start_date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Due Date (optional)</Label>
                <Input
                  type="date"
                  value={newTask.due_date}
                  onChange={(e) => setNewTask({ ...newTask, due_date: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddTaskOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddTask} disabled={!newTask.title.trim()}>
              Add Task
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Task Dialog */}
      <Dialog
        open={editTaskOpen}
        onOpenChange={(open) => {
          setEditTaskOpen(open);
          if (!open) setEditingTask(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Task</DialogTitle>
            <DialogDescription>
              Update the task details.
            </DialogDescription>
          </DialogHeader>
          {editTaskError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {editTaskError}
            </div>
          )}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Title</Label>
              <Input
                value={editTask.title}
                onChange={(e) => setEditTask({ ...editTask, title: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={editTask.description}
                onChange={(e) => setEditTask({ ...editTask, description: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Status</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={editTask.status}
                  onChange={(e) =>
                    setEditTask({ ...editTask, status: e.target.value as TaskStatus })
                  }
                >
                  <option value="todo">To Do</option>
                  <option value="in_progress">In Progress</option>
                  <option value="blocked">Blocked</option>
                  <option value="review">Review</option>
                  <option value="done">Done</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Priority</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={editTask.priority}
                  onChange={(e) =>
                    setEditTask({ ...editTask, priority: e.target.value as Priority })
                  }
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Est. Hours</Label>
                <Input
                  type="number"
                  step="0.5"
                  min="0"
                  value={editTask.estimated_hours}
                  onChange={(e) =>
                    setEditTask({ ...editTask, estimated_hours: e.target.value })
                  }
                  placeholder="0"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Actual Hours</Label>
              <Input
                type="number"
                step="0.5"
                min="0"
                value={editTask.actual_hours}
                onChange={(e) =>
                  setEditTask({ ...editTask, actual_hours: e.target.value })
                }
                placeholder="0"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Start Date</Label>
                <Input
                  type="date"
                  value={editTask.start_date}
                  onChange={(e) => setEditTask({ ...editTask, start_date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Due Date</Label>
                <Input
                  type="date"
                  value={editTask.due_date}
                  onChange={(e) => setEditTask({ ...editTask, due_date: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTaskOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateTask} disabled={!editTask.title.trim()}>
              Update Task
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Milestone Dialog */}
      <Dialog
        open={addMilestoneOpen}
        onOpenChange={(open) => {
          setAddMilestoneOpen(open);
          if (!open) resetNewMilestone();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Milestone</DialogTitle>
            <DialogDescription>
              Add a new milestone to this project.
            </DialogDescription>
          </DialogHeader>
          {addMilestoneError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {addMilestoneError}
            </div>
          )}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Title</Label>
              <Input
                value={newMilestone.title}
                onChange={(e) =>
                  setNewMilestone({ ...newMilestone, title: e.target.value })
                }
                placeholder="Milestone title"
              />
            </div>
            <div className="space-y-2">
              <Label>Description (optional)</Label>
              <Input
                value={newMilestone.description}
                onChange={(e) =>
                  setNewMilestone({ ...newMilestone, description: e.target.value })
                }
                placeholder="Milestone description"
              />
            </div>
            <div className="space-y-2">
              <Label>Due Date (optional)</Label>
              <Input
                type="date"
                value={newMilestone.due_date}
                onChange={(e) =>
                  setNewMilestone({ ...newMilestone, due_date: e.target.value })
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddMilestoneOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddMilestone} disabled={!newMilestone.title.trim()}>
              Add Milestone
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Milestone Dialog */}
      <Dialog
        open={editMilestoneOpen}
        onOpenChange={(open) => {
          setEditMilestoneOpen(open);
          if (!open) setEditingMilestone(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Milestone</DialogTitle>
            <DialogDescription>
              Update the milestone details.
            </DialogDescription>
          </DialogHeader>
          {editMilestoneError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {editMilestoneError}
            </div>
          )}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Title</Label>
              <Input
                value={editMilestoneData.title}
                onChange={(e) =>
                  setEditMilestoneData({ ...editMilestoneData, title: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={editMilestoneData.description}
                onChange={(e) =>
                  setEditMilestoneData({ ...editMilestoneData, description: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Due Date</Label>
              <Input
                type="date"
                value={editMilestoneData.due_date}
                onChange={(e) =>
                  setEditMilestoneData({ ...editMilestoneData, due_date: e.target.value })
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditMilestoneOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleUpdateMilestone}
              disabled={!editMilestoneData.title.trim()}
            >
              Update Milestone
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
