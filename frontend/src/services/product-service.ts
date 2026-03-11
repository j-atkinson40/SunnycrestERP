import apiClient from "@/lib/api-client";
import type {
  CategoryCreate,
  CategoryUpdate,
  PaginatedProducts,
  Product,
  ProductCategory,
  ProductCreate,
  ProductUpdate,
} from "@/types/product";

export const productService = {
  // -----------------------------------------------------------------------
  // Products
  // -----------------------------------------------------------------------

  async getProducts(
    page = 1,
    perPage = 20,
    search?: string,
    categoryId?: string,
    includeInactive = false,
  ): Promise<PaginatedProducts> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (search) params.set("search", search);
    if (categoryId) params.set("category_id", categoryId);
    if (includeInactive) params.set("include_inactive", "true");
    const response = await apiClient.get<PaginatedProducts>(
      `/products?${params.toString()}`,
    );
    return response.data;
  },

  async getProduct(id: string): Promise<Product> {
    const response = await apiClient.get<Product>(`/products/${id}`);
    return response.data;
  },

  async createProduct(data: ProductCreate): Promise<Product> {
    const response = await apiClient.post<Product>("/products", data);
    return response.data;
  },

  async updateProduct(id: string, data: ProductUpdate): Promise<Product> {
    const response = await apiClient.patch<Product>(`/products/${id}`, data);
    return response.data;
  },

  async deleteProduct(id: string): Promise<void> {
    await apiClient.delete(`/products/${id}`);
  },

  // -----------------------------------------------------------------------
  // Categories
  // -----------------------------------------------------------------------

  async getCategories(includeInactive = false): Promise<ProductCategory[]> {
    const params = includeInactive ? "?include_inactive=true" : "";
    const response = await apiClient.get<ProductCategory[]>(
      `/products/categories${params}`,
    );
    return response.data;
  },

  async createCategory(data: CategoryCreate): Promise<ProductCategory> {
    const response = await apiClient.post<ProductCategory>(
      "/products/categories",
      data,
    );
    return response.data;
  },

  async updateCategory(
    id: string,
    data: CategoryUpdate,
  ): Promise<ProductCategory> {
    const response = await apiClient.patch<ProductCategory>(
      `/products/categories/${id}`,
      data,
    );
    return response.data;
  },

  async deleteCategory(id: string): Promise<void> {
    await apiClient.delete(`/products/categories/${id}`);
  },
};
