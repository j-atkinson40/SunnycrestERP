import apiClient from "@/lib/api-client";

export interface AgingVendorRow {
  vendor_id: string;
  vendor_name: string;
  current: number;
  d1_30: number;
  d31_60: number;
  d61_90: number;
  d90_plus: number;
  total: number;
}

export interface AgingTotals {
  current: number;
  d1_30: number;
  d31_60: number;
  d61_90: number;
  d90_plus: number;
  total: number;
}

export interface AgingReport {
  vendors: AgingVendorRow[];
  totals: AgingTotals;
}

export const apAgingService = {
  async getAging(asOfDate?: string): Promise<AgingReport> {
    const params = new URLSearchParams();
    if (asOfDate) params.set("as_of_date", asOfDate);
    const qs = params.toString();
    return (
      await apiClient.get<AgingReport>(`/ap/aging${qs ? `?${qs}` : ""}`)
    ).data;
  },

  getAgingCsvUrl(asOfDate?: string): string {
    const params = new URLSearchParams();
    if (asOfDate) params.set("as_of_date", asOfDate);
    const qs = params.toString();
    // Build full URL for download (token appended by interceptor)
    const base = apiClient.defaults.baseURL || "/api";
    return `${base}/ap/aging/csv${qs ? `?${qs}` : ""}`;
  },

  async downloadAgingCsv(asOfDate?: string): Promise<void> {
    const params = new URLSearchParams();
    if (asOfDate) params.set("as_of_date", asOfDate);
    const qs = params.toString();
    const response = await apiClient.get(`/ap/aging/csv${qs ? `?${qs}` : ""}`, {
      responseType: "blob",
    });
    const blob = new Blob([response.data], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download =
      response.headers["content-disposition"]
        ?.split("filename=")[1]
        ?.replace(/"/g, "") || "ap_aging.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};
