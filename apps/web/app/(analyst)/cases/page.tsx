"use client";

import { CaseGrid } from "@/components/cases/CaseGrid/CaseGrid";
import { Card } from "@/components/ui/Card/Card";
import { EmptyState } from "@/components/ui/EmptyState/EmptyState";
import { Loader } from "@/components/ui/Loader/Loader";
import { useCases } from "@/hooks/useCases";

export default function CasesPage() {
  const { data, error } = useCases();
  const open = data?.filter((c) => c.status === "awaiting_approval" || c.status === "needs_review").length ?? 0;

  return (
    <>
      <div>
        <h1>Dispute cases</h1>
        <p className="muted">
          {data ? `${data.length} cases · ${open} waiting for an analyst` : "Agent-purchase disputes from PayPal webhooks and the simulator."}
        </p>
      </div>
      <Card flush>
        {error ? (
          <p className="error" style={{ margin: 16 }}>{error.message}</p>
        ) : !data ? (
          <Loader />
        ) : data.length === 0 ? (
          <div style={{ padding: 16 }}>
            <EmptyState title="No disputes yet">
              Buy something with the buyer agent, then open a dispute from Orders, or send a PayPal sandbox dispute.
            </EmptyState>
          </div>
        ) : (
          <CaseGrid rows={data} />
        )}
      </Card>
    </>
  );
}
