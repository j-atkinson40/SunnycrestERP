import apiClient from "@/lib/api-client";
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectStats,
  PaginatedProjects,
  TaskCreate,
  TaskUpdate,
  MilestoneCreate,
  MilestoneUpdate,
} from "@/types/project";

export const projectService = {
  // -----------------------------------------------------------------------
  // Projects
  // -----------------------------------------------------------------------

  async listProjects(
    page = 1,
    perPage = 20,
    search?: string,
    status?: string,
    projectType?: string,
    priority?: string,
    customerId?: string,
  ): Promise<PaginatedProjects> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (projectType) params.set("project_type", projectType);
    if (priority) params.set("priority", priority);
    if (customerId) params.set("customer_id", customerId);
    const response = await apiClient.get<PaginatedProjects>(
      `/projects?${params.toString()}`,
    );
    return response.data;
  },

  async getProject(id: string): Promise<Project> {
    const response = await apiClient.get<Project>(`/projects/${id}`);
    return response.data;
  },

  async createProject(data: ProjectCreate): Promise<Project> {
    const response = await apiClient.post<Project>("/projects", data);
    return response.data;
  },

  async updateProject(id: string, data: ProjectUpdate): Promise<Project> {
    const response = await apiClient.patch<Project>(`/projects/${id}`, data);
    return response.data;
  },

  async deleteProject(id: string): Promise<void> {
    await apiClient.delete(`/projects/${id}`);
  },

  async getProjectStats(): Promise<ProjectStats> {
    const response = await apiClient.get<ProjectStats>("/projects/stats");
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Tasks
  // -----------------------------------------------------------------------

  async addTask(projectId: string, data: TaskCreate): Promise<Project> {
    const response = await apiClient.post<Project>(
      `/projects/${projectId}/tasks`,
      data,
    );
    return response.data;
  },

  async updateTask(
    projectId: string,
    taskId: string,
    data: TaskUpdate,
  ): Promise<Project> {
    const response = await apiClient.patch<Project>(
      `/projects/${projectId}/tasks/${taskId}`,
      data,
    );
    return response.data;
  },

  async completeTask(projectId: string, taskId: string): Promise<Project> {
    const response = await apiClient.post<Project>(
      `/projects/${projectId}/tasks/${taskId}/complete`,
    );
    return response.data;
  },

  async deleteTask(projectId: string, taskId: string): Promise<Project> {
    const response = await apiClient.delete<Project>(
      `/projects/${projectId}/tasks/${taskId}`,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Milestones
  // -----------------------------------------------------------------------

  async addMilestone(
    projectId: string,
    data: MilestoneCreate,
  ): Promise<Project> {
    const response = await apiClient.post<Project>(
      `/projects/${projectId}/milestones`,
      data,
    );
    return response.data;
  },

  async updateMilestone(
    projectId: string,
    milestoneId: string,
    data: MilestoneUpdate,
  ): Promise<Project> {
    const response = await apiClient.patch<Project>(
      `/projects/${projectId}/milestones/${milestoneId}`,
      data,
    );
    return response.data;
  },

  async completeMilestone(
    projectId: string,
    milestoneId: string,
  ): Promise<Project> {
    const response = await apiClient.post<Project>(
      `/projects/${projectId}/milestones/${milestoneId}/complete`,
    );
    return response.data;
  },

  async deleteMilestone(
    projectId: string,
    milestoneId: string,
  ): Promise<Project> {
    const response = await apiClient.delete<Project>(
      `/projects/${projectId}/milestones/${milestoneId}`,
    );
    return response.data;
  },
};
