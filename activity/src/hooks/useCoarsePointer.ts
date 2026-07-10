import { useEffect, useState } from "react";

/**
 * True when the primary pointer is coarse (touchscreens — phones/tablets).
 * Use it to drop hover-only interactions on touch, where synthesized mouse
 * events cause flicker and "stuck" hover states.
 */
export function useCoarsePointer(): boolean {
  const [coarse, setCoarse] = useState(
    () =>
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(pointer: coarse)").matches,
  );

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(pointer: coarse)");
    const onChange = () => setCoarse(mq.matches);
    onChange();
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, []);

  return coarse;
}
