import { humanize, shortHash, when } from "@/lib/format";
import type { AuditEntry } from "@/types";

export function AuditTrail({ entries }: { entries: AuditEntry[] }) {
  if (!entries.length) return <p className="muted">No audit entries.</p>;
  return (
    <div className="scroll-x">
      <table className="table">
        <thead>
          <tr>
            <th>When</th>
            <th>Actor</th>
            <th>Action</th>
            <th>Hash</th>
            <th>Previous</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((a) => (
            <tr key={a.id}>
              <td>{when(a.created_at)}</td>
              <td>{a.actor}</td>
              <td>{humanize(a.action.replace(".", " "))}</td>
              <td className="mono">{shortHash(a.hash)}</td>
              <td className="mono">{shortHash(a.prev_hash)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
