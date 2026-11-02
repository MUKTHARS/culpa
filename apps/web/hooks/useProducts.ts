"use client";

import { storeApi } from "@/api/store";
import type { Product, ProductVersion, StoreFacet } from "@/types";
import { useApi } from "./useApi";

export function useProducts() {
  return useApi<Product[]>(storeApi.productsPath);
}

export function useProductHistory(id: string | null) {
  return useApi<ProductVersion[]>(id ? storeApi.historyPath(id) : null);
}

/** Category filters built from the catalog. They change only when listings change, so no polling. */
export function useStoreFacets() {
  return useApi<StoreFacet[]>(storeApi.facetsPath, { revalidateOnFocus: false });
}
