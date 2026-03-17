import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { projectService } from "@/services/project-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type {
  ProjectListItem,
  ProjectStatus,
  ProjectType,
  Priority,
  ProjectStats,
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
  DialogTrigger,
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

export default function ProjectListPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("projects.create");
  const canDelete = hasPermission("projects.delete");

  // List state
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterPriority, setFilterPriority] = useState("");
  const [loading, setLoading] = useState(true);

  // Stats
  const [stats, setStats] = useState<ProjectStats | null>(null);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newProject, setNewProject] = useState({
    name: "",
    description: "",
    project_type: "custom" as ProjectType,
    priority: "medium" as Priority,
    start_date: "",
    target_date: "",
    budget: "",
    notes: "",
  });
  const [createError, setCreateError] = useState("");

  const loadStats = useCallback(async () => {
    try {
      const data = await projectService.getProjectStats();
      setStats(data);
    } catch {
      // Silent — stats are supplementary
    }
  }, []);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const data = await projectService.listProjects(
        page,
        20,
        search || undefined,
        filterStatus || undefined,
        filterType || undefined,
        filterPriority || undefined,
      );
      setProjects(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, filterStatus, filterType, filterPriority]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  async function handleCreateProject() {
    setCreateError("");
    try {
      const project = await projectService.createProject({
        name: newProject.name.trim(),
        description: newProject.description.trim() || undefined,
        project_type: newProject.project_type,
        priority: newProject.priority,
        start_date: newProject.start_date || undefined,
        target_date: newProject.target_date || undefined,
        budget: newProject.budget ? parseFloat(newProject.budget) : undefined,
        notes: newProject.notes.trim() || undefined,
      });
      setCreateOpen(false);
      setNewProject({
        name: "",
        description: "",
        project_type: "custom",
        priority: "medium",
        start_date: "",
        target_date: "",
        budget: "",
        notes: "",
      });
      toast.success("Project created");
      window.location.href = `/projects/${project.id}`;
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create project"));
    }
  }

  async function handleDelete(project: ProjectListItem) {
    if (!confirm(`Delete project "${project.name}"?`)) return;
    try {
      await projectService.deleteProject(project.id);
      toast.success("Project deleted");
      loadProjects();
      loadStats();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete project"));
    }
  }

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Projects</h1>
          <p className="text-muted-foreground">{total} total projects</p>
        </div>
        <div className="flex gap-2">
          {canCreate && (
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger render={<Button />}>New Project</DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create New Project</DialogTitle>
                  <DialogDescription>
                    Create a new project to track work, tasks, and milestones.
                  </DialogDescription>
                </DialogHeader>
                {createError && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {createError}
                  </div>
                )}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Project Name</Label>
                    <Input
                      value={newProject.name}
                      onChange={(e) =>
                        setNewProject({ ...newProject, name: e.target.value })
                      }
                      placeholder="Enter project name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Description (optional)</Label>
                    <Input
                      value={newProject.description}
                      onChange={(e) =>
                        setNewProject({ ...newProject, description: e.target.value })
                      }
                      placeholder="Brief description of the project"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Project Type</Label>
                      <select
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                        value={newProject.project_type}
                        onChange={(e) =>
                          setNewProject({
                            ...newProject,
                            project_type: e.target.value as ProjectType,
                          })
                        }
                      >
                        <option value="columbarium">Columbarium</option>
                        <option value="monument">Monument</option>
                        <option value="redi_rock">Redi-Rock</option>
                        <option value="custom">Custom</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label>Priority</Label>
                      <select
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                        value={newProject.priority}
                        onChange={(e) =>
                          setNewProject({
                            ...newProject,
                            priority: e.target.value as Priority,
                          })
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
                      <Label>Start Date (optional)</Label>
                      <Input
                        type="date"
                        value={newProject.start_date}
                        onChange={(e) =>
                          setNewProject({ ...newProject, start_date: e.target.value })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Target Date (optional)</Label>
                      <Input
                        type="date"
                        value={newProject.target_date}
                        onChange={(e) =>
                          setNewProject({ ...newProject, target_date: e.target.value })
                        }
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Budget (optional)</Label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      value={newProject.budget}
                      onChange={(e) =>
                        setNewProject({ ...newProject, budget: e.target.value })
                      }
                      placeholder="0.00"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Notes (optional)</Label>
                    <Input
                      value={newProject.notes}
                      onChange={(e) =>
                        setNewProject({ ...newProject, notes: e.target.value })
                      }
                      placeholder="Optional notes"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setCreateOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateProject}
                    disabled={!newProject.name.trim()}
                  >
                    Create Project
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Stats Summary Cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded-md border p-4">
            <p className="text-sm font-medium text-muted-foreground">Planning</p>
            <p className="text-2xl font-bold">{stats.planning}</p>
          </div>
          <div className="rounded-md border p-4">
            <p className="text-sm font-medium text-muted-foreground">In Progress</p>
            <p className="text-2xl font-bold text-blue-600">{stats.in_progress}</p>
          </div>
          <div className="rounded-md border p-4">
            <p className="text-sm font-medium text-muted-foreground">On Hold</p>
            <p className="text-2xl font-bold text-yellow-600">{stats.on_hold}</p>
          </div>
          <div className="rounded-md border p-4">
            <p className="text-sm font-medium text-muted-foreground">Completed</p>
            <p className="text-2xl font-bold text-green-600">{stats.completed}</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search projects..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Statuses</option>
          <option value="planning">Planning</option>
          <option value="in_progress">In Progress</option>
          <option value="on_hold">On Hold</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterType}
          onChange={(e) => {
            setFilterType(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Types</option>
          <option value="columbarium">Columbarium</option>
          <option value="monument">Monument</option>
          <option value="redi_rock">Redi-Rock</option>
          <option value="custom">Custom</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={filterPriority}
          onChange={(e) => {
            setFilterPriority(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Priorities</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Number</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Progress</TableHead>
              <TableHead>Target Date</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : projects.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center">
                  No projects found
                </TableCell>
              </TableRow>
            ) : (
              projects.map((project) => (
                <TableRow key={project.id}>
                  <TableCell className="text-muted-foreground">
                    {project.project_number}
                  </TableCell>
                  <TableCell className="font-medium">
                    <Link
                      to={`/projects/${project.id}`}
                      className="hover:underline"
                    >
                      {project.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {project.customer_name || "—"}
                  </TableCell>
                  <TableCell>{projectTypeLabel(project.project_type)}</TableCell>
                  <TableCell>{statusBadge(project.status)}</TableCell>
                  <TableCell>{priorityBadge(project.priority)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-16 rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-primary"
                          style={{ width: `${project.completion_pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {project.completion_pct}%
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(project.target_date)}
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Link to={`/projects/${project.id}`}>
                      <Button variant="ghost" size="sm">
                        View
                      </Button>
                    </Link>
                    {canDelete && project.status === "planning" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(project)}
                      >
                        Delete
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
