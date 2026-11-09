import type { CaseRow } from "@/types";
import { cx } from "@/lib/utils";
import styles from "./PayPalResult.module.css";

const RESULT = {
  success: { icon: "✓", label: "Success", tone: styles.good },
  already_refunded: { icon: "✓", label: "Already refunded earlier", tone: styles.good },
  offer_sent: { icon: "✓", label: "Offer sent to buyer", tone: styles.good },
  simulated: { icon: "○", label: "Simulated: no money moved", tone: styles.muted },
  in_progress: { icon: "…", label: "Sending to PayPal", tone: styles.muted },
  retrying: { icon: "↻", label: "Retrying", tone: styles.warn },
  failed: { icon: "✗", label: "Failed", tone: styles.bad },
} as const;

/** What PayPal answered for this case's settlement. The error, if any, shows on hover. */
export function PayPalResult({ result, error }: { result: CaseRow["paypal_result"]; error?: string | null }) {
  if (!result) return <span className={styles.muted}>—</span>;
  const r = RESULT[result];
  return (
    <span className={cx(styles.result, r.tone)} title={error ?? undefined}>
      <span className={styles.icon} aria-hidden>{r.icon}</span>
      {r.label}
    </span>
  );
}
