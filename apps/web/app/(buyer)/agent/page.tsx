"use client";

import { useState } from "react";
import { agentApi, type ShopInput } from "@/api/agent";
import { AgentResult } from "@/components/agent/AgentResult/AgentResult";
import { MandateForm } from "@/components/agent/MandateForm/MandateForm";
import { MandatePanel, type MandateStatus } from "@/components/agent/MandatePanel/MandatePanel";
import { Loader } from "@/components/ui/Loader/Loader";
import { BUYER_ID_KEY, DEVICE_ID_KEY } from "@/constants/config";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { useLocalId } from "@/hooks/useLocalId";
import type { ShopResult } from "@/types";
import styles from "./page.module.css";

export default function AgentPage() {
  const [buyerId] = useLocalId(BUYER_ID_KEY, "buyer");
  const [deviceId] = useLocalId(DEVICE_ID_KEY, "device");
  const [draft, setDraft] = useState<ShopInput | null>(null);
  // What was actually signed: the panel shows this, not later edits, once a mandate is signed.
  const [signed, setSigned] = useState<ShopInput | null>(null);
  const [result, setResult] = useState<ShopResult | null>(null);
  const shop = useAsyncAction(async (input: ShopInput) => {
    setResult(null);
    setSigned(input);
    try {
      setResult(await agentApi.shop(input));
    } catch (e) {
      setSigned(null);
      throw e;
    }
  });

  const status: MandateStatus = shop.pending ? "signing" : result ? "signed" : "draft";
  // The panel appears once there is something to show: an example picked, anything typed, or a signed mandate.
  const drafting = Boolean(
    draft &&
      (draft.instruction.trim() || draft.max_amount || draft.category || Object.keys(draft.required_attributes).length),
  );
  const showPanel = drafting || Boolean(signed) || shop.pending;

  return (
    <main className={`page ${styles.page}`}>
      <header className={styles.intro}>
        <h1 className={styles.title}>Buyer agent</h1>
        <p className={styles.lead}>
          Describe what you want and set the limits. The agent picks one item, and nothing is charged until you approve
          the cart on PayPal.
        </p>
      </header>

      <div className={styles.layout}>
        <section className={styles.compose} aria-label="Write the mandate">
          <MandateForm buyerId={buyerId} deviceId={deviceId} pending={shop.pending} onSubmit={(i) => shop.run(i)}
                       onDraftChange={setDraft} />
          {shop.error && <p className={`error ${styles.error}`}>{shop.error}</p>}
        </section>

        {showPanel && (
          <div className={styles.side}>
            <MandatePanel mandate={signed ?? draft} status={status}>
              {result ? (
                <AgentResult result={result} />
              ) : shop.pending ? (
                <Loader label="The agent is comparing products against your limits…" />
              ) : (
                <p className={styles.waiting}>
                  Once you sign, the agent&apos;s pick appears here with its reasoning and a PayPal approval button.
                </p>
              )}
            </MandatePanel>
          </div>
        )}
      </div>
    </main>
  );
}
