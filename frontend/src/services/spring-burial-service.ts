import apiClient from "@/lib/api-client";
import type {
  SpringBurialGroup,
  SpringBurialStats,
  ScheduleRequest,
} from "@/types/spring-burial";

export async function getSpringBurials(params?: {
  group_by?: "funeral_home" | "cemetery";
  funeral_home_id?: string;
}): Promise<SpringBurialGroup[]> {
  const { data } = await apiClient.get("/spring-burials", { params });
  return data;
}

export async function getStats(): Promise<SpringBurialStats> {
  const { data } = await apiClient.get("/spring-burials/stats");
  return data;
}

export async function markAsSpringBurial(
  orderId: string,
  notes?: string
): Promise<void> {
  await apiClient.post(`/spring-burials/${orderId}`, { notes });
}

export async function scheduleSpringBurial(
  orderId: string,
  req: Omit<ScheduleRequest, "order_id">
): Promise<void> {
  await apiClient.post(`/spring-burials/${orderId}/schedule`, req);
}

export async function bulkSchedule(orders: ScheduleRequest[]): Promise<void> {
  await apiClient.post("/spring-burials/bulk-schedule", { orders });
}

export async function removeSpringBurial(orderId: string): Promise<void> {
  await apiClient.delete(`/spring-burials/${orderId}`);
}

export async function getReport(
  year?: number
): Promise<{
  year: number;
  total_orders: number;
  avg_days_held: number | null;
  by_funeral_home: Array<{ name: string; count: number }>;
  by_cemetery: Array<{ name: string; count: number }>;
}> {
  const { data } = await apiClient.get("/spring-burials/report", {
    params: year ? { year } : undefined,
  });
  return data;
}
