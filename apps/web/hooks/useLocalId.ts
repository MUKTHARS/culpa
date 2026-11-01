"use client";

import { useEffect, useState } from "react";

/** A stable random id kept in localStorage (buyer id, device id). Empty string until mounted. */
export function useLocalId(key: string, prefix: string): [string, (v: string) => void] {
  const [value, setValue] = useState("");

  useEffect(() => {
    let v = "";
    try {
      v = window.localStorage.getItem(key) ?? "";
      if (!v) {
        v = `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
        window.localStorage.setItem(key, v);
      }
    } catch {
      v = `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
    }
    setValue(v);
  }, [key, prefix]);

  const update = (v: string) => {
    setValue(v);
    try {
      window.localStorage.setItem(key, v);
    } catch {
      /* storage unavailable */
    }
  };
  return [value, update];
}
