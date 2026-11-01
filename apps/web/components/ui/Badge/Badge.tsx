import type { ReactNode } from "react";
import { cx } from "@/lib/utils";
import styles from "./Badge.module.css";

export type Tone = "neutral" | "info" | "good" | "warn" | "bad" | "accent";

export function Badge({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={cx(styles.badge, styles[tone])} title={title}>
      {children}
    </span>
  );
}
