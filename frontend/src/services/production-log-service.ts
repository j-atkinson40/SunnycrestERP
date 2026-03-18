import apiClient from "@/lib/api-client";
import type { ProductionLogEntry, ProductionLogEntryCreate, ProductionLogEntryUpdate, DailyTotal, ProductionLogSummary } from "@/types/production-log";

export async function listEntries(params?: {
  start_date?: string;
  end_date?: string;
  product_id?: string;
  limit?: number;
  offset?: number;
}): Promise<ProductionLogEntry[]> {
  const { data } = await apiClient.get("/production/production-log", { params });
  return data;
}

export async function getToday(): Promise<DailyTotal> {
  const { data } = await apiClient.get("/production/production-log/today");
  return data;
}

export async function getSummaries(startDate: string, endDate: string): Promise<ProductionLogSummary[]> {
  const { data } = await apiClient.get("/production/production-log/summary", {
    params: { start_date: startDate, end_date: endDate },
  });
  return data;
}

export async function createEntry(entry: ProductionLogEntryCreate): Promise<ProductionLogEntry> {
  const { data } = await apiClient.post("/production/production-log", entry);
  return data;
}

export async function updateEntry(id: string, update: ProductionLogEntryUpdate): Promise<ProductionLogEntry> {
  const { data } = await apiClient.put(`/production/production-log/${id}`, update);
  return data;
}

export async function deleteEntry(id: string): Promise<void> {
  await apiClient.delete(`/production/production-log/${id}`);
}
