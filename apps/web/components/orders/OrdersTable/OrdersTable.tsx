"use client";

import { Fragment, useCallback, useState } from "react";
import Link from "next/link";
import { ordersApi } from "@/api/orders";
import { ROUTES } from "@/constants/routes";
import { Badge } from "@/components/ui/Badge/Badge";
import { Button } from "@/components/ui/Button/Button";
import { SimulateDispute } from "@/components/orders/SimulateDispute/SimulateDispute";
import { ProductImage } from "@/components/ui/ProductImage/ProductImage";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { attrs, money, shortHash, when } from "@/lib/format";
import type { Order } from "@/types";
import styles from "./OrdersTable.module.css";

interface Props {
  orders: Order[];
  onChange: () => void;
  /** Show the dispute simulator. Off for the merchant, who fulfils orders but never disputes them. */
  allowDispute?: boolean;
}

export function OrdersTable({ orders, onChange, allowDispute = true }: Props) {
  const [disputing, setDisputing] = useState<string | null>(null);
  // Stable ref callback: scrolls once when the form opens, not on every refresh of the list.
  const scrollIntoView = useCallback((el: HTMLDivElement | null) => {
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, []);
  const ship = useAsyncAction(async (id: string) => {
    await ordersApi.ship(id);
    onChange();
  });

  return (
    <div className="stack">
      {ship.error && <p className="error">{ship.error}</p>}
      <div className="scroll-x">
        <table className="table">
          <thead>
            <tr>
              <th>Created</th>
              <th>Item at purchase</th>
              <th>Delivered</th>
              <th>Amount</th>
              <th>Evidence root</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <Fragment key={o.id}>
                <tr>
                  <td>{when(o.created_at)}</td>
                  <td>
                    <div className={styles.item}>
                      <ProductImage src={o.product_image_url} alt={o.product_title} size="sm" />
                      <div>
                        <strong>{o.product_title}</strong>
                        <div className="muted">{attrs(o.snapshot_attributes)}</div>
                      </div>
                    </div>
                  </td>
                  <td>{o.delivered ? attrs(o.delivered_attributes) : <span className="muted">Not shipped</span>}</td>
                  <td>{money(o.amount, o.currency)}</td>
                  <td className="mono">{shortHash(o.evidence_root)}</td>
                  <td>
                    <div className={styles.badges}>
                      <Badge tone={o.status === "captured" ? "good" : "neutral"}>{o.status}</Badge>
                      {o.simulated && <Badge tone="warn">simulated</Badge>}
                    </div>
                  </td>
                  <td>
                    <div className={styles.actions}>
                      {o.status === "captured" && !o.shipped_at && (
                        <Button size="sm" variant="secondary" onClick={() => ship.run(o.id)} loading={ship.pending}>
                          Ship
                        </Button>
                      )}
                      {allowDispute && o.case_id && <Link href={ROUTES.caseDetail(o.case_id)}>View case</Link>}
                      {allowDispute && o.status === "captured" && !o.case_id && (
                        <Button size="sm" onClick={() => setDisputing(disputing === o.id ? null : o.id)}
                                aria-expanded={disputing === o.id}>
                          {disputing === o.id ? "Close" : "Open dispute"}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
                {disputing === o.id && (
                  // The form opens right under its order, so it is visible however long the table is.
                  <tr className={styles.disputeRow}>
                    <td colSpan={7}>
                      <div ref={scrollIntoView}>
                        <SimulateDispute order={o} onDone={onChange} />
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
