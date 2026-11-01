import { Badge } from "@/components/ui/Badge/Badge";
import { ProductImage } from "@/components/ui/ProductImage/ProductImage";
import { attrs, money } from "@/lib/format";
import type { ShopResult } from "@/types";
import styles from "./AgentResult.module.css";

export function AgentResult({ result }: { result: ShopResult }) {
  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h3 className={styles.heading}>Agent&apos;s pick</h3>
        {result.simulated && <Badge tone="warn">Simulated checkout</Badge>}
      </div>

      <div className={styles.product}>
        <ProductImage src={result.product.image_url} alt={result.product.title} size="lg" />
        <div className={styles.productText}>
          <p className={styles.title}>{result.product.title}</p>
          <p className={styles.attrs}>{attrs(result.product.attributes)}</p>
          <p className={styles.price}>{money(result.product.price)}</p>
        </div>
      </div>

      <div className={styles.why}>
        <p className={styles.whyLabel}>Why this item</p>
        <p>{result.reasoning}</p>
        <p className={styles.compared}>Compared {result.candidates} products that fit the mandate.</p>
      </div>

      {result.approve_url ? (
        <a className={styles.paypal} href={result.approve_url}>
          {result.simulated ? "Approve cart (simulated PayPal)" : "Approve with PayPal"}
        </a>
      ) : (
        <p className="error">PayPal didn&apos;t return an approval link. Sign the mandate again to create a new order.</p>
      )}
      <p className={styles.note}>
        Nothing is charged until you approve. Your approval of this exact cart becomes part of the evidence.
      </p>

      <details className={styles.details}>
        <summary>Evidence details</summary>
        <dl className={styles.facts}>
          <dt>Mandate</dt>
          <dd className="mono">{result.mandate.id}</dd>
          <dt>Mandate hash</dt>
          <dd className="mono">{result.mandate.hash}</dd>
          <dt>PayPal order</dt>
          <dd className="mono">{result.paypal_order_id}</dd>
          <dt>Agent policy</dt>
          <dd>{result.policy}</dd>
        </dl>
      </details>
    </div>
  );
}
