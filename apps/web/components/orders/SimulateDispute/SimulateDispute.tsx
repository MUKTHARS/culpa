"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { casesApi } from "@/api/cases";
import { Badge } from "@/components/ui/Badge/Badge";
import { Button } from "@/components/ui/Button/Button";
import { Field, Input, Select, TextArea } from "@/components/ui/Field/Field";
import { ProductImage } from "@/components/ui/ProductImage/ProductImage";
import { ROUTES } from "@/constants/routes";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { attributeLabel } from "@/lib/facets";
import { attrs, money } from "@/lib/format";
import { cx } from "@/lib/utils";
import type { Order } from "@/types";
import styles from "./SimulateDispute.module.css";

type Problem = "not_received" | "not_as_described" | "agent_wrong" | "unauthorized" | "other";

// What the buyer picks, in their words, and the PayPal dispute reason each one is filed under.
const PROBLEMS: { value: Problem; title: string; detail: string; reason: string }[] = [
  { value: "not_received", title: "I didn't receive it", detail: "The order never arrived.", reason: "ITEM_NOT_RECEIVED" },
  { value: "not_as_described", title: "It's not as described", detail: "Wrong size, colour, material or model.", reason: "ITEM_NOT_AS_DESCRIBED" },
  { value: "agent_wrong", title: "My agent bought the wrong thing", detail: "The item isn't what I wanted.", reason: "ITEM_NOT_AS_DESCRIBED" },
  { value: "unauthorized", title: "I didn't authorise this", detail: "I never approved this purchase.", reason: "UNAUTHORISED" },
  { value: "other", title: "Something else", detail: "Describe the problem yourself.", reason: "OTHER" },
];

/** The buyer's main complaint, written from the structured answers ("" until the required details are given). */
function mainSentence(problem: Problem | null, f: { attr: string; expected: string; received: string; wanted: string }) {
  let main = "";
  if (problem === "not_received") main = "The item never arrived.";
  if (problem === "not_as_described" && f.attr && f.expected.trim() && f.received.trim())
    main = `I expected ${f.attr} ${f.expected.trim()}, but received ${f.received.trim()}.`;
  if (problem === "agent_wrong") main = `My AI agent bought the wrong item.${f.wanted.trim() ? ` I wanted ${f.wanted.trim()}.` : ""}`;
  if (problem === "unauthorized") main = "I never authorised this purchase.";
  return main;
}

