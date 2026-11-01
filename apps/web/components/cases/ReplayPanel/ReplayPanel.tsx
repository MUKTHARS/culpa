import { ProductImage } from "@/components/ui/ProductImage/ProductImage";
import { attrs, money } from "@/lib/format";
import type { CaseDetail } from "@/types";
import styles from "./ReplayPanel.module.css";

export function ReplayPanel({ detail }: { detail: CaseDetail }) {
  const { trace, mandate, verdict } = detail;
  if (!trace || !mandate) return <p className="muted">No agent trace recorded for this transaction.</p>;
  const replay = verdict?.evidence.filter((e) => e.check === "replay") ?? [];
  const required = (mandate.constraints.required_attributes ?? {}) as Record<string, string>;

  return (
    <div className={styles.wrap}>
      <dl className={styles.facts}>
        <dt>Buyer instruction</dt>
        <dd>“{trace.instruction}”</dd>
        <dt>Mandate requires</dt>
        <dd>{Object.keys(required).length ? attrs(required) : "No attribute constraints"}</dd>
        <dt>Agent policy</dt>
        <dd>
          {trace.policy}
          {trace.model ? ` (${trace.model})` : ""}
        </dd>
        <dt>Agent reasoning</dt>
        <dd>{trace.reasoning || "—"}</dd>
      </dl>
      <div className="scroll-x">
        <table className="table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Attributes</th>
              <th>Price</th>
            </tr>
          </thead>
          <tbody>
            {trace.candidates.map((c) => (
              <tr key={c.id} className={c.id === trace.chosen_product_id ? styles.chosen : undefined}>
                <td>
                  <span className={styles.candidate}>
                    <ProductImage src={trace.candidate_images?.[c.id]} alt={c.title} size="sm" />
                    <span>
                      {c.title}
                      {c.id === trace.chosen_product_id ? <strong> · chosen</strong> : null}
                    </span>
                  </span>
                </td>
                <td>{attrs(c.attributes)}</td>
                <td>{money(c.price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {replay.length > 0 && (
        <div className={styles.result}>
          <p className={styles.label}>Replay result</p>
          {replay.map((e, i) => (
            <p key={i}>{e.finding}</p>
          ))}
        </div>
      )}
    </div>
  );
}
