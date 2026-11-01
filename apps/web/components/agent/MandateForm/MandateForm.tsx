"use client";

import { useState } from "react";
import type { ShopInput } from "@/api/agent";
import { Button } from "@/components/ui/Button/Button";
import { Field, Input, Select, TextArea } from "@/components/ui/Field/Field";
import { parseAttributes } from "@/lib/utils";
import styles from "./MandateForm.module.css";

const EXAMPLES = [
  { label: "Ambiguous size", instruction: "running shoes size 9 under $120", category: "shoes", attrs: "size: 9", max: "120" },
  { label: "Exact size", instruction: "running shoes size US 9", category: "shoes", attrs: "size: US 9", max: "120" },
  { label: "Leather jacket", instruction: "brown leather jacket size M", category: "apparel/jackets", attrs: "size: M\nmaterial: Leather", max: "200" },
];

interface Props {
  buyerId: string;
  deviceId: string;
  pending: boolean;
  onSubmit: (input: ShopInput) => void;
}

export function MandateForm({ buyerId, deviceId, pending, onSubmit }: Props) {
  const [instruction, setInstruction] = useState(EXAMPLES[0].instruction);
  const [category, setCategory] = useState(EXAMPLES[0].category);
  const [attrText, setAttrText] = useState(EXAMPLES[0].attrs);
  const [max, setMax] = useState(EXAMPLES[0].max);
  // The preset whose values are in the fields right now (-1 when none match), however they got there.
  const active = EXAMPLES.findIndex(
    (ex) => ex.instruction === instruction && ex.category === category && ex.attrs === attrText && ex.max === max,
  );

  return (
    <form
      className={styles.form}
      // These values become a signed mandate: the browser must not fill them in (it would also clear the preset highlight).
      autoComplete="off"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          buyer_id: buyerId,
          device_id: deviceId,
          instruction,
          category: category || undefined,
          max_amount: max || undefined,
          required_attributes: parseAttributes(attrText),
        });
      }}
    >
      <div className={styles.examples}>
        {EXAMPLES.map((ex, i) => (
          <Button key={ex.label} type="button" size="sm" variant={active === i ? "primary" : "secondary"}
                  aria-pressed={active === i}
                  onClick={() => { setInstruction(ex.instruction); setCategory(ex.category); setAttrText(ex.attrs); setMax(ex.max); }}>
            {ex.label}
          </Button>
        ))}
      </div>
      <Field label="What should the agent buy?">
        <Input value={instruction} onChange={(e) => setInstruction(e.target.value)} required minLength={3} maxLength={500} />
      </Field>
      <div className={styles.grid}>
        <Field label="Spending cap (USD)" hint="Hard limit, signed into the mandate">
          <Input value={max} onChange={(e) => setMax(e.target.value)} inputMode="decimal" pattern="^\d+(\.\d{1,2})?$" />
        </Field>
        <Field label="Category">
          <Select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Any</option>
            <option value="shoes">Shoes</option>
            <option value="apparel">Apparel</option>
            <option value="apparel/jackets">Jackets</option>
            <option value="electronics">Electronics</option>
          </Select>
        </Field>
      </div>
      <Field label="Required attributes" hint="One per line, e.g. size: 9. The agent must satisfy these.">
        <TextArea value={attrText} onChange={(e) => setAttrText(e.target.value)} />
      </Field>
      <div className="row">
        <Button type="submit" loading={pending} disabled={!buyerId}>
          Sign mandate and let the agent shop
        </Button>
        <span className="muted">Buyer id: {buyerId || "…"}</span>
      </div>
    </form>
  );
}
