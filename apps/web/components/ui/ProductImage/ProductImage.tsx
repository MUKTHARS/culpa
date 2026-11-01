"use client";

import { useState } from "react";
import { cx } from "@/lib/utils";
import styles from "./ProductImage.module.css";

interface Props {
  src: string | null | undefined;
  alt: string;
  size?: "sm" | "md" | "lg";
}

/** Product thumbnail. Falls back to a neutral placeholder when there is no image or it fails to load. */
export function ProductImage({ src, alt, size = "md" }: Props) {
  const [failed, setFailed] = useState(false);
  const show = Boolean(src) && !failed;
  return (
    <span className={cx(styles.frame, styles[size])}>
      {show ? (
        // Static SVGs from public/: next/image adds nothing here and would need dangerouslyAllowSVG.
        <img src={src!} alt={alt} className={styles.img} loading="lazy" onError={() => setFailed(true)} />
      ) : (
        <span className={styles.placeholder} aria-label={alt} role="img" />
      )}
    </span>
  );
}
