import { when } from "@/lib/format";
import styles from "./Timeline.module.css";

export function Timeline({ events }: { events: { at: string; event: string }[] }) {
  if (!events.length) return <p className="muted">No events yet.</p>;
  return (
    <ol className={styles.list}>
      {events.map((e, i) => (
        <li key={i} className={styles.item}>
          <span className={styles.dot} />
          <span className={styles.when}>{when(e.at)}</span>
          <span>{e.event}</span>
        </li>
      ))}
    </ol>
  );
}
