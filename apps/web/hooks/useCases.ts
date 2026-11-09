"use client";

import { casesApi } from "@/api/cases";
import { POLL_MS } from "@/constants/config";
import type { CaseDetail, CaseRow } from "@/types";
import { useApi } from "./useApi";

export function useCases() {
  return useApi<CaseRow[]>(casesApi.listPath, { refreshInterval: POLL_MS });
}

// Autonomous cases go straight from analysis to settling, so keep polling quickly until PayPal has answered.
const ACTIVE = new Set(["open", "analyzing", "settling"]);

export function useCase(id: string | undefined) {
  return useApi<CaseDetail>(id ? casesApi.detailPath(id) : null, {
    refreshInterval: (data) => (data && !ACTIVE.has(data.status) ? 15000 : 1500),
  });
}
