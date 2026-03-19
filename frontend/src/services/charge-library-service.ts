import apiClient from "@/lib/api-client";
import type { ChargeLibraryItem, ChargeUpdate } from "@/types/charge-library";

export async function listCharges(): Promise<ChargeLibraryItem[]> {
  const { data } = await apiClient.get("/charges");
  return data;
}

export async function seedCharges(): Promise<void> {
  await apiClient.post("/charges/seed");
}

export async function bulkSaveCharges(charges: ChargeUpdate[]): Promise<void> {
  await apiClient.put("/charges/bulk", { charges });
}

export async function createCustomCharge(charge: {
  charge_name: string;
  category: string;
  description?: string;
  pricing_type?: string;
  fixed_amount?: number;
  invoice_label?: string;
}): Promise<ChargeLibraryItem> {
  const { data } = await apiClient.post("/charges/custom", charge);
  return data;
}
