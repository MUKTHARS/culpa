import { Badge } from "@/components/ui/Badge/Badge";
import { PARTY_LABEL, humanize } from "@/lib/format";
import type { Evidence } from "@/types";
import styles from "./EvidenceList.module.css";

const CHECK_ORDER = ["integrity", "rules", "listing", "replay", "claim"];

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  const sorted = [...evidence].sort((a, b) => CHECK_ORDER.indexOf(a.check) - CHECK_ORDER.indexOf(b.check));
  return (
    <ol className={styles.list}>
      {sorted.map((e, i) => (
        <li key={i} className={styles.item}>
          <div className={styles.head}>
            <Badge tone="neutral">{humanize(e.check)}</Badge>
            {e.party ? (
              <Badge tone={e.party === "buyer" ? "warn" : e.party === "merchant" ? "info" : "accent"}>
                {e.fault_class} → {PARTY_LABEL[e.party]} · weight {e.weight}
              </Badge>
            ) : (
              <Badge tone="good">No fault</Badge>
            )}
          </div>
          <p className={styles.finding}>{e.finding}</p>
          <p className={styles.cite}>Source: {e.cite}</p>
        </li>
      ))}
    </ol>
  );
}
