export type ProjectType = "columbarium" | "monument" | "redi_rock" | "custom";
export type ProjectStatus = "planning" | "in_progress" | "on_hold" | "completed" | "cancelled";
export type TaskStatus = "todo" | "in_progress" | "blocked" | "review" | "done";
export type Priority = "low" | "medium" | "high" | "critical";

export interface ProjectTask {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: Priority;
  assigned_to_id: string | null;
  assigned_to_name: string | null;
  estimated_hours: number | null;
  actual_hours: number | null;
  start_date: string | null;
  due_date: string | null;
  completed_at: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface TaskCreate {
  title: string;
  description?: string;
  status?: TaskStatus;
  priority?: Priority;
  assigned_to_id?: string;
  estimated_hours?: number;
  start_date?: string;
  due_date?: string;
  sort_order?: number;
}

export interface TaskUpdate {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: Priority;
  assigned_to_id?: string | null;
  estimated_hours?: number;
  actual_hours?: number;
  start_date?: string;
  due_date?: string;
  sort_order?: number;
}

export interface ProjectMilestone {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  due_date: string | null;
  completed_at: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface MilestoneCreate {
  title: string;
  description?: string;
  due_date?: string;
  sort_order?: number;
}

export interface MilestoneUpdate {
  title?: string;
  description?: string;
  due_date?: string;
  sort_order?: number;
}

export interface Project {
  id: string;
  company_id: string;
  project_number: string;
  name: string;
  description: string | null;
  project_type: ProjectType;
  status: ProjectStatus;
  priority: Priority;
  customer_id: string | null;
  customer_name: string | null;
  start_date: string | null;
  target_date: string | null;
  completed_at: string | null;
  budget: number | null;
  actual_cost: number | null;
  completion_pct: number;
  tasks: ProjectTask[];
  milestones: ProjectMilestone[];
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectListItem {
  id: string;
  project_number: string;
  name: string;
  project_type: ProjectType;
  status: ProjectStatus;
  priority: Priority;
  customer_name: string | null;
  completion_pct: number;
  target_date: string | null;
  task_count: number;
  created_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  project_type: ProjectType;
  priority?: Priority;
  customer_id?: string;
  start_date?: string;
  target_date?: string;
  budget?: number;
  notes?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  project_type?: ProjectType;
  status?: ProjectStatus;
  priority?: Priority;
  customer_id?: string | null;
  start_date?: string;
  target_date?: string;
  budget?: number;
  actual_cost?: number;
  notes?: string;
}

export interface ProjectStats {
  planning: number;
  in_progress: number;
  on_hold: number;
  completed: number;
  cancelled: number;
  total: number;
}

export interface PaginatedProjects {
  items: ProjectListItem[];
  total: number;
  page: number;
  per_page: number;
}
