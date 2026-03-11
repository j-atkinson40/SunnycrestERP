import axios from "axios";

import type {
  CompanyRegisterRequest,
  CompanyRegisterResponse,
} from "@/types/company";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const companyService = {
  async registerCompany(
    data: CompanyRegisterRequest
  ): Promise<CompanyRegisterResponse> {
    const response = await axios.post<CompanyRegisterResponse>(
      `${API_BASE_URL}/api/companies/register`,
      data
    );
    return response.data;
  },
};
