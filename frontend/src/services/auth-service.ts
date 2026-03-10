import apiClient from "@/lib/api-client";
import type { LoginRequest, RegisterRequest, TokenResponse, User } from "@/types/auth";

export const authService = {
  async login(data: LoginRequest): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>("/auth/login", data);
    return response.data;
  },

  async register(data: RegisterRequest): Promise<User> {
    const response = await apiClient.post<User>("/auth/register", data);
    return response.data;
  },

  async getMe(): Promise<User> {
    const response = await apiClient.get<User>("/auth/me");
    return response.data;
  },
};
