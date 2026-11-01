"use client";

import useSWR, { type SWRConfiguration } from "swr";
import { fetcher } from "@/api/client";

/** Stale-while-revalidate GET with a shared cache. Pass null to skip the request. */
export function useApi<T>(path: string | null, config?: SWRConfiguration<T>) {
  return useSWR<T>(path, (p: string) => fetcher<T>(p), { revalidateOnFocus: true, dedupingInterval: 1500, ...config });
}
