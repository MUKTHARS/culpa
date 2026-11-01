import { Badge } from "@/components/ui/Badge/Badge";
import { ProductImage } from "@/components/ui/ProductImage/ProductImage";
import { attrs, money, shortHash } from "@/lib/format";
import type { ShopResult } from "@/types";
import styles from "./AgentResult.module.css";

export function AgentResult({ result }: { result: ShopResult }) {
  return (
    <div className={styles.wrap}>
      <div className="row">
        <Badge tone="accent">Agent policy: {result.policy}</Badge>
        {result.simulated ? <Badge tone="warn">Simulated PayPal</Badge> : <Badge tone="good">PayPal sandbox order</Badge>}
        <span className="muted">{result.candidates} candidates considered</span>
      </div>
      <div className={styles.product}>
        <ProductImage src={result.product.image_url} alt={result.product.title} size="lg" />
        <div>
          <p className={styles.title}>{result.product.title}</p>
          <p>{attrs(result.product.attributes)}</p>
          <p className={styles.price}>{money(result.product.price)}</p>
        </div>
      </div>
      <p>
        <span className="muted">Agent reasoning: </span>
        {result.reasoning}
      </p>
      <p className="muted mono">
        Mandate {result.mandate.id} · hash {shortHash(result.mandate.hash, 16)} · PayPal order {result.paypal_order_id}
      </p>
      {result.approve_url ? (
        <a className={styles.approve} href={result.approve_url}>
          {result.simulated ? "Approve the cart (simulated checkout)" : "Approve the cart with PayPal"}
        </a>
      ) : (
        <p className="error">PayPal returned no approval link.</p>
      )}
      <p className="muted">
        You approve the exact cart. That approval is part of the evidence Culpa fingerprints at capture.
      </p>
    </div>
  );
}
