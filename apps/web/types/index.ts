export type Party = "buyer" | "merchant" | "agent_provider";
export type Split = Record<Party, number>;
export type Action = "refund_full" | "refund_partial" | "contest" | "review";

export interface Product {
  id: string;
  merchant_id: string;
  title: string;
  category: string;
  price: string;
  currency: string;
  attributes: Record<string, string>;
  image_url: string;
  version: number;
  updated_at: string;
}

export interface ProductVersion {
  version: number;
  title: string;
  price: string;
  attributes: Record<string, string>;
  captured_at: string;
}

export interface Evidence {
  check: string;
  finding: string;
  cite: string;
  fault_class: string | null;
  party: Party | null;
  weight: number;
}

export interface Verdict {
  fault_class: string | null;
  fault_name: string | null;
  split: Split;
  confidence: number;
  action: Action;
  refund_amount: string | null;
  liability: Partial<Record<Party, string>>;
  evidence: Evidence[];
  flags: string[];
  check_order: string[][];
  degraded: boolean;
}

export interface EvidenceFingerprint {
  evidence_id: string;
  mandate_hash: string;
  trace_hash: string;
  snapshot_hash: string;
  root: string;
  captured_at: string;
}

export interface Order {
  id: string;
  paypal_order_id: string;
  capture_id: string | null;
  simulated: boolean;
  status: "created" | "captured" | "cancelled";
  amount: string;
  currency: string;
  buyer_id: string;
  merchant_id: string;
  product_id: string;
  product_title: string;
  product_image_url: string;
  snapshot_attributes: Record<string, string>;
  current_attributes: Record<string, string>;
  evidence: EvidenceFingerprint | null;
  evidence_root: string | null;
  created_at: string;
  approved_at: string | null;
  shipped_at: string | null;
  delivered: boolean;
  delivered_attributes: Record<string, string> | null;
  tracking_number: string | null;
  approve_url: string;
}

export interface CaseRow {
  id: string;
  source: "paypal" | "simulator";
  status: string;
  reason: string;
  amount: string;
  currency: string;
  buyer_id: string;
  order_id: string | null;
  paypal_dispute_id: string | null;
  fault_class: string | null;
  fault_name: string | null;
  split: Split | null;
  confidence: number | null;
  recommended_action: Action | null;
  refund_amount: string | null;
  flags: string[];
  created_at: string;
  updated_at: string;
}

export interface Settlement {
  id: string;
  action: Action;
  status: string;
  amount: string | null;
  simulated: boolean;
  error: string | null;
  attempts: number;
  approved_by: string;
  idempotency_key: string;
  paypal_response: Record<string, unknown> | null;
  updated_at: string;
}

export interface AuditEntry {
  id: number;
  actor: string;
  action: string;
  data: Record<string, unknown>;
  hash: string;
  prev_hash: string;
  created_at: string;
}

export interface CaseDetail extends CaseRow {
  claim_text: string;
  error: string | null;
  liability: Partial<Record<Party, string>> | null;
  verdict: Verdict | null;
  order: Order | null;
  mandate: { id: string; text: string; constraints: Record<string, unknown>; hash: string } | null;
  trace: {
    id: string;
    policy: string;
    model: string;
    instruction: string;
    chosen_product_id: string;
    reasoning: string;
    candidates: { id: string; title: string; price: string; attributes: Record<string, string> }[];
    candidate_images: Record<string, string>;
  } | null;
  settlement: Settlement | null;
  timeline: { at: string; event: string }[];
  audit: AuditEntry[];
}

export interface ShopResult {
  order_id: string;
  paypal_order_id: string;
  approve_url: string;
  simulated: boolean;
  policy: string;
  reasoning: string;
  product: { id: string; title: string; price: string; attributes: Record<string, string>; image_url: string };
  mandate: { id: string; hash: string; constraints: Record<string, unknown> };
  candidates: number;
}

export interface SystemStatus {
  env: string;
  paypal: { configured: boolean; env: string; webhook_verification: boolean; breaker: string };
  llm: { configured: boolean; judge_model: string; fast_model: string; breaker: string; unavailable_reason: string | null };
  queue: { mode: string; depth: number | null };
  auto_settle: boolean;
  confidence_threshold: number;
  analyst_login_configured: boolean;
}

export interface BenchMetrics {
  n: number;
  accuracy: number;
  macro_f1: number;
  wrong_money_rate: number;
  escalation_rate: number;
  auto_decided_accuracy: number | null;
  friendly_fraud_recall: number | null;
  false_accusation_rate: number | null;
  accuracy_by_difficulty: Record<string, number>;
  confusion: Record<string, Record<string, number>>;
}

export interface BenchResults {
  generated_at: string;
  n_cases: number;
  n_hard: number;
  systems: { name: string; metrics: BenchMetrics; ms_per_case: number }[];
}

export interface DeadLetter {
  id: number;
  outbox_id: number;
  topic: string;
  payload: Record<string, unknown>;
  error: string;
  attempts: number;
  created_at: string;
  replayed_at: string | null;
}

export interface JobStats {
  outbox: Record<string, number>;
  dead_letters_open: number;
  audit_chain_ok: boolean;
  audit_chain_broken_at: number | null;
}
