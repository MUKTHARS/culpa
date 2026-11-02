import type { StoreFacet } from "@/types";

const ATTRIBUTE_ORDER = ["size", "color", "material", "model", "capacity"];
const ATTRIBUTE_LABEL: Record<string, string> = { color: "Colour" };

/** "shoes/running" -> "Shoes › Running". */
export function categoryLabel(path: string | null | undefined): string {
  if (!path) return "Any category";
  return path
    .split("/")
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" › ");
}

export function attributeLabel(key: string): string {
  return ATTRIBUTE_LABEL[key] ?? key.charAt(0).toUpperCase() + key.slice(1);
}

/** Attribute keys in shop order: size, colour, material, model, then anything else alphabetically. */
export function orderedAttributes(facet: StoreFacet): string[] {
  const rank = (k: string) => (ATTRIBUTE_ORDER.includes(k) ? ATTRIBUTE_ORDER.indexOf(k) : ATTRIBUTE_ORDER.length);
  return Object.keys(facet.attributes).sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

/** Same normalisation as the API's keywords: lower case, words only, a plural "s" dropped. */
function words(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
    .map((w) => (w.length > 3 && w.endsWith("s") ? w.slice(0, -1) : w));
}

/**
 * The category a request is about ("wireless earphones" -> "electronics/audio"), or "" when unclear.
 * The best-matching subcategory wins; when several tie, their shared group is used ("shoes").
 */
export function detectCategory(instruction: string, facets: StoreFacet[]): string {
  const asked = new Set(words(instruction));
  if (!asked.size) return "";
  const score = (f: StoreFacet) => f.keywords.filter((k) => asked.has(k)).length;
  const subs = facets.filter((f) => f.parent !== null).map((f) => ({ f, s: score(f) }));
  const best = Math.max(0, ...subs.map((x) => x.s));
  if (best === 0) return "";
  const top = subs.filter((x) => x.s === best).map((x) => x.f);
  if (top.length === 1) return top[0].value;
  const parents = new Set(top.map((f) => f.parent));
  return parents.size === 1 ? (top[0].parent ?? "") : "";
}
