import apiClient from "@/lib/api-client";
import type {
  ARAgingReport,
  CustomerPayment,
  CustomerPaymentCreate,
  Invoice,
  InvoiceCreate,
  InvoiceUpdate,
  PaginatedCustomerPayments,
  PaginatedInvoices,
  PaginatedQuotes,
  PaginatedSalesOrders,
  PaymentImportResult,
  Quote,
  QuoteCreate,
  QuoteUpdate,
  SalesOrder,
  SalesOrderCreate,
  SalesOrderUpdate,
  SalesStats,
} from "@/types/sales";

export const salesService = {
  // -----------------------------------------------------------------------
  // Stats
  // -----------------------------------------------------------------------

  async getStats(): Promise<SalesStats> {
    const r = await apiClient.get<SalesStats>("/sales/stats");
    return r.data;
  },

  // -----------------------------------------------------------------------
  // Quotes
  // -----------------------------------------------------------------------

  async getQuotes(
    page = 1,
    perPage = 20,
    status?: string,
    customerId?: string,
  ): Promise<PaginatedQuotes> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (status) params.set("status", status);
    if (customerId) params.set("customer_id", customerId);
    const r = await apiClient.get<PaginatedQuotes>(
      `/sales/quotes?${params.toString()}`,
    );
    return r.data;
  },

  async getQuote(id: string): Promise<Quote> {
    const r = await apiClient.get<Quote>(`/sales/quotes/${id}`);
    return r.data;
  },

  async createQuote(data: QuoteCreate): Promise<Quote> {
    const r = await apiClient.post<Quote>("/sales/quotes", data);
    return r.data;
  },

  async updateQuote(id: string, data: QuoteUpdate): Promise<Quote> {
    const r = await apiClient.patch<Quote>(`/sales/quotes/${id}`, data);
    return r.data;
  },

  async convertQuote(id: string): Promise<SalesOrder> {
    const r = await apiClient.post<SalesOrder>(
      `/sales/quotes/${id}/convert`,
    );
    return r.data;
  },

  // -----------------------------------------------------------------------
  // Sales Orders
  // -----------------------------------------------------------------------

  async getSalesOrders(
    page = 1,
    perPage = 20,
    status?: string,
    customerId?: string,
  ): Promise<PaginatedSalesOrders> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (status) params.set("status", status);
    if (customerId) params.set("customer_id", customerId);
    const r = await apiClient.get<PaginatedSalesOrders>(
      `/sales/orders?${params.toString()}`,
    );
    return r.data;
  },

  async getSalesOrder(id: string): Promise<SalesOrder> {
    const r = await apiClient.get<SalesOrder>(`/sales/orders/${id}`);
    return r.data;
  },

  async createSalesOrder(data: SalesOrderCreate): Promise<SalesOrder> {
    const r = await apiClient.post<SalesOrder>("/sales/orders", data);
    return r.data;
  },

  async updateSalesOrder(
    id: string,
    data: SalesOrderUpdate,
  ): Promise<SalesOrder> {
    const r = await apiClient.patch<SalesOrder>(
      `/sales/orders/${id}`,
      data,
    );
    return r.data;
  },

  async invoiceFromOrder(orderId: string): Promise<Invoice> {
    const r = await apiClient.post<Invoice>(
      `/sales/orders/${orderId}/invoice`,
    );
    return r.data;
  },

  // -----------------------------------------------------------------------
  // Invoices
  // -----------------------------------------------------------------------

  async getInvoices(
    page = 1,
    perPage = 20,
    status?: string,
    customerId?: string,
  ): Promise<PaginatedInvoices> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (status) params.set("status", status);
    if (customerId) params.set("customer_id", customerId);
    const r = await apiClient.get<PaginatedInvoices>(
      `/sales/invoices?${params.toString()}`,
    );
    return r.data;
  },

  async getInvoice(id: string): Promise<Invoice> {
    const r = await apiClient.get<Invoice>(`/sales/invoices/${id}`);
    return r.data;
  },

  async createInvoice(data: InvoiceCreate): Promise<Invoice> {
    const r = await apiClient.post<Invoice>("/sales/invoices", data);
    return r.data;
  },

  async updateInvoice(id: string, data: InvoiceUpdate): Promise<Invoice> {
    const r = await apiClient.patch<Invoice>(
      `/sales/invoices/${id}`,
      data,
    );
    return r.data;
  },

  async voidInvoice(id: string): Promise<Invoice> {
    const r = await apiClient.post<Invoice>(
      `/sales/invoices/${id}/void`,
    );
    return r.data;
  },

  // -----------------------------------------------------------------------
  // Customer Payments
  // -----------------------------------------------------------------------

  async getPayments(
    page = 1,
    perPage = 20,
    customerId?: string,
  ): Promise<PaginatedCustomerPayments> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (customerId) params.set("customer_id", customerId);
    const r = await apiClient.get<PaginatedCustomerPayments>(
      `/sales/payments?${params.toString()}`,
    );
    return r.data;
  },

  async createPayment(data: CustomerPaymentCreate): Promise<CustomerPayment> {
    const r = await apiClient.post<CustomerPayment>(
      "/sales/payments",
      data,
    );
    return r.data;
  },

  async importPayments(file: File): Promise<PaymentImportResult> {
    const formData = new FormData();
    formData.append("file", file);
    const r = await apiClient.post<PaymentImportResult>(
      "/sales/payments/import",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return r.data;
  },

  async getPayment(id: string): Promise<Record<string, unknown>> {
    const r = await apiClient.get(`/sales/payments/${id}`);
    return r.data;
  },

  async voidPayment(id: string): Promise<{ message: string; payment_id: string }> {
    const r = await apiClient.post<{ message: string; payment_id: string }>(
      `/sales/payments/${id}/void`,
    );
    return r.data;
  },

  async getInvoicePayments(invoiceId: string): Promise<Record<string, unknown>[]> {
    const r = await apiClient.get(`/sales/invoices/${invoiceId}/payments`);
    return r.data;
  },

  // -----------------------------------------------------------------------
  // AR Aging
  // -----------------------------------------------------------------------

  async getARAgingReport(): Promise<ARAgingReport> {
    const r = await apiClient.get<ARAgingReport>("/sales/aging");
    return r.data;
  },
};
