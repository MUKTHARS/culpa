import { PARTY_LABEL, pct } from "@/lib/format";
import type { Party, Split } from "@/types";
import styles from "./FaultSplitBar.module.css";

const ORDER: Party[] = ["merchant", "agent_provider", "buyer"];

export function FaultSplitBar({ split }: { split: Split | null }) {
  if (!split || ORDER.every((p) => !split[p])) {
    return <p className="muted">No party was found at fault yet.</p>;
  }
  return (
    <div className={styles.wrap}>
      <div className={styles.bar} role="img" aria-label="Fault split by party">
        {ORDER.filter((p) => split[p] > 0).map((p) => (
          <span key={p} className={`${styles.segment} ${styles[p]}`} style={{ width: `${split[p] * 100}%` }}>
            {split[p] >= 0.12 ? pct(split[p]) : ""}
          </span>
        ))}
      </div>
      <ul className={styles.legend}>
        {ORDER.map((p) => (
          <li key={p}>
            <span className={`${styles.swatch} ${styles[p]}`} />
            {PARTY_LABEL[p]} <strong>{pct(split[p])}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}
