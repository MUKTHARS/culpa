"use client";

import { OrdersTable } from "@/components/orders/OrdersTable/OrdersTable";
import { ProductEditor } from "@/components/merchant/ProductEditor/ProductEditor";
import { Badge } from "@/components/ui/Badge/Badge";
import { Card } from "@/components/ui/Card/Card";
import { EmptyState } from "@/components/ui/EmptyState/EmptyState";
import { Loader } from "@/components/ui/Loader/Loader";
import { ProductImage } from "@/components/ui/ProductImage/ProductImage";
import { useOrders } from "@/hooks/useOrders";
import { useProducts } from "@/hooks/useProducts";
import { money } from "@/lib/format";

export default function MerchantPage() {
  const products = useProducts();
  const orders = useOrders();

  return (
    <main className="page stack">
      <div>
        <h1>Merchant</h1>
        <p className="muted">Demo store. Every listing edit creates a new version; Culpa keeps all of them.</p>
      </div>

      <Card title="Orders to fulfil" subtitle="Shipping sends whatever the listing says right now.">
        {orders.error ? (
          <p className="error">{orders.error.message}</p>
        ) : !orders.data ? (
          <Loader />
        ) : orders.data.length === 0 ? (
          <EmptyState title="No orders yet">Use the buyer agent to place one.</EmptyState>
        ) : (
          <OrdersTable orders={orders.data} onChange={() => orders.mutate()} />
        )}
      </Card>

      <div className="grid-2">
        {products.error && <p className="error">{products.error.message}</p>}
        {!products.data && !products.error && <Loader />}
        {products.data?.map((p) => (
          <Card key={`${p.id}-${p.version}`} title={p.title}
                subtitle={<>{p.category} · {money(p.price, p.currency)}</>}
                actions={<Badge tone="neutral">v{p.version}</Badge>}>
            <div className="stack">
              <ProductImage src={p.image_url} alt={p.title} size="lg" />
              <ProductEditor product={p} onSaved={() => products.mutate()} />
            </div>
          </Card>
        ))}
      </div>
    </main>
  );
}
