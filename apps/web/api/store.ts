import type { Product, ProductVersion } from "@/types";
import { api } from "./client";

export const storeApi = {
  productsPath: "/store/products",
  historyPath: (id: string) => `/store/products/${id}/history`,
  products: () => api.get<Product[]>("/store/products"),
  history: (id: string) => api.get<ProductVersion[]>(`/store/products/${id}/history`),
  update: (id: string, changes: { title?: string; price?: string; attributes?: Record<string, string> }) =>
    api.put<Product>(`/store/products/${id}`, changes),
};
