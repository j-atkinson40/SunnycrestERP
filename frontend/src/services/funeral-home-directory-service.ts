import apiClient from "@/lib/api-client";
import type {
  DirectoryEntry,
  PlatformMatch,
  DirectorySelection,
  ManualCustomer,
} from "@/types/funeral-home-directory";

export async function getDirectory(): Promise<DirectoryEntry[]> {
  const { data } = await apiClient.get("/funeral-home-directory");
  return data;
}

export async function getPlatformMatches(): Promise<PlatformMatch[]> {
  const { data } = await apiClient.get(
    "/funeral-home-directory/platform-matches"
  );
  return data;
}

export async function recordSelections(
  selections: DirectorySelection[]
): Promise<{
  created_customers: number;
  invitations_sent: number;
  skipped: number;
}> {
  const { data } = await apiClient.post(
    "/funeral-home-directory/selections",
    { selections }
  );
  return data;
}

export async function addManualCustomers(
  customers: ManualCustomer[]
): Promise<{ created_customers: number }> {
  const { data } = await apiClient.post("/funeral-home-directory/manual", {
    customers,
  });
  return data;
}

export async function refreshDirectory(): Promise<DirectoryEntry[]> {
  const { data } = await apiClient.post("/funeral-home-directory/refresh");
  return data;
}
