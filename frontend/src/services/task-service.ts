/**
 * Task service — thin axios client for `/api/v1/tasks/*`.
 *
 * Seven endpoints per `backend/app/api/routes/tasks.py`. Each
 * function unwraps the axios `response.data`. 409 from the server
 * means "invalid state transition"; 400 means validation failure;
 * 404 means the task doesn't exist for the current tenant.
 */

import apiClient from "@/lib/api-client";

export type TaskPriority = "low" | "normal" | "high" | "urgent";
export type TaskStatus =
  | "open"
  | "in_progress"
  | "blocked"
  | "done"
  | "cancelled";

export interface Task {
  id: string;
  company_id: string;
  title: string;
  description?: string | null;
  assignee_user_id?: string | null;
  created_by_user_id?: string | null;
  priority: TaskPriority;
  due_date?: string | null;      // YYYY-MM-DD
  due_datetime?: string | null;  // ISO datetime
  status: TaskStatus;
  completed_at?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  metadata_json: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateTaskPayload {
  title: string;
  description?: string | null;
  assignee_user_id?: string | null;
  priority?: TaskPriority;
  due_date?: string | null;
  due_datetime?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  metadata_json?: Record<string, unknown> | null;
}

export interface UpdateTaskPayload {
  title?: string | null;
  description?: string | null;
  assignee_user_id?: string | null;
  priority?: TaskPriority | null;
  due_date?: string | null;
  due_datetime?: string | null;
  status?: TaskStatus | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  metadata_json?: Record<string, unknown> | null;
}

export interface ListTaskFilters {
  status?: TaskStatus | null;
  assignee_user_id?: string | null;
  priority?: TaskPriority | null;
  due_before?: string | null;
  due_after?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  limit?: number;
}

export async function listTasks(filters: ListTaskFilters = {}): Promise<Task[]> {
  const params: Record<string, string | number> = {};
  if (filters.status) params.status = filters.status;
  if (filters.assignee_user_id) params.assignee_user_id = filters.assignee_user_id;
  if (filters.priority) params.priority = filters.priority;
  if (filters.due_before) params.due_before = filters.due_before;
  if (filters.due_after) params.due_after = filters.due_after;
  if (filters.related_entity_type) {
    params.related_entity_type = filters.related_entity_type;
  }
  if (filters.related_entity_id) {
    params.related_entity_id = filters.related_entity_id;
  }
  if (filters.limit) params.limit = filters.limit;

  const { data } = await apiClient.get<Task[]>("/tasks", { params });
  return data;
}

export async function createTask(payload: CreateTaskPayload): Promise<Task> {
  const { data } = await apiClient.post<Task>("/tasks", payload);
  return data;
}

export async function getTask(taskId: string): Promise<Task> {
  const { data } = await apiClient.get<Task>(
    `/tasks/${encodeURIComponent(taskId)}`,
  );
  return data;
}

export async function updateTask(
  taskId: string,
  payload: UpdateTaskPayload,
): Promise<Task> {
  const { data } = await apiClient.patch<Task>(
    `/tasks/${encodeURIComponent(taskId)}`,
    payload,
  );
  return data;
}

export async function deleteTask(taskId: string): Promise<{ status: string; id: string }> {
  const { data } = await apiClient.delete<{ status: string; id: string }>(
    `/tasks/${encodeURIComponent(taskId)}`,
  );
  return data;
}

export async function completeTask(taskId: string): Promise<Task> {
  const { data } = await apiClient.post<Task>(
    `/tasks/${encodeURIComponent(taskId)}/complete`,
  );
  return data;
}

export async function cancelTask(taskId: string): Promise<Task> {
  const { data } = await apiClient.post<Task>(
    `/tasks/${encodeURIComponent(taskId)}/cancel`,
  );
  return data;
}
