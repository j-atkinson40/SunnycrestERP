import axios from "axios";

import apiClient from "@/lib/api-client";
import type {
  Company,
  CompanyRegisterRequest,
  CompanyRegisterResponse,
  CompanyUpdate,
} from "@/types/company";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const companyService = {
  async registerCompany(
    data: CompanyRegisterRequest
  ): Promise<CompanyRegisterResponse> {
    const response = await axios.post<CompanyRegisterResponse>(
      `${API_BASE_URL}/api/v1/companies/register`,
      data
    );
    return response.data;
  },

  async getSettings(): Promise<Company> {
    const response = await apiClient.get<Company>("/companies/settings");
    return response.data;
  },

  async updateSettings(data: CompanyUpdate): Promise<Company> {
    const response = await apiClient.patch<Company>(
      "/companies/settings",
      data
    );
    return response.data;
  },
};
