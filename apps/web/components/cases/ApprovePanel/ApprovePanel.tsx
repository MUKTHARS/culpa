"use client";

import { useState } from "react";
import { casesApi } from "@/api/cases";
import { Badge } from "@/components/ui/Badge/Badge";
import { Button } from "@/components/ui/Button/Button";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { ACTION_LABEL, PARTY_LABEL, humanize, money, when } from "@/lib/format";
import { cx } from "@/lib/utils";
import type { Action, CaseDetail, Party } from "@/types";
import styles from "./ApprovePanel.module.css";

type Option = Exclude<Action, "review">;

const AMOUNT = /^\d{1,7}(\.\d{1,2})?$/;

/** What each option does on PayPal for this case, so the analyst knows exactly what will happen. */
function paypalStep(option: Option, detail: CaseDetail): string {
  const dispute = Boolean(detail.paypal_dispute_id);
  if (option === "refund_full") return dispute ? "PayPal: accept the buyer's claim (full refund)" : "PayPal: refund the payment in full";
  if (option === "refund_partial") return dispute ? "PayPal: send the buyer a refund offer" : "PayPal: refund part of the payment";
  return dispute ? "PayPal: submit Culpa's evidence to contest the dispute" : "No PayPal dispute to contest: the claim is denied in Culpa";
}

/** The settlement in plain words: what happened to the money. */
function outcomeTitle(action: Action, status: string, amount: string | null, detail: CaseDetail): string {
  const done = status === "succeeded";
  if (detail.status === "already_refunded") return "Already refunded earlier";
  const failed = status === "failed_final" || detail.status === "settle_failed";
  if (action === "contest") return failed ? "Contest failed" : done ? "Dispute contested" : "Contesting the dispute…";
  const sum = money(amount, detail.currency);
  if (failed) return `Refund of ${sum} failed`;
  if (detail.status === "offer_sent") return `Refund offer of ${sum} sent`;
  if (action === "refund_partial") return done ? `Refunded ${sum} of ${money(detail.amount, detail.currency)}` : `Refunding ${sum}…`;
  return done ? `Refunded ${sum} in full` : `Refunding ${sum}…`;
}

function outcomeDetail(action: Action, status: string, simulated: boolean, detail: CaseDetail): string {
  if (detail.status === "already_refunded") return "PayPal shows this payment was refunded in full before this case. Nothing more was sent, so there was no second refund.";
  if (status === "failed_final") return "PayPal rejected the action. See the error below; the case needs another decision.";
  if (detail.status === "settle_failed") return "PayPal could not be reached after every retry. No money moved. Replay it from the Jobs page.";
  if (detail.status === "offer_sent") return "Sent on the buyer's PayPal dispute. The money moves only if the buyer accepts the offer.";
  if (action === "contest") {
    return detail.paypal_dispute_id
      ? "No money moved. Culpa's fingerprinted evidence was sent to PayPal to defend the payment."
      : "No money moved. There was no PayPal dispute to answer, so the buyer's claim was denied in Culpa.";
  }
  if (simulated) return "Simulated order: the refund was recorded in Culpa, but no PayPal money moved.";
  return detail.paypal_dispute_id ? "Sent to PayPal on the buyer's dispute." : "Refunded through PayPal to the buyer's account.";
}

