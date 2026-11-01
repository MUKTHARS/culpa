import type { ShopResult } from "@/types";
import { api } from "./client";

export interface ShopInput {
  buyer_id: string;
  instruction: string;
  max_amount?: string;
  category?: string;
  required_attributes: Record<string, string>;
  device_id?: string;
}

export const agentApi = {
  shop: (input: ShopInput) => api.post<ShopResult>("/agent/shop", input),
};
