import apiClient from "@/lib/api-client";
import type {
  QuickQuoteTemplate,
  OrderStationActivity,
} from "@/types/order-station";

export async function getTemplates(): Promise<QuickQuoteTemplate[]> {
  const { data } = await apiClient.get("/order-station/templates");
  return data;
}

export async function getActivity(): Promise<OrderStationActivity> {
  const { data } = await apiClient.get("/order-station/activity");
  return data;
}

export async function createQuote(
  quoteData: Record<string, unknown>,
): Promise<{ id: string; quote_number: string }> {
  const { data } = await apiClient.post("/order-station/quotes", quoteData);
  return data;
}

export async function convertQuoteToOrder(
  quoteId: string,
): Promise<{ id: string; order_number: string }> {
  const { data } = await apiClient.post(
    `/order-station/quotes/${quoteId}/convert`,
  );
  return data;
}

export async function updateQuoteStatus(
  quoteId: string,
  status: string,
): Promise<void> {
  await apiClient.patch(`/order-station/quotes/${quoteId}`, { status });
}

export async function recordCemeteryHistory(
  customerId: string,
  cemeteryId: string,
  orderDate?: string,
): Promise<void> {
  await apiClient.post("/order-station/record-cemetery-history", {
    customer_id: customerId,
    cemetery_id: cemeteryId,
    order_date: orderDate,
  });
}
