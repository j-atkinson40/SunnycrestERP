import apiClient from "@/lib/api-client";
import type { LoginRequest, TokenResponse, User } from "@/types/auth";
import type { Company } from "@/types/company";

export interface MeResponse extends User {
  company: Company;
}

export const authService = {
  async login(data: LoginRequest): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>("/auth/login", data);
    return response.data;
  },

  async loginPin(username: string, pin: string): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>("/auth/login", { username, pin });
    return response.data;
  },

  // `register` was deleted on 2026-11-06 with POST /auth/register.

  async getMe(): Promise<MeResponse> {
    const response = await apiClient.get<MeResponse>("/auth/me");
    return response.data;
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await apiClient.post("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },
};
