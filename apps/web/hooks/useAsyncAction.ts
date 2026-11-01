"use client";

import { useCallback, useState } from "react";

/** Run an async action with pending/error state. Prevents double-submits while pending. */
export function useAsyncAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      if (pending) return undefined;
      setPending(true);
      setError(null);
      try {
        return await fn(...args);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        return undefined;
      } finally {
        setPending(false);
      }
    },
    [fn, pending],
  );

  return { run, pending, error, setError };
}
