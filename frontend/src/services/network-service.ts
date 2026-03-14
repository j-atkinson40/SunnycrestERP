import apiClient from "@/lib/api-client";
import type {
  NetworkRelationshipCreate,
  NetworkRelationshipUpdate,
  NetworkRelationship,
  NetworkStats,
  NetworkTransaction,
  NetworkTransactionCreate,
  PaginatedRelationships,
  PaginatedTransactions,
} from "@/types/network";

export const networkService = {
  async getStats(): Promise<NetworkStats> {
    const response = await apiClient.get<NetworkStats>("/network/stats");
    return response.data;
  },

  async listRelationships(params?: {
    page?: number;
    per_page?: number;
    status?: string;
    relationship_type?: string;
  }): Promise<PaginatedRelationships> {
    const response = await apiClient.get<PaginatedRelationships>(
      "/network/relationships",
      { params },
    );
    return response.data;
  },

  async createRelationship(
    data: NetworkRelationshipCreate,
  ): Promise<NetworkRelationship> {
    const response = await apiClient.post<NetworkRelationship>(
      "/network/relationships",
      data,
    );
    return response.data;
  },

  async getRelationship(id: string): Promise<NetworkRelationship> {
    const response = await apiClient.get<NetworkRelationship>(
      `/network/relationships/${id}`,
    );
    return response.data;
  },

  async updateRelationship(
    id: string,
    data: NetworkRelationshipUpdate,
  ): Promise<NetworkRelationship> {
    const response = await apiClient.patch<NetworkRelationship>(
      `/network/relationships/${id}`,
      data,
    );
    return response.data;
  },

  async approveRelationship(id: string): Promise<NetworkRelationship> {
    const response = await apiClient.post<NetworkRelationship>(
      `/network/relationships/${id}/approve`,
    );
    return response.data;
  },

  async listTransactions(params?: {
    page?: number;
    per_page?: number;
    relationship_id?: string;
    transaction_type?: string;
  }): Promise<PaginatedTransactions> {
    const response = await apiClient.get<PaginatedTransactions>(
      "/network/transactions",
      { params },
    );
    return response.data;
  },

  async createTransaction(
    data: NetworkTransactionCreate,
  ): Promise<NetworkTransaction> {
    const response = await apiClient.post<NetworkTransaction>(
      "/network/transactions",
      data,
    );
    return response.data;
  },
};
