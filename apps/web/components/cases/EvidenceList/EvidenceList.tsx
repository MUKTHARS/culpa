import { Badge } from "@/components/ui/Badge/Badge";
import { PARTY_LABEL, humanize } from "@/lib/format";
import type { Evidence } from "@/types";
import styles from "./EvidenceList.module.css";

const CHECK_ORDER = ["integrity", "rules", "listing", "replay", "claim"];

/** How a finding counts: the cause decides who is at fault; the rest only affect confidence. */
function role(e: Evidence, faultClass: string | null): { label: string; decides: boolean } {
  if (e.primary === false) return { label: "Supporting signal", decides: false };
  if (e.fault_class === faultClass) return { label: "Cause", decides: true };
  return { label: "Also noted", decides: false };
}

export function EvidenceList({ evidence, faultClass }: { evidence: Evidence[]; faultClass: string | null }) {
  const sorted = [...evidence].sort((a, b) => CHECK_ORDER.indexOf(a.check) - CHECK_ORDER.indexOf(b.check));
  return (
    <ol className={styles.list}>
      {sorted.map((e, i) => (
        <li key={i} className={styles.item}>
          <div className={styles.head}>
            <Badge tone="neutral">{humanize(e.check)}</Badge>
            {e.party ? (
              <Badge tone={!role(e, faultClass).decides ? "neutral" : e.party === "buyer" ? "warn" : e.party === "merchant" ? "info" : "accent"}>
                {role(e, faultClass).label} · {e.fault_class} → {PARTY_LABEL[e.party]}
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
