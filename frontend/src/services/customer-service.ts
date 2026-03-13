import apiClient from "@/lib/api-client";
import type {
  CreditCheckResult,
  Customer,
  CustomerContact,
  CustomerContactCreate,
  CustomerContactUpdate,
  CustomerCreate,
  CustomerNote,
  CustomerNoteCreate,
  CustomerStats,
  CustomerUpdate,
  PaginatedCustomers,
} from "@/types/customer";

export const customerService = {
  // -----------------------------------------------------------------------
  // Customers
  // -----------------------------------------------------------------------

  async getCustomers(
    page = 1,
    perPage = 20,
    search?: string,
    accountStatus?: string,
    includeInactive = false,
  ): Promise<PaginatedCustomers> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (search) params.set("search", search);
    if (accountStatus) params.set("account_status", accountStatus);
    if (includeInactive) params.set("include_inactive", "true");
    const response = await apiClient.get<PaginatedCustomers>(
      `/customers?${params.toString()}`,
    );
    return response.data;
  },

  async getCustomer(id: string): Promise<Customer> {
    const response = await apiClient.get<Customer>(`/customers/${id}`);
    return response.data;
  },

  async createCustomer(data: CustomerCreate): Promise<Customer> {
    const response = await apiClient.post<Customer>("/customers", data);
    return response.data;
  },

  async updateCustomer(id: string, data: CustomerUpdate): Promise<Customer> {
    const response = await apiClient.patch<Customer>(`/customers/${id}`, data);
    return response.data;
  },

  async deleteCustomer(id: string): Promise<void> {
    await apiClient.delete(`/customers/${id}`);
  },

  async getStats(): Promise<CustomerStats> {
    const response = await apiClient.get<CustomerStats>("/customers/stats");
    return response.data;
  },

  async checkCredit(
    customerId: string,
    amount: number,
  ): Promise<CreditCheckResult> {
    const response = await apiClient.get<CreditCheckResult>(
      `/customers/${customerId}/credit-check?amount=${amount}`,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Contacts
  // -----------------------------------------------------------------------

  async getContacts(customerId: string): Promise<CustomerContact[]> {
    const response = await apiClient.get<CustomerContact[]>(
      `/customers/${customerId}/contacts`,
    );
    return response.data;
  },

  async createContact(
    customerId: string,
    data: CustomerContactCreate,
  ): Promise<CustomerContact> {
    const response = await apiClient.post<CustomerContact>(
      `/customers/${customerId}/contacts`,
      data,
    );
    return response.data;
  },

  async updateContact(
    customerId: string,
    contactId: string,
    data: CustomerContactUpdate,
  ): Promise<CustomerContact> {
    const response = await apiClient.patch<CustomerContact>(
      `/customers/${customerId}/contacts/${contactId}`,
      data,
    );
    return response.data;
  },

  async deleteContact(customerId: string, contactId: string): Promise<void> {
    await apiClient.delete(`/customers/${customerId}/contacts/${contactId}`);
  },

  // -----------------------------------------------------------------------
  // Notes
  // -----------------------------------------------------------------------

  async getNotes(
    customerId: string,
    page = 1,
    perPage = 20,
  ): Promise<{ items: CustomerNote[]; total: number }> {
    const response = await apiClient.get(
      `/customers/${customerId}/notes?page=${page}&per_page=${perPage}`,
    );
    return response.data;
  },

  async createNote(
    customerId: string,
    data: CustomerNoteCreate,
  ): Promise<CustomerNote> {
    const response = await apiClient.post<CustomerNote>(
      `/customers/${customerId}/notes`,
      data,
    );
    return response.data;
  },
};