export function ApprovePanel({ detail, onChange }: { detail: CaseDetail; onChange: () => void }) {
  const recommended = detail.recommended_action;
  const executable = recommended && recommended !== "review" ? (recommended as Option) : null;
  const [choice, setChoice] = useState<Option | null>(executable);
  const [partial, setPartial] = useState(detail.refund_amount ?? "");
  const [note, setNote] = useState("");

  const approve = useAsyncAction(async () => {
    if (!choice) return;
    await casesApi.approve(detail.id, {
      action: choice,
      amount: choice === "refund_partial" ? partial : undefined,
      note: note.trim() || undefined,
    });
    onChange();
  });
  const reanalyze = useAsyncAction(async () => {
    await casesApi.reanalyze(detail.id);
    onChange();
  });

  const s = detail.settlement;
  const canApprove = !s && (detail.status === "awaiting_approval" || detail.status === "needs_review");
  const total = Number(detail.amount);
  const partialOk = AMOUNT.test(partial) && Number(partial) > 0 && Number(partial) < total;
  const ready = choice !== null && (choice !== "refund_partial" || partialOk);
  const bearers = Object.entries(detail.liability ?? {});
  const flags = detail.flags ?? [];

  const options: { value: Option; title: string; detail: string }[] = [
    { value: "refund_full", title: "Full refund", detail: `Return ${money(detail.amount, detail.currency)} to the buyer.` },
    { value: "refund_partial", title: "Partial refund", detail: "Refund part of the payment; the buyer keeps the item." },
    { value: "contest", title: "Contest the claim", detail: "Keep the payment and defend it with the fingerprinted evidence." },
  ];

  const summary = !choice ? null
    : choice === "refund_full" ? `Refund ${money(detail.amount, detail.currency)} to the buyer.`
    : choice === "refund_partial" ? (partialOk ? `Refund ${money(partial, detail.currency)} of ${money(detail.amount, detail.currency)} to the buyer.` : "Enter a valid partial amount.")
    : "Contest the dispute; no money moves.";

  return (
    <div className={styles.wrap}>
      {!s && (
      <div className={styles.recommendation}>
        <p className={styles.label}>Culpa recommends</p>
        <p className={styles.action}>{recommended ? ACTION_LABEL[recommended] : "Waiting for analysis"}</p>
        {detail.refund_amount && recommended !== "contest" && <p>{money(detail.refund_amount, detail.currency)} to the buyer</p>}
        {bearers.length > 0 && (
          <ul className={styles.liability}>
            {bearers.map(([party, amount]) => (
              <li key={party}>{PARTY_LABEL[party as Party]} bears {money(amount, detail.currency)}</li>
            ))}
          </ul>
        )}
        {recommended === "review" && (
          <p className={styles.hint}>
            {flags.includes("needs_evidence") ? "Ask the buyer for photos or a return before choosing."
              : flags.includes("processing_dispute") ? "Check the PayPal transaction history before choosing."
              : "The evidence does not prove a single cause. Choose an outcome below."}
          </p>
        )}
      </div>
      )}

      {s ? (
        <div className={styles.result}>
          {/* What actually happened comes first; the recommendation is only context. */}
          <div className={cx(styles.outcome, s.action === "contest" ? styles.outcomeContest : styles.outcomeRefund)}>
            <p className={styles.label}>Outcome</p>
            <p className={styles.action}>{outcomeTitle(s.action, s.status, s.amount, detail)}</p>
            <p>{outcomeDetail(s.action, s.status, s.simulated, detail)}</p>
          </div>
          <div className="row">
            {detail.status === "already_refunded" ? (
              <Badge tone="good">No action needed</Badge>
            ) : (
              <Badge tone={s.status === "succeeded" ? "good" : s.status === "failed_final" ? "bad" : "info"}>{humanize(s.status)}</Badge>
            )}
            {s.simulated && <Badge tone="warn">Simulated: no money moved</Badge>}
          </div>
          {recommended && recommended !== "review" && (
            <p className={styles.hint}>
              {recommended === s.action
                ? `This follows Culpa's recommendation (${ACTION_LABEL[recommended].toLowerCase()}).`
                : `Culpa recommended ${ACTION_LABEL[recommended].toLowerCase()}; the analyst chose to ${s.action === "contest" ? "contest the claim" : ACTION_LABEL[s.action].toLowerCase()}.`}
            </p>
          )}
          {s.error && <p className="error">{s.error}</p>}
          <dl className={styles.facts}>
            <dt>Approved by</dt>
            <dd>{s.approved_by === "auto-policy" ? "Culpa, automatically (no analyst)" : s.approved_by}</dd>
            <dt>Attempts</dt>
            <dd>{s.attempts}</dd>
            <dt>Last update</dt>
            <dd>{when(s.updated_at)}</dd>
            <dt>PayPal request ID</dt>
            <dd className="mono">{s.idempotency_key}</dd>
          </dl>
          <p className={styles.hint}>The request ID is reused on every retry, so PayPal never applies this twice.</p>
        </div>
      ) : canApprove ? (
        <div className={styles.controls}>
          <fieldset className={styles.options}>
            <legend className={styles.question}>Settle this dispute</legend>
            {options.map((o) => (
              <label key={o.value} className={cx(styles.option, choice === o.value && styles.optionActive)}>
                <input type="radio" name={`settle-${detail.id}`} className={styles.radio} checked={choice === o.value}
                       onChange={() => setChoice(o.value)} />
                <span className={styles.optionHead}>
                  <span className={styles.optionTitle}>{o.title}</span>
                  {o.value === executable && <Badge tone="accent">Recommended</Badge>}
                </span>
                <span className={styles.optionDetail}>{o.detail}</span>
                <span className={styles.optionStep}>{paypalStep(o.value, detail)}</span>
                {o.value === "refund_partial" && choice === "refund_partial" && (
                  <span className={styles.amount}>
                    <span aria-hidden>$</span>
                    <input value={partial} onChange={(e) => setPartial(e.target.value)} inputMode="decimal"
                           placeholder="0.00" aria-label="Partial refund amount" className={styles.amountInput} />
                    <span className={styles.amountMax}>of {money(detail.amount, detail.currency)}</span>
                  </span>
                )}
              </label>
            ))}
          </fieldset>

          <label className={styles.noteField}>
            <span className={styles.noteLabel}>Note for the audit log (optional)</span>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000}
                      className={styles.note} placeholder="Why you chose this outcome" />
          </label>

          {summary && <p className={styles.confirm}>{summary}</p>}
          <div className="row">
            <Button onClick={() => approve.run()} loading={approve.pending} disabled={!ready}>
              {choice === "contest" ? "Confirm and contest" : "Confirm and refund"}
            </Button>
            <Button variant="ghost" onClick={() => reanalyze.run()} loading={reanalyze.pending}>
              Re-run analysis
            </Button>
          </div>
          {approve.error && <p className="error">{approve.error}</p>}
          {reanalyze.error && <p className="error">{reanalyze.error}</p>}
        </div>
      ) : (
        <p className="muted">Waiting for analysis…</p>
      )}
    </div>
  );
}
