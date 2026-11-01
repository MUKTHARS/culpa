import { pct } from "@/lib/format";
import type { BenchResults } from "@/types";
import styles from "./ResultsTable.module.css";

const LABEL: Record<string, string> = {
  claim_keywords: "Baseline: reads the claim only",
  culpa_no_replay: "Culpa without agent replay",
  culpa_full: "Culpa (all four checks)",
  culpa_full_llm: "Culpa + Claude judge",
};

export function ResultsTable({ results }: { results: BenchResults }) {
  return (
    <div className="scroll-x">
      <table className="table">
        <thead>
          <tr>
            <th>System</th>
            <th>Accuracy</th>
            <th>Macro-F1</th>
            <th>Wrong-money rate</th>
            <th>Escalated to human</th>
            <th>Friendly-fraud recall</th>
            <th>False accusations</th>
            <th>ms / case</th>
          </tr>
        </thead>
        <tbody>
          {results.systems.map((s) => (
            <tr key={s.name} className={s.name.startsWith("culpa_full") ? styles.best : undefined}>
              <td>
                <strong>{LABEL[s.name] ?? s.name}</strong>
              </td>
              <td>{pct(s.metrics.accuracy, 1)}</td>
              <td>{s.metrics.macro_f1.toFixed(3)}</td>
              <td className={styles.money}>{pct(s.metrics.wrong_money_rate, 1)}</td>
              <td>{pct(s.metrics.escalation_rate, 1)}</td>
              <td>{pct(s.metrics.friendly_fraud_recall, 0)}</td>
              <td>{pct(s.metrics.false_accusation_rate, 1)}</td>
              <td>{s.ms_per_case}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
