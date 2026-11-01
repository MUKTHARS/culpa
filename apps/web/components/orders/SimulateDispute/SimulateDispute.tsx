"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { casesApi } from "@/api/cases";
import { Button } from "@/components/ui/Button/Button";
import { Card } from "@/components/ui/Card/Card";
import { Field, Select, TextArea } from "@/components/ui/Field/Field";
import { ROUTES } from "@/constants/routes";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import styles from "./SimulateDispute.module.css";

const PRESETS = [
  { label: "Wrong size (ambiguity)", reason: "ITEM_NOT_AS_DESCRIBED", text: "I wanted US 9, they sent UK 9." },
  { label: "Not as described", reason: "ITEM_NOT_AS_DESCRIBED", text: "The listing said mesh, I received synthetic." },
  { label: "Never arrived", reason: "ITEM_NOT_RECEIVED", text: "It never arrived." },
  { label: "Blame the agent", reason: "ITEM_NOT_AS_DESCRIBED", text: "My AI agent bought the wrong thing, refund me." },
];

export function SimulateDispute({ orderId, onDone }: { orderId: string; onDone: () => void }) {
  const router = useRouter();
  const [reason, setReason] = useState(PRESETS[0].reason);
  const [text, setText] = useState(PRESETS[0].text);
  // The preset whose values are in the fields right now (-1 when none match).
  const active = PRESETS.findIndex((p) => p.reason === reason && p.text === text);
  const submit = useAsyncAction(async () => {
    const c = await casesApi.simulate(orderId, reason, text);
    onDone();
    router.push(ROUTES.caseDetail(c.id));
  });

  return (
    <Card title="Open a dispute (simulator)"
          subtitle="Same path as a PayPal CUSTOMER.DISPUTE.CREATED webhook, for demos without a sandbox dispute.">
      <div className={styles.form}>
        <div className={styles.presets}>
          {PRESETS.map((p, i) => (
            <Button key={p.label} size="sm" variant={active === i ? "primary" : "secondary"} aria-pressed={active === i}
                    onClick={() => { setReason(p.reason); setText(p.text); }}>
              {p.label}
            </Button>
          ))}
        </div>
        <Field label="Reason">
          <Select value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="ITEM_NOT_AS_DESCRIBED">Item not as described</option>
            <option value="ITEM_NOT_RECEIVED">Item not received</option>
            <option value="UNAUTHORISED">Unauthorised</option>
            <option value="OTHER">Other</option>
          </Select>
        </Field>
        <Field label="Buyer's claim">
          <TextArea value={text} onChange={(e) => setText(e.target.value)} maxLength={4000} autoComplete="off" />
        </Field>
        <div className="row">
          <Button onClick={() => submit.run()} loading={submit.pending}>
            Open dispute
          </Button>
        </div>
        {submit.error && <p className="error">{submit.error}</p>}
      </div>
    </Card>
  );
}
