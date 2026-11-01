"use client";

import { storeApi } from "@/api/store";
import type { Product, ProductVersion } from "@/types";
import { useApi } from "./useApi";

export function useProducts() {
  return useApi<Product[]>(storeApi.productsPath);
}

export function useProductHistory(id: string | null) {
  return useApi<ProductVersion[]>(id ? storeApi.historyPath(id) : null);
}
