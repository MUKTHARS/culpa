"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge/Badge";
import { Button } from "@/components/ui/Button/Button";
import { ProductImage } from "@/components/ui/ProductImage/ProductImage";
import { attributeLabel, categoryLabel } from "@/lib/facets";
import { money } from "@/lib/format";
import { cx } from "@/lib/utils";
import type { SearchResult, SearchStats } from "@/types";
import styles from "./SearchResults.module.css";

const FIT_LABEL = { match: "matches", ambiguous: "unclear", mismatch: "doesn't match", missing: "not listed" } as const;

type Sort = "best" | "price_asc" | "price_desc";
const SORTS: { value: Sort; label: string }[] = [
  { value: "best", label: "Best match" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
];
const ATTRIBUTE_ORDER = ["size", "color", "material", "model", "capacity"];

interface Props {
  results: SearchResult[];
  stats?: SearchStats;
  /** The product shown on the right: the agent's pick unless the buyer selected another. */
  selectedId: string;
  /** Shows this product on the right instantly; its PayPal order is created only at checkout. */
  onSelect: (result: SearchResult) => void;
}

/** The products the agent compared, in its own ranking, with why each one matched. */
export function SearchResults({ results, stats, selectedId, onSelect }: Props) {
  const [sort, setSort] = useState<Sort>("best");
  const [picked, setPicked] = useState<Record<string, string[]>>({});

  // Filters exist only where the results actually differ (a size filter for tees, not for one-size items).
  const facets = useMemo(() => {
    const values: Record<string, Set<string>> = {};
    for (const r of results) for (const [k, v] of Object.entries(r.attributes)) (values[k] ??= new Set()).add(v);
    const rankOf = (k: string) => (ATTRIBUTE_ORDER.includes(k) ? ATTRIBUTE_ORDER.indexOf(k) : 99);
    return Object.entries(values)
      .filter(([, v]) => v.size > 1)
      .sort(([a], [b]) => rankOf(a) - rankOf(b) || a.localeCompare(b))
      .map(([k, v]) => ({ key: k, values: [...v].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })) }));
  }, [results]);

  const shown = useMemo(() => {
    const matches = results
      .map((r, i) => ({ r, rank: i + 1 }))
      .filter(({ r }) => Object.entries(picked).every(([k, vs]) => !vs.length || vs.includes(r.attributes[k])));
    if (sort === "price_asc") matches.sort((a, b) => Number(a.r.price) - Number(b.r.price) || a.rank - b.rank);
    if (sort === "price_desc") matches.sort((a, b) => Number(b.r.price) - Number(a.r.price) || a.rank - b.rank);
    return matches;
  }, [results, picked, sort]);

  const toggle = (key: string, value: string) =>
    setPicked((p) => {
      const cur = p[key] ?? [];
      return { ...p, [key]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value] };
    });
  const filtering = Object.values(picked).some((vs) => vs.length > 0);
  const excluded = stats
    ? [
        stats.other_category && `${stats.other_category} in other categories`,
        stats.over_budget && `${stats.over_budget} over your cap`,
        stats.attribute_mismatch && `${stats.attribute_mismatch} not matching your requirements`,
      ].filter(Boolean)
    : [];

  return (
    <section className={styles.panel} aria-labelledby="search-results">
      <header className={styles.head}>
        <h2 id="search-results" className={styles.title}>Search results</h2>
        {stats && (
          <p className={styles.stats}>
            {stats.matching} of {stats.searched} products fit your mandate
            {excluded.length > 0 && ` (left out: ${excluded.join(", ")})`}.
          </p>
        )}
      </header>

      <div className={styles.toolbar}>
        <label className={styles.sort}>
          <span>Sort by</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className={styles.sortSelect}>
            {SORTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        <p className={styles.count}>
          Showing {shown.length} of {results.length}
          {filtering && (
            <button type="button" className={styles.clear} onClick={() => setPicked({})}>Clear filters</button>
          )}
        </p>
      </div>

      {facets.length > 0 && (
        <div className={styles.facets}>
          {facets.map((f) => (
            <div key={f.key} className={styles.facet} role="group" aria-label={attributeLabel(f.key)}>
              <span className={styles.facetLabel}>{attributeLabel(f.key)}</span>
              {f.values.map((v) => {
                const on = picked[f.key]?.includes(v) ?? false;
                return (
                  <button key={v} type="button" aria-pressed={on} onClick={() => toggle(f.key, v)}
                          className={cx(styles.chip, on && styles.chipOn)}>
                    {v}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {shown.length === 0 && <p className={styles.empty}>No product matches these filters.</p>}
      <ol className={styles.list}>
        {shown.map(({ r, rank }) => (
          <li key={r.id} className={cx(styles.item, r.id === selectedId && styles.chosen)}
              aria-current={r.id === selectedId || undefined}>
            <span className={styles.rank} aria-label={`Best-match rank ${rank}`}>{rank}</span>
            <ProductImage src={r.image_url} alt={r.title} size="md" />
            <div className={styles.body}>
              <div className={styles.titleRow}>
                <p className={styles.name}>{r.title}</p>
                {r.chosen && <Badge tone="accent">Agent&apos;s pick</Badge>}
                {r.id === selectedId && !r.chosen && <Badge tone="good">Your choice</Badge>}
              </div>
              <p className={styles.category}>{categoryLabel(r.category)}</p>
              <ul className={styles.attrs}>
                {Object.entries(r.attributes).map(([k, v]) => {
                  const status = r.fit[k];
                  return (
                    <li key={k} className={cx(styles.attr, status && styles[status])}
                        title={status ? `Your requirement ${FIT_LABEL[status]}` : undefined}>
                      {attributeLabel(k)} <strong>{v}</strong>
                    </li>
                  );
                })}
              </ul>
              {r.matched.length > 0 && <p className={styles.matched}>Matches “{r.matched.join(" ")}”</p>}
            </div>
            <div className={styles.side}>
              <p className={styles.price}>{money(r.price)}</p>
              {r.id === selectedId ? (
                <span className={styles.selected}>Selected</span>
              ) : (
                <Button size="sm" variant="secondary" onClick={() => onSelect(r)}>
                  {r.chosen ? "Back to agent's pick" : "Select"}
                </Button>
              )}
            </div>
          </li>
        ))}
      </ol>
      <p className={styles.footnote}>
        Selecting a product shows it on the right. Approving it signs a mandate for exactly that item, so the
        evidence always shows what you chose. Highlighted attributes show how each product meets your requirements.
      </p>
    </section>
  );
}
