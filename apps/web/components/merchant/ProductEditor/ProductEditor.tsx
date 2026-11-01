"use client";

import { useState } from "react";
import { storeApi } from "@/api/store";
import { Button } from "@/components/ui/Button/Button";
import { Field, Input, TextArea } from "@/components/ui/Field/Field";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { useProductHistory } from "@/hooks/useProducts";
import { attrs, when } from "@/lib/format";
import { formatAttributes, parseAttributes } from "@/lib/utils";
import type { Product } from "@/types";
import styles from "./ProductEditor.module.css";

export function ProductEditor({ product, onSaved }: { product: Product; onSaved: () => void }) {
  const [price, setPrice] = useState(product.price);
  const [attrText, setAttrText] = useState(formatAttributes(product.attributes));
  // History is fetched only when opened: the store has dozens of products and this keeps page load to one request.
  const [showHistory, setShowHistory] = useState(false);
  const history = useProductHistory(showHistory ? product.id : null);
  const save = useAsyncAction(async () => {
    await storeApi.update(product.id, { price, attributes: parseAttributes(attrText) });
    await history.mutate();
    onSaved();
  });

  return (
    <div className={styles.wrap}>
      <div className={styles.grid}>
        <Field label="Price (USD)">
          <Input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" />
        </Field>
        <Field label="Attributes" hint="Editing after a purchase changes what ships, which is the merchant-fault demo.">
          <TextArea value={attrText} onChange={(e) => setAttrText(e.target.value)} rows={4} />
        </Field>
      </div>
      <div className="row">
        <Button size="sm" onClick={() => save.run()} loading={save.pending}>
          Save as v{product.version + 1}
        </Button>
        {save.error && <span className="error">{save.error}</span>}
      </div>
      <details onToggle={(e) => setShowHistory((e.currentTarget as HTMLDetailsElement).open)}>
        <summary className="muted">Listing history ({product.version} version{product.version === 1 ? "" : "s"})</summary>
        {!history.data ? (
          <p className="muted">{history.error ? history.error.message : "Loading…"}</p>
        ) : (
          <ul className={styles.history}>
            {[...history.data].reverse().map((v) => (
              <li key={v.version}>
                <strong>v{v.version}</strong> · {when(v.captured_at)} · {attrs(v.attributes)} · ${v.price}
              </li>
            ))}
          </ul>
        )}
      </details>
    </div>
  );
}
