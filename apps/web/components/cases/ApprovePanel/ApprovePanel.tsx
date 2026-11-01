"use client";

import { useState } from "react";
import { casesApi } from "@/api/cases";
import { Badge } from "@/components/ui/Badge/Badge";
import { Button } from "@/components/ui/Button/Button";
import { Select } from "@/components/ui/Field/Field";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { ACTION_LABEL, PARTY_LABEL, humanize, money } from "@/lib/format";
import type { Action, CaseDetail, Party } from "@/types";
import styles from "./ApprovePanel.module.css";

type Executable = Exclude<Action, "review">;

export function ApprovePanel({ detail, onChange }: { detail: CaseDetail; onChange: () => void }) {
  const recommended = detail.recommended_action;
  const [override, setOverride] = useState<Executable | "">("");
  const approve = useAsyncAction(async () => {
    await casesApi.approve(detail.id, override || undefined);
    onChange();
  });
  const reanalyze = useAsyncAction(async () => {
    await casesApi.reanalyze(detail.id);
    onChange();
  });

  const s = detail.settlement;
  const canApprove = !s && (detail.status === "awaiting_approval" || detail.status === "needs_review");
  const needsChoice = recommended === "review" || recommended === null;

  return (
    <div className={styles.wrap}>
      <div className={styles.recommendation}>
        <p className={styles.label}>Policy recommendation</p>
        <p className={styles.action}>{recommended ? ACTION_LABEL[recommended] : "—"}</p>
        {detail.refund_amount && <p>Refund {money(detail.refund_amount, detail.currency)}</p>}
        {detail.liability && Object.keys(detail.liability).length > 0 && (
          <ul className={styles.liability}>
            {Object.entries(detail.liability).map(([party, amount]) => (
              <li key={party}>
                {PARTY_LABEL[party as Party]} bears {money(amount, detail.currency)}
              </li>
            ))}
          </ul>
        )}
      </div>

      {s ? (
        <div className={styles.settlement}>
          <div className="row">
            <Badge tone={s.status === "succeeded" ? "good" : s.status === "failed_final" ? "bad" : "info"}>
              {humanize(s.status)}
            </Badge>
            <span>{ACTION_LABEL[s.action]}</span>
            {s.amount && <span>{money(s.amount, detail.currency)}</span>}
            {s.simulated && <Badge tone="warn">Simulated: no money moved</Badge>}
          </div>
          {s.error && <p className="error">{s.error}</p>}
          <p className="muted mono">PayPal-Request-Id {s.idempotency_key}</p>
          <p className="muted">
            Approved by {s.approved_by} · {s.attempts} attempt{s.attempts === 1 ? "" : "s"}
          </p>
        </div>
      ) : canApprove ? (
        <div className={styles.controls}>
          <Select value={override} onChange={(e) => setOverride(e.target.value as Executable | "")}
                  aria-label="Action to execute">
            <option value="">{needsChoice ? "Choose an action…" : `Use recommendation (${ACTION_LABEL[recommended!]})`}</option>
            <option value="refund_full">Override: full refund</option>
            {detail.refund_amount && <option value="refund_partial">Override: partial refund</option>}
            <option value="contest">Override: contest claim</option>
          </Select>
          <div className="row">
            <Button onClick={() => approve.run()} loading={approve.pending} disabled={needsChoice && !override}>
              Approve and execute on PayPal
            </Button>
            <Button variant="secondary" onClick={() => reanalyze.run()} loading={reanalyze.pending}>
              Re-run analysis
            </Button>
          </div>
          {approve.error && <p className="error">{approve.error}</p>}
          {reanalyze.error && <p className="error">{reanalyze.error}</p>}
          <p className="muted">
            Money only moves through the settlement worker, with a deterministic idempotency key. Approving twice is safe.
          </p>
        </div>
      ) : (
        <p className="muted">Waiting for analysis…</p>
      )}
    </div>
  );
}
