import type { CaseRow } from "@/types";
import { cx } from "@/lib/utils";
import styles from "./ResolutionPill.module.css";

/** Who settles this case: Culpa on its own, or an analyst. */
export function ResolutionPill({ strategy }: { strategy: CaseRow["resolution_strategy"] }) {
  if (!strategy) return <span className={styles.none}>—</span>;
  const autonomous = strategy === "autonomous";
  return (
    <span className={cx(styles.pill, autonomous ? styles.autonomous : styles.human)}>
      <span aria-hidden>{autonomous ? "⚡" : "👤"}</span>
      {autonomous ? "Autonomous PayPal Execution" : "Human Analyst Required"}
    </span>
  );
}
