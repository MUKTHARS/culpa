"use client";

import { useState } from "react";
import { agentApi, type ShopInput } from "@/api/agent";
import { AgentResult } from "@/components/agent/AgentResult/AgentResult";
import { MandateForm } from "@/components/agent/MandateForm/MandateForm";
import { Card } from "@/components/ui/Card/Card";
import { BUYER_ID_KEY, DEVICE_ID_KEY } from "@/constants/config";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { useLocalId } from "@/hooks/useLocalId";
import type { ShopResult } from "@/types";

export default function AgentPage() {
  const [buyerId] = useLocalId(BUYER_ID_KEY, "buyer");
  const [deviceId] = useLocalId(DEVICE_ID_KEY, "device");
  const [result, setResult] = useState<ShopResult | null>(null);
  const shop = useAsyncAction(async (input: ShopInput) => {
    setResult(null);
    setResult(await agentApi.shop(input));
  });

  return (
    <main className="page stack">
      <div>
        <h1>Buyer agent</h1>
        <p className="muted">
          Tell the agent what to buy. Your instruction and limits become a signed mandate that Culpa uses as evidence.
        </p>
      </div>
      <div className="grid-2">
        <Card title="Mandate">
          <MandateForm buyerId={buyerId} deviceId={deviceId} pending={shop.pending} onSubmit={(i) => shop.run(i)} />
          {shop.error && <p className="error" style={{ marginTop: 12 }}>{shop.error}</p>}
        </Card>
        <Card title="Agent's choice">
          {result ? <AgentResult result={result} /> : <p className="muted">The agent's pick will appear here.</p>}
        </Card>
      </div>
    </main>
  );
}
