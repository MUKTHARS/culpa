"use client";

import { ordersApi } from "@/api/orders";
import { POLL_MS } from "@/constants/config";
import type { Order } from "@/types";
import { useApi } from "./useApi";

export function useOrders() {
  return useApi<Order[]>(ordersApi.listPath, { refreshInterval: POLL_MS });
}
