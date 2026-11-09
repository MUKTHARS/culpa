"use client";

import { useParams } from "next/navigation";
import { ApprovePanel } from "@/components/cases/ApprovePanel/ApprovePanel";
import { AuditTrail } from "@/components/cases/AuditTrail/AuditTrail";
import { EvidenceList } from "@/components/cases/EvidenceList/EvidenceList";
import { FaultSplitBar } from "@/components/cases/FaultSplitBar/FaultSplitBar";
import { ReplayPanel } from "@/components/cases/ReplayPanel/ReplayPanel";
import { Timeline } from "@/components/cases/Timeline/Timeline";
import { Badge } from "@/components/ui/Badge/Badge";
import { Card } from "@/components/ui/Card/Card";
import { Loader } from "@/components/ui/Loader/Loader";
import { ProductImage } from "@/components/ui/ProductImage/ProductImage";
import { useCase } from "@/hooks/useCases";
import { ACTION_LABEL, FAULT_LABEL, STATUS_TONE, attrs, humanize, money, pct, shortHash } from "@/lib/format";
import styles from "./page.module.css";

const FLAG_LABEL: Record<string, string> = {
  llm_unavailable: "Rule-based (AI unavailable)",
  already_settled: "Held: order already settled",
  claim_contradicts_delivery: "Held: claim contradicts delivery record",
  decided_by_rules: "Decided by mandate rules",
  replay_unavailable: "Replay unavailable",
  nondeterministic: "Agent not reproducible",
};

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, error, mutate } = useCase(params?.id);

  if (error) return <p className="error">{error.message}</p>;
  if (!data) return <Loader label="Loading case…" />;
  const v = data.verdict;
  // Opened but not yet judged: the checks run in the background and can take a few seconds.
  const analyzing = data.status === "open" || data.status === "analyzing";

  return (
    <>
      <div className={styles.head}>
        <div>
          <p className="muted mono">{data.id}{data.paypal_dispute_id ? ` · PayPal ${data.paypal_dispute_id}` : ""}</p>
          <h1>
            {data.fault_class
              ? `${data.fault_class} · ${FAULT_LABEL[data.fault_class]}`
              : analyzing ? "Analyzing the dispute…" : "Fault not determined"}
          </h1>
          <div className="row" style={{ marginTop: 8 }}>
            <Badge tone={STATUS_TONE[data.status] ?? "neutral"}>{humanize(data.status)}</Badge>
            <Badge tone="neutral">{data.source}</Badge>
            <span>{money(data.amount, data.currency)}</span>
            {data.confidence != null && <span className="muted">confidence {pct(data.confidence)}</span>}
            {data.flags.map((f) => (
              <Badge key={f} tone={f === "decided_by_rules" ? "accent" : "warn"}>{FLAG_LABEL[f] ?? humanize(f)}</Badge>
            ))}
          </div>
        </div>
      </div>

      {data.error && <p className="error">{data.error}</p>}
      {data.flags.includes("llm_unavailable") && (
        <p className={styles.notice}>
          Gemini was unavailable for this analysis, so the verdict comes from the rule-based checks: the mandate, the
          listing history, the agent replay and the buyer's record. See Jobs for the reason.
        </p>
      )}

      {v?.reason?.title && !analyzing && (
        <section className={styles.reason} aria-label="Why this verdict">
          <div className={styles.reasonHead}>
            <Badge tone="accent">{v.reason.code}</Badge>
            <h2 className={styles.reasonTitle}>{v.reason.title}</h2>
          </div>
          <p>{v.reason.summary}</p>
          <p className={styles.reasonRule}>Rule followed: {v.reason.reference}</p>
          {data.settlement && data.settlement.action !== data.recommended_action && (
            <p className={styles.reasonOverride}>
              This was Culpa&apos;s advice. The analyst decided differently:{" "}
              {data.settlement.action === "contest" ? "the claim was contested and no money moved"
                : `${ACTION_LABEL[data.settlement.action].toLowerCase()} of ${money(data.settlement.amount, data.currency)}`}
              . See Settlement.
            </p>
          )}
        </section>
      )}

      <div className={styles.layout}>
        <div className="stack">
          <Card title="Who is at fault" subtitle="Set by the cause of the problem. Other findings only change the confidence.">
            {analyzing ? (
              <Loader label="Checking the mandate, the listing, the agent's decision and the claim…" />
            ) : (
              <FaultSplitBar split={data.split} />
            )}
          </Card>
          <Card title="Buyer's claim" subtitle={humanize(data.reason.toLowerCase())}>
            <blockquote className={styles.claim}>{data.claim_text || "No message from the buyer."}</blockquote>
          </Card>
          {v && (
            <Card title="Evidence" subtitle={`Checks ran in order: ${v.check_order.map((l) => l.join(" + ")).join(" → ")}`}>
              <EvidenceList evidence={v.evidence} faultClass={data.fault_class} />
            </Card>
          )}
          <Card title="Agent replay" subtitle="The recorded decision, re-run on the same inputs and on a clarified instruction.">
            <ReplayPanel detail={data} />
          </Card>
        </div>

        <div className="stack">
          <Card title="Settlement">
            <ApprovePanel detail={data} onChange={() => mutate()} />
          </Card>
          {data.order && (
            <Card title="Order evidence">
              <div className="stack">
                <ProductImage src={data.order.product_image_url} alt={data.order.product_title} size="lg" />
                <dl className={styles.facts}>
                  <dt>Listing at purchase</dt>
                  <dd>{attrs(data.order.snapshot_attributes)}</dd>
                  <dt>Delivered</dt>
                  <dd>{data.order.delivered ? attrs(data.order.delivered_attributes) : "Not delivered"}</dd>
                  <dt>Listing now</dt>
                  <dd>{attrs(data.order.current_attributes)}</dd>
                  <dt>Merkle root</dt>
                  <dd className="mono">{shortHash(data.order.evidence_root, 18)}</dd>
                  <dt>PayPal order</dt>
                  <dd className="mono">{data.order.paypal_order_id}</dd>
                </dl>
              </div>
            </Card>
          )}
          <Card title="Timeline">
            <Timeline events={data.timeline} />
          </Card>
        </div>
      </div>

      <Card title="Audit trail" subtitle="Append-only and hash-chained: each row stores the previous row's hash.">
        <AuditTrail entries={data.audit} />
      </Card>
    </>
  );
}
