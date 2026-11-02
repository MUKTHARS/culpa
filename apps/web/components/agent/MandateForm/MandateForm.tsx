"use client";

import { useEffect, useMemo, useState } from "react";
import type { ShopInput } from "@/api/agent";
import { Button } from "@/components/ui/Button/Button";
import { Field, Select } from "@/components/ui/Field/Field";
import { useStoreFacets } from "@/hooks/useProducts";
import { attributeLabel, categoryLabel, detectCategory, orderedAttributes } from "@/lib/facets";
import { cx } from "@/lib/utils";
import styles from "./MandateForm.module.css";

interface Example {
  label: string;
  instruction: string;
  category: string;
  attrs: Record<string, string>;
  max: string;
}

// "Ambiguous size" deliberately asks for size "9" without a system (UK, US, EU): the agent replay demo needs it.
const EXAMPLES: Example[] = [
  { label: "Ambiguous size", instruction: "running shoes size 9 under $120", category: "shoes", attrs: { size: "9" }, max: "120" },
  { label: "Exact size", instruction: "running shoes size US 9", category: "shoes", attrs: { size: "US 9" }, max: "120" },
  { label: "Leather jacket", instruction: "brown leather jacket size M", category: "apparel/jackets", attrs: { size: "M", material: "Leather" }, max: "200" },
];

const sameAttrs = (a: Record<string, string>, b: Record<string, string>) =>
  JSON.stringify(Object.entries(a).sort()) === JSON.stringify(Object.entries(b).sort());

interface Props {
  buyerId: string;
  deviceId: string;
  pending: boolean;
  onSubmit: (input: ShopInput) => void;
  /** Called with the current values on every change, so the page can preview the mandate. */
  onDraftChange?: (input: ShopInput) => void;
}

export function MandateForm({ buyerId, deviceId, pending, onSubmit, onDraftChange }: Props) {
  const { data: facets } = useStoreFacets();
  // Starts empty: the buyer writes their own mandate or picks an example.
  const [instruction, setInstruction] = useState("");
  // null = follow the category detected from the instruction; a string = the buyer (or an example) chose it.
  const [chosenCategory, setChosenCategory] = useState<string | null>(null);
  const [attrs, setAttrs] = useState<Record<string, string>>({});
  const [max, setMax] = useState("");

  const detected = useMemo(() => detectCategory(instruction, facets ?? []), [instruction, facets]);
  const category = chosenCategory ?? detected;
  const facet = facets?.find((f) => f.value === category);
  const filterKeys = facet ? orderedAttributes(facet) : [];

  // Only filters that exist for the category count, and "Any" is not a requirement.
  const required: Record<string, string> = {};
  for (const [k, v] of Object.entries(attrs)) if (v && (!facets || filterKeys.includes(k))) required[k] = v;

  const active = EXAMPLES.findIndex(
    (ex) => ex.instruction === instruction && ex.category === category && sameAttrs(ex.attrs, required) && ex.max === max,
  );

  const draft: ShopInput = {
    buyer_id: buyerId,
    device_id: deviceId,
    instruction,
    category: category || undefined,
    max_amount: max || undefined,
    required_attributes: required,
  };
  const draftKey = JSON.stringify(draft);
  useEffect(() => {
    onDraftChange?.(JSON.parse(draftKey) as ShopInput);
  }, [onDraftChange, draftKey]);

  return (
    <form
      className={styles.form}
      // These values become a signed mandate: the browser must not fill them in (it would also clear the preset highlight).
      autoComplete="off"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(draft);
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
          placeholder="Describe the item and your budget, like “wireless earphones under $150”"
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
              onClick={() => { setInstruction(ex.instruction); setChosenCategory(ex.category); setAttrs(ex.attrs); setMax(ex.max); }}
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
          <Field
            label="Category"
            hint={chosenCategory === null && detected ? "Picked from your request. Change it if it's wrong." : undefined}
          >
            <Select value={category} onChange={(e) => setChosenCategory(e.target.value)}>
              <option value="">Any category</option>
              {(facets ?? [])
                .filter((f) => f.parent === null)
                .map((group) => (
                  <optgroup key={group.value} label={group.label}>
                    <option value={group.value}>All {group.label.toLowerCase()}</option>
                    {facets!
                      .filter((f) => f.parent === group.value)
                      .map((f) => (
                        <option key={f.value} value={f.value}>{f.label}</option>
                      ))}
                  </optgroup>
                ))}
              {/* An example's category stays selectable before the catalog has loaded. */}
              {category && !facet && <option value={category}>{categoryLabel(category)}</option>}
            </Select>
          </Field>
        </div>

        {facet && filterKeys.length > 0 ? (
          <div className={styles.filters}>
            <p className={styles.filtersNote}>
              Filters for {categoryLabel(category).toLowerCase()}. Leave one on “Any” if it doesn&apos;t matter.
            </p>
            <div className={styles.grid}>
              {filterKeys.map((key) => {
                const values = facet.attributes[key];
                const current = attrs[key] ?? "";
                return (
                  <Field key={key} label={attributeLabel(key)}>
                    <Select value={current} onChange={(e) => setAttrs({ ...attrs, [key]: e.target.value })}>
                      <option value="">Any</option>
                      {values.map((v) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                      {/* A value given in other words (an example's "9"), kept so it isn't silently dropped. */}
                      {current && !values.includes(current) && <option value={current}>{current} (as written)</option>}
                    </Select>
                  </Field>
                );
              })}
            </div>
          </div>
        ) : (
          <p className={styles.filtersNote}>
            {category ? "This category has no filters." : "Pick a category, or describe the item above, to filter by size, colour and more."}
          </p>
        )}
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
