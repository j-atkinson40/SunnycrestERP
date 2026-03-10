import apiClient from "@/lib/api-client";
import type { User } from "@/types/auth";
import type { PaginatedUsers, UserCreate, UserUpdate } from "@/types/user";

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
};
