import type { ReactNode } from "react";
import type { ShopInput } from "@/api/agent";
import { attributeLabel, categoryLabel } from "@/lib/facets";
import { money } from "@/lib/format";
import { cx } from "@/lib/utils";
import styles from "./MandatePanel.module.css";

export type MandateStatus = "draft" | "signing" | "signed";

const STATUS_LABEL: Record<MandateStatus, string> = {
  draft: "Draft",
  signing: "Signing",
  signed: "Signed",
};

interface Props {
  mandate: ShopInput | null;
  status: MandateStatus;
  children: ReactNode;
}

/** The buyer's mandate as an authorization slip: live while drafting, frozen once signed, with the outcome below. */
export function MandatePanel({ mandate, status, children }: Props) {
  const attributes = Object.entries(mandate?.required_attributes ?? {});
  const category = categoryLabel(mandate?.category);

  return (
    <aside className={styles.panel} aria-label="Mandate">
      <div className={styles.band}>
        <p className={styles.bandTitle}>Mandate</p>
        <span className={cx(styles.status, styles[status])}>{STATUS_LABEL[status]}</span>
      </div>

      <div className={styles.cap}>
        <span className={styles.capLabel}>Spending cap</span>
        <span className={styles.capValue}>{mandate?.max_amount ? money(mandate.max_amount) : "No cap"}</span>
      </div>

      <dl className={styles.terms}>
        <dt>Task</dt>
        <dd>{mandate?.instruction ? `“${mandate.instruction}”` : <span className={styles.empty}>Not set</span>}</dd>
        <dt>Category</dt>
        <dd>{category}</dd>
        <dt>Must match</dt>
        <dd>
          {attributes.length ? (
            <ul className={styles.chips}>
              {attributes.map(([k, v]) => (
                <li key={k} className={styles.chip}>
                  {attributeLabel(k)} <strong>{v}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <span className={styles.empty}>Nothing specific</span>
          )}
        </dd>
        <dt>Valid for</dt>
        <dd>24 hours after signing</dd>
      </dl>

      <div className={styles.outcome}>{children}</div>

      {mandate?.buyer_id && (
        <p className={styles.footer}>
          {status === "signed" ? "Signed" : "Signs"} under buyer ID <span className="mono">{mandate.buyer_id}</span>.
          Culpa keeps a fingerprint of this mandate as evidence if the purchase is disputed.
        </p>
      )}
    </aside>
  );
}
