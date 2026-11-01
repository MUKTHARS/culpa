import type { Order } from "@/types";
import { api } from "./client";

export const ordersApi = {
  listPath: "/orders",
  list: () => api.get<Order[]>("/orders"),
  ship: (id: string) => api.post<Order>(`/orders/${id}/ship`),
  capture: (token: string) => api.post<Order>("/checkout/capture", { token }),
};
