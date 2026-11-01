"use client";

import { OrdersTable } from "@/components/orders/OrdersTable/OrdersTable";
import { Card } from "@/components/ui/Card/Card";
import { EmptyState } from "@/components/ui/EmptyState/EmptyState";
import { Loader } from "@/components/ui/Loader/Loader";
import { useOrders } from "@/hooks/useOrders";

export default function OrdersPage() {
  const { data, error, mutate } = useOrders();
  return (
    <>
      <div>
        <h1>Orders</h1>
        <p className="muted">Agent purchases with their evidence fingerprint. Open a simulated dispute on any captured order.</p>
      </div>
      <Card>
        {error ? (
          <p className="error">{error.message}</p>
        ) : !data ? (
          <Loader />
        ) : data.length === 0 ? (
          <EmptyState title="No orders yet">Place one with the buyer agent.</EmptyState>
        ) : (
          <OrdersTable orders={data} onChange={() => mutate()} />
        )}
      </Card>
    </>
  );
}
