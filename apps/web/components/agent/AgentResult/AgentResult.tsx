import { Badge } from "@/components/ui/Badge/Badge";
import { ProductImage } from "@/components/ui/ProductImage/ProductImage";
import { attrs, money } from "@/lib/format";
import type { SearchResult, ShopResult } from "@/types";
import styles from "./AgentResult.module.css";

interface Props {
  result: ShopResult;
  /** A product the buyer picked from the search results instead of the agent's pick, or null. */
  selected?: SearchResult | null;
  onBackToPick?: () => void;
  /** Creates the PayPal order for the buyer's selection and goes to PayPal. */
  onCheckout?: () => void;
  checkingOut?: boolean;
  checkoutError?: string | null;
}

export function AgentResult({ result, selected, onBackToPick, onCheckout, checkingOut, checkoutError }: Props) {
  const product = selected ?? result.product;
  const ownChoice = Boolean(selected);

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h3 className={styles.heading}>{ownChoice ? "Your choice" : "Agent's pick"}</h3>
        {result.simulated && <Badge tone="warn">Simulated checkout</Badge>}
      </div>

      <div className={styles.product}>
        <ProductImage src={product.image_url} alt={product.title} size="lg" />
        <div className={styles.productText}>
          <p className={styles.title}>{product.title}</p>
          <p className={styles.attrs}>{attrs(product.attributes)}</p>
          <p className={styles.price}>{money(product.price)}</p>
        </div>
      </div>

      {ownChoice ? (
        <div className={styles.why}>
          <p className={styles.whyLabel}>You chose this from the search results</p>
          <p>
            The agent recommended {result.product.title} ({attrs(result.product.attributes)}) for{" "}
            {money(result.product.price)}.{" "}
            <button type="button" className={styles.linkButton} onClick={onBackToPick}>Go back to the agent&apos;s pick</button>
          </p>
        </div>
      ) : (
        <div className={styles.why}>
          <p className={styles.whyLabel}>Why this item</p>
          <p>{result.reasoning}</p>
          <p className={styles.compared}>Compared {result.candidates} products that fit the mandate.</p>
        </div>
      )}

      {ownChoice ? (
        <button type="button" className={styles.paypal} onClick={onCheckout} disabled={checkingOut} aria-busy={checkingOut || undefined}>
          {checkingOut ? "Preparing PayPal checkout…" : result.simulated ? "Approve cart (simulated PayPal)" : "Approve with PayPal"}
        </button>
      ) : result.approve_url ? (
        <a className={styles.paypal} href={result.approve_url}>
          {result.simulated ? "Approve cart (simulated PayPal)" : "Approve with PayPal"}
        </a>
      ) : (
        <p className="error">PayPal didn&apos;t return an approval link. Sign the mandate again to create a new order.</p>
      )}
      {checkoutError && <p className="error">{checkoutError}</p>}
      <p className={styles.note}>
        {ownChoice
          ? "Approving signs an updated mandate for exactly this item, so the evidence shows you chose it. Nothing is charged until you approve on PayPal."
          : "Nothing is charged until you approve. Your approval of this exact cart becomes part of the evidence."}
      </p>

      {!ownChoice && (
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
      )}
    </div>
  );
}
