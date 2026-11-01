"use client";

import { useEffect, useState } from "react";
import type { ShopInput } from "@/api/agent";
import { Button } from "@/components/ui/Button/Button";
import { Field, Select, TextArea } from "@/components/ui/Field/Field";
import { cx, parseAttributes } from "@/lib/utils";
import styles from "./MandateForm.module.css";

const EXAMPLES = [
  { label: "Ambiguous size", instruction: "running shoes size 9 under $120", category: "shoes", attrs: "size: 9", max: "120" },
  { label: "Exact size", instruction: "running shoes size US 9", category: "shoes", attrs: "size: US 9", max: "120" },
  { label: "Leather jacket", instruction: "brown leather jacket size M", category: "apparel/jackets", attrs: "size: M\nmaterial: Leather", max: "200" },
];

export const CATEGORIES = [
  { value: "", label: "Any category" },
  { value: "shoes", label: "Shoes" },
  { value: "apparel", label: "Apparel" },
  { value: "apparel/jackets", label: "Jackets" },
  { value: "electronics", label: "Electronics" },
];

interface Props {
  buyerId: string;
  deviceId: string;
  pending: boolean;
  onSubmit: (input: ShopInput) => void;
  /** Called with the current values on every change, so the page can preview the mandate. */
  onDraftChange?: (input: ShopInput) => void;
}

export function MandateForm({ buyerId, deviceId, pending, onSubmit, onDraftChange }: Props) {
  // Starts empty: the buyer writes their own mandate or picks an example.
  const [instruction, setInstruction] = useState("");
  const [category, setCategory] = useState("");
  const [attrText, setAttrText] = useState("");
  const [max, setMax] = useState("");
  // The preset whose values are in the fields right now (-1 when none match), however they got there.
  const active = EXAMPLES.findIndex(
    (ex) => ex.instruction === instruction && ex.category === category && ex.attrs === attrText && ex.max === max,
  );

  useEffect(() => {
    onDraftChange?.({
      buyer_id: buyerId,
      device_id: deviceId,
      instruction,
      category: category || undefined,
      max_amount: max || undefined,
      required_attributes: parseAttributes(attrText),
    });
  }, [onDraftChange, buyerId, deviceId, instruction, category, max, attrText]);

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
      <label className={styles.task}>
        <span className={styles.taskLabel}>What should the agent buy?</span>
        <textarea
          className={styles.taskInput}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          rows={2}
          required
          minLength={3}
          maxLength={500}
          placeholder="Describe the item, the size or colour you need, and your budget"
        />
      </label>

      <div className={styles.examples}>
        <span className={styles.examplesLabel} id="mandate-examples">Examples</span>
        <div className={styles.segmented} role="group" aria-labelledby="mandate-examples">
          {EXAMPLES.map((ex, i) => (
            <button
              key={ex.label}
              type="button"
              className={cx(styles.segment, active === i && styles.segmentActive)}
              aria-pressed={active === i}
              onClick={() => { setInstruction(ex.instruction); setCategory(ex.category); setAttrText(ex.attrs); setMax(ex.max); }}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <fieldset className={styles.limits}>
        <legend className={styles.limitsTitle}>Limits the agent must follow</legend>
        <div className={styles.grid}>
          <label className={styles.capField}>
            <span className={styles.fieldLabel}>Spending cap</span>
            <span className={styles.money}>
              <span className={styles.currency} aria-hidden>$</span>
              <input
                className={styles.moneyInput}
                value={max}
                onChange={(e) => setMax(e.target.value)}
                inputMode="decimal"
                pattern="^\d+(\.\d{1,2})?$"
                placeholder="No cap"
                aria-describedby="cap-hint"
              />
              <span className={styles.code} aria-hidden>USD</span>
            </span>
            <span className={styles.hint} id="cap-hint">The agent can never spend more than this.</span>
          </label>
          <Field label="Category">
            <Select value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Must match" hint="One per line, like size: 9. The agent may only buy an item with these exact values.">
          <TextArea value={attrText} onChange={(e) => setAttrText(e.target.value)} rows={3} placeholder="size: 9" />
        </Field>
      </fieldset>

      <div className={styles.submit}>
        <Button type="submit" loading={pending} disabled={!buyerId}>
          Sign mandate and shop
        </Button>
        <p className={styles.submitNote}>Signing doesn&apos;t charge you. You approve the cart on PayPal next.</p>
      </div>
    </form>
  );
}
