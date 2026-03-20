import apiClient from "@/lib/api-client";
import type { User } from "@/types/auth";
import type { PaginatedUsers, UserCreate, UserUpdate, BulkCreateResponse } from "@/types/user";

export const userService = {
  async getUsers(
    page = 1,
    perPage = 20,
    search?: string
  ): Promise<PaginatedUsers> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (search) params.set("search", search);
    const response = await apiClient.get<PaginatedUsers>(
      `/users?${params.toString()}`
    );
    return response.data;
  },

  async createUser(data: UserCreate): Promise<User> {
    const response = await apiClient.post<User>("/users", data);
    return response.data;
  },

  async updateUser(userId: string, data: UserUpdate): Promise<User> {
    const response = await apiClient.patch<User>(`/users/${userId}`, data);
    return response.data;
  },

  async deleteUser(userId: string): Promise<void> {
    await apiClient.delete(`/users/${userId}`);
  },

  async bulkCreateUsers(users: UserCreate[]): Promise<BulkCreateResponse> {
    const response = await apiClient.post<BulkCreateResponse>("/users/bulk", { users });
    return response.data;
  },

  async resetPassword(userId: string, newPassword: string): Promise<void> {
    await apiClient.post(`/users/${userId}/reset-password`, {
      new_password: newPassword,
    });
  },

  async resetPin(userId: string, newPin: string): Promise<void> {
    await apiClient.post(`/users/${userId}/reset-pin`, {
      new_pin: newPin,
    });
  },

  async getPin(userId: string): Promise<string> {
    const response = await apiClient.get<{ pin: string }>(`/users/${userId}/pin`);
    return response.data.pin;
  },

  async suggestUsername(firstName: string, lastName: string): Promise<string> {
    const params = new URLSearchParams({ first_name: firstName, last_name: lastName });
    const response = await apiClient.get<{ username: string }>(
      `/users/suggest-username?${params.toString()}`
    );
    return response.data.username;
  },
};
