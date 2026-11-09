import type { Action, Party } from "@/types";

export const PARTY_LABEL: Record<Party, string> = {
  buyer: "Buyer",
  merchant: "Merchant",
  agent_provider: "Agent provider",
};

export const ACTION_LABEL: Record<Action, string> = {
  refund_full: "Full refund",
  refund_partial: "Partial refund",
  contest: "Contest claim",
  review: "Human review",
};

export const FAULT_LABEL: Record<string, string> = {
  F1: "Mandate breach by agent",
  F2: "Agent reasoning error",
  F3: "Ambiguous instruction",
  F4: "Merchant misrepresentation",
  F5: "Fulfillment failure",
  F6: "Friendly fraud",
};

export const STATUS_TONE: Record<string, "neutral" | "info" | "good" | "warn" | "bad"> = {
  open: "info",
  analyzing: "info",
  awaiting_approval: "warn",
  needs_review: "warn",
  settling: "info",
  settled: "good",
  offer_sent: "info",
  already_refunded: "good",
  settle_failed: "bad",
};

export function money(value: string | null | undefined, currency = "USD"): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n);
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function shortHash(h: string | null | undefined, n = 10): string {
  if (!h) return "—";
  return h.length > n ? `${h.slice(0, n)}…` : h;
}

export function attrs(a: Record<string, string> | null | undefined): string {
  if (!a) return "—";
  return Object.entries(a)
    .map(([k, v]) => `${k}: ${v}`)
    .join(" · ");
}

export function humanize(s: string): string {
  return s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