export function SimulateDispute({ order, onDone }: { order: Order; onDone: () => void }) {
  const router = useRouter();
  const ordered = order.snapshot_attributes;
  const delivered = order.delivered ? order.delivered_attributes ?? null : null;
  const detailKeys = Object.keys({ ...ordered, ...(delivered ?? {}) });

  const [problem, setProblem] = useState<Problem | null>(null);
  const [attr, setAttr] = useState("");
  const [expected, setExpected] = useState("");
  const [received, setReceived] = useState("");
  const [wanted, setWanted] = useState("");
  const [notes, setNotes] = useState("");

  const chosen = PROBLEMS.find((p) => p.value === problem);
  const main = mainSentence(problem, { attr, expected, received, wanted });
  // The message PayPal would receive from the buyer. "Something else" is the only problem told in free text.
  const claim = [main, notes.trim()].filter(Boolean).join(" ");
  const ready = Boolean(chosen && (problem === "other" ? notes.trim() : main));

  const pickDetail = (key: string) => {
    setAttr(key);
    // What arrived is on record; what the buyer expected is theirs to say.
    setReceived(key ? delivered?.[key] ?? "" : "");
    setExpected("");
  };

  // Set once the case exists: the form stays up, busy, until the case page replaces it.
  const [openedCase, setOpenedCase] = useState<string | null>(null);
  const submit = useAsyncAction(async () => {
    if (!chosen) return;
    const c = await casesApi.simulate(order.id, chosen.reason, claim);
    setOpenedCase(c.id);
    onDone();
    router.push(ROUTES.caseDetail(c.id));
  });

  return (
    <section className={styles.panel} aria-labelledby={`dispute-${order.id}`}>
      <header className={styles.head}>
        <div>
          <h2 className={styles.title} id={`dispute-${order.id}`}>Open a dispute</h2>
          <p className={styles.subtitle}>
            Filed exactly like a buyer&apos;s dispute arriving from PayPal, so you can demo without a sandbox dispute.
          </p>
        </div>
        <Badge tone="warn">Simulator</Badge>
      </header>

      <div className={styles.order}>
        <ProductImage src={order.product_image_url} alt={order.product_title} size="md" />
        <dl className={styles.orderFacts}>
          <dt>Item</dt>
          <dd><strong>{order.product_title}</strong></dd>
          <dt>Ordered</dt>
          <dd>{attrs(ordered)}</dd>
          <dt>Delivered</dt>
          <dd>{delivered ? attrs(delivered) : order.shipped_at ? "Shipped, delivery not confirmed" : "Not shipped yet"}</dd>
        </dl>
        <p className={styles.amount}>{money(order.amount, order.currency)}</p>
      </div>

      <fieldset className={styles.problems}>
        <legend className={styles.question}>What went wrong?</legend>
        <div className={styles.choices}>
          {PROBLEMS.map((p) => (
            <label key={p.value} className={cx(styles.choice, problem === p.value && styles.choiceActive)}>
              <input type="radio" name={`problem-${order.id}`} value={p.value} checked={problem === p.value}
                     onChange={() => setProblem(p.value)} className={styles.radio} />
              <span className={styles.choiceTitle}>{p.title}</span>
              <span className={styles.choiceDetail}>{p.detail}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {problem === "not_as_described" && (
        <div className={styles.details}>
          <Field label="What was wrong?">
            <Select value={attr} onChange={(e) => pickDetail(e.target.value)}>
              <option value="">Choose a detail…</option>
              {detailKeys.map((k) => (
                <option key={k} value={k}>{attributeLabel(k)}</option>
              ))}
            </Select>
          </Field>
          {attr && (
            <div className={styles.pair}>
              <Field label="What you expected" hint={`The listing said ${ordered[attr] ?? "nothing"} at purchase.`}>
                <Input value={expected} onChange={(e) => setExpected(e.target.value)} placeholder={`e.g. ${ordered[attr] ?? ""}`} autoComplete="off" />
              </Field>
              <Field label="What you received" hint={delivered?.[attr] ? "Filled in from the delivery record." : undefined}>
                <Input value={received} onChange={(e) => setReceived(e.target.value)} autoComplete="off" />
              </Field>
            </div>
          )}
        </div>
      )}

      {problem === "agent_wrong" && (
        <div className={styles.details}>
          <Field label="What did you want instead?" hint="Optional. Culpa replays the agent's decision either way.">
            <Input value={wanted} onChange={(e) => setWanted(e.target.value)} placeholder="e.g. size US 9" autoComplete="off" />
          </Field>
        </div>
      )}

      {problem === "not_received" && delivered && (
        <p className={styles.notice}>A delivery is on record for this order. Culpa will weigh the claim against it.</p>
      )}

      {problem && (
        <Field label={problem === "other" ? "Describe the problem" : "Anything else? (optional)"}>
          <TextArea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} rows={2} autoComplete="off" />
        </Field>
      )}

      {claim && (
        <div className={styles.preview}>
          <p className={styles.previewLabel}>Message to PayPal</p>
          <blockquote className={styles.previewText}>{claim}</blockquote>
          <p className={styles.previewMeta}>Filed as {chosen?.reason.replaceAll("_", " ").toLowerCase()}</p>
        </div>
      )}

      <div className={styles.actions}>
        <Button onClick={() => submit.run()} loading={submit.pending || openedCase !== null} disabled={!ready}>
          {openedCase ? "Opening the case…" : submit.pending ? "Opening dispute…" : "Open dispute"}
        </Button>
        {!ready && <span className={styles.wait}>{problem ? "Fill in the details above." : "Choose what went wrong."}</span>}
      </div>
      {submit.error && <p className="error">{submit.error}</p>}
    </section>
  );
}
