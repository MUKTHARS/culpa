import type { Product, ProductVersion, StoreFacet } from "@/types";
import { api } from "./client";

export const storeApi = {
  productsPath: "/store/products",
  facetsPath: "/store/facets",
  historyPath: (id: string) => `/store/products/${id}/history`,
  products: () => api.get<Product[]>("/store/products"),
  facets: () => api.get<StoreFacet[]>("/store/facets"),
  history: (id: string) => api.get<ProductVersion[]>(`/store/products/${id}/history`),
  update: (id: string, changes: { title?: string; price?: string; attributes?: Record<string, string> }) =>
    api.put<Product>(`/store/products/${id}`, changes),
};
