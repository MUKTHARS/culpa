import styles from "./Loader.module.css";

export function Loader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className={styles.loader} role="status">
      <span className={styles.dot} />
      <span className={styles.dot} />
      <span className={styles.dot} />
      <span className={styles.label}>{label}</span>
    </div>
  );
}
