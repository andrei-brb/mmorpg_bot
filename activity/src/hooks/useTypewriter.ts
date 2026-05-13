import { useCallback, useEffect, useMemo, useRef, useState } from "react";

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const fn = () => setReduced(mq.matches);
    fn();
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);
  return reduced;
}

export type TypewriterControls = {
  /** Visible slice of the current page */
  visibleText: string;
  pageIndex: number;
  pageCount: number;
  /** Current page has finished typing (or reduced motion). */
  pageComplete: boolean;
  /** Every page has been typed through (or skipped). */
  allComplete: boolean;
  /** First click completes the current page; next click advances (if any). */
  skipOrAdvance: () => void;
};

/**
 * Multi-page typewriter: click advances or completes the active page.
 * Respects `prefers-reduced-motion` (full text per page immediately).
 */
export function useTypewriter(
  pages: string[],
  resetKey: string,
  options?: { cps?: number },
): TypewriterControls {
  const cps = options?.cps ?? 32;
  const reducedMotion = usePrefersReducedMotion();
  const normalized = useMemo(
    () => pages.map((p) => p.trim()).filter((p) => p.length > 0),
    [pages],
  );

  const [pageIndex, setPageIndex] = useState(0);
  const [count, setCount] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countRef = useRef(0);

  useEffect(() => {
    countRef.current = count;
  }, [count]);

  useEffect(() => {
    setPageIndex(0);
    setCount(0);
  }, [resetKey]);

  const full = normalized[pageIndex] ?? "";
  const pageComplete = !full || count >= full.length;
  const allComplete = normalized.length === 0 || (pageIndex >= normalized.length - 1 && pageComplete);
  const visibleText = full.slice(0, count);

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (!full) return;
    if (reducedMotion) {
      setCount(full.length);
      return;
    }
    setCount(0);
    const ms = Math.max(12, Math.floor(1000 / cps));
    const id = setInterval(() => {
      setCount((c) => {
        const n = c + 1;
        return Math.min(n, full.length);
      });
    }, ms);
    intervalRef.current = id;
    return () => {
      clearInterval(id);
      intervalRef.current = null;
    };
  }, [full, reducedMotion, cps, pageIndex, resetKey]);

  const skipOrAdvance = useCallback(() => {
    if (!full && normalized.length === 0) return;
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (countRef.current < full.length) {
      setCount(full.length);
      return;
    }
    if (pageIndex < normalized.length - 1) {
      setPageIndex((i) => i + 1);
    }
  }, [full, normalized.length, pageIndex]);

  return {
    visibleText,
    pageIndex,
    pageCount: normalized.length,
    pageComplete,
    allComplete,
    skipOrAdvance,
  };
}
