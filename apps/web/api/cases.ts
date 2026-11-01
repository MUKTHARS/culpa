import type { Action, CaseDetail, CaseRow } from "@/types";
import { api } from "./client";

export const casesApi = {
  listPath: "/cases",
  detailPath: (id: string) => `/cases/${id}`,
  list: () => api.get<CaseRow[]>("/cases"),
  get: (id: string) => api.get<CaseDetail>(`/cases/${id}`),
  simulate: (orderId: string, reason: string, claimText: string) =>
    api.post<CaseRow>("/cases/simulate", { order_id: orderId, reason, claim_text: claimText }),
  approve: (id: string, action?: Exclude<Action, "review">) =>
    api.post<{ settlement_id: string; action: Action; status: string; amount: string | null }>(
      `/cases/${id}/approve`,
      action ? { action } : {},
    ),
  reanalyze: (id: string) => api.post<CaseRow>(`/cases/${id}/reanalyze`),
};
