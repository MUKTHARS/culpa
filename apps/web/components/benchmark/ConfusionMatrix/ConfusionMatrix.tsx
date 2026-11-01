import { FAULT_LABEL } from "@/lib/format";
import styles from "./ConfusionMatrix.module.css";

const CLASSES = ["F1", "F2", "F3", "F4", "F5", "F6"];

export function ConfusionMatrix({ confusion }: { confusion: Record<string, Record<string, number>> }) {
  const cols = [...CLASSES, "none"];
  const max = Math.max(1, ...CLASSES.flatMap((g) => cols.map((p) => confusion[g]?.[p] ?? 0)));
  return (
    <div className="scroll-x">
      <table className={styles.matrix}>
        <thead>
          <tr>
            <th>Actual \ Predicted</th>
            {cols.map((c) => (
              <th key={c} title={FAULT_LABEL[c] ?? "No fault found"}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {CLASSES.map((g) => (
            <tr key={g}>
              <th title={FAULT_LABEL[g]}>
                {g} <span className="muted">{FAULT_LABEL[g]}</span>
              </th>
              {cols.map((p) => {
                const n = confusion[g]?.[p] ?? 0;
                const tone = g === p ? "var(--accent)" : "var(--bad)";
                return (
                  <td key={p} style={{ background: n ? `color-mix(in srgb, ${tone} ${Math.round(15 + 60 * (n / max))}%, white)` : undefined }}>
                    {n || ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
