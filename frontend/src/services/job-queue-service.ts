import apiClient from "@/lib/api-client";
import type {
  Job,
  PaginatedJobs,
  QueueStats,
  SyncDashboard,
} from "@/types/job-queue";

export const jobQueueService = {
  async getStats(): Promise<QueueStats> {
    const response = await apiClient.get<QueueStats>("/jobs/stats");
    return response.data;
  },

  async enqueue(params: {
    job_type: string;
    payload?: Record<string, unknown>;
    priority?: number;
    max_retries?: number;
    delay_seconds?: number;
  }): Promise<Job> {
    const response = await apiClient.post<Job>("/jobs/enqueue", params);
    return response.data;
  },

  async listJobs(params?: {
    status?: string;
    job_type?: string;
    page?: number;
    per_page?: number;
  }): Promise<PaginatedJobs> {
    const response = await apiClient.get<PaginatedJobs>("/jobs/jobs", {
      params,
    });
    return response.data;
  },

  async listDeadLetter(params?: {
    page?: number;
    per_page?: number;
  }): Promise<PaginatedJobs> {
    const response = await apiClient.get<PaginatedJobs>("/jobs/dead-letter", {
      params,
    });
    return response.data;
  },

  async retryDeadLetter(jobId: string): Promise<Job> {
    const response = await apiClient.post<Job>(
      `/jobs/dead-letter/${jobId}/retry`,
    );
    return response.data;
  },

  async getSyncDashboard(): Promise<SyncDashboard> {
    const response = await apiClient.get<SyncDashboard>(
      "/jobs/sync-dashboard",
    );
    return response.data;
  },
};
