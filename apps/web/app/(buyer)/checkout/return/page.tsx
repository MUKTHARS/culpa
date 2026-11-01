"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { ordersApi } from "@/api/orders";
import { Card } from "@/components/ui/Card/Card";
import { Loader } from "@/components/ui/Loader/Loader";
import { ROUTES } from "@/constants/routes";
import { attrs, money, shortHash } from "@/lib/format";
import type { Order } from "@/types";

function Capture() {
  const token = useSearchParams()?.get("token") ?? "";
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true; // capture once, even under React strict-mode double effects
    ordersApi.capture(token).then(setOrder).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [token]);

  if (!token) return <p className="error">Missing order token in the return URL.</p>;
  if (error) return <p className="error">{error}</p>;
  if (!order) return <Loader label="Capturing payment and fingerprinting evidence…" />;

  return (
    <div className="stack">
      <p>
        Paid <strong>{money(order.amount, order.currency)}</strong> for <strong>{order.product_title}</strong> (
        {attrs(order.snapshot_attributes)}).
      </p>
      <dl className="stack" style={{ gap: 4 }}>
        <dt className="muted">Evidence root (Merkle)</dt>
        <dd className="mono" style={{ margin: 0, wordBreak: "break-all" }}>{order.evidence_root}</dd>
        <dt className="muted">Mandate · trace · snapshot hashes</dt>
        <dd className="mono" style={{ margin: 0 }}>
          {shortHash(order.evidence?.mandate_hash)} · {shortHash(order.evidence?.trace_hash)} ·{" "}
          {shortHash(order.evidence?.snapshot_hash)}
        </dd>
        <dt className="muted">PayPal capture</dt>
        <dd className="mono" style={{ margin: 0 }}>{order.capture_id}</dd>
      </dl>
      <div className="row">
        <Link href={ROUTES.merchant}>Go to the merchant to ship it</Link>
        <Link href={ROUTES.orders}>Open a dispute on it</Link>
      </div>
    </div>
  );
}

export default function CheckoutReturnPage() {
  return (
    <main className="page" style={{ maxWidth: 760 }}>
      <Card title="Checkout complete">
        <Suspense fallback={<Loader />}>
          <Capture />
        </Suspense>
      </Card>
    </main>
  );
}
