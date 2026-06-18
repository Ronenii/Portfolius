import { useEffect, useRef, useState } from "react";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Cubic ease-out — fast start, gentle settle. Mirrors the brand's
 * `--ease-standard` curve closely enough for JS-driven value tweens.
 * Input is clamped to [0, 1].
 */
export function easeOutCubic(t: number): number {
  const clamped = Math.min(1, Math.max(0, t));
  return 1 - Math.pow(1 - clamped, 3);
}

type CountUpOptions = {
  /** Animation duration in ms. Defaults to 320 (brand `--dur-slow`). */
  durationMs?: number;
};

/**
 * Animates a numeric value toward `target`. On first mount it counts up from
 * zero; on later target changes it tweens from the value currently shown, so an
 * interrupted animation continues smoothly. Honors `prefers-reduced-motion` by
 * snapping straight to the target with no animation.
 */
export function useCountUp(
  target: number,
  { durationMs = 320 }: CountUpOptions = {}
): number {
  const reducedMotion = prefersReducedMotion();
  const [value, setValue] = useState(() => (reducedMotion ? target : 0));
  const valueRef = useRef(value);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (prefersReducedMotion() || !Number.isFinite(target)) {
      valueRef.current = target;
      setValue(target);
      return;
    }

    const from = valueRef.current;
    if (from === target) {
      return;
    }

    let startTime: number | null = null;

    const tick = (now: number) => {
      if (startTime === null) {
        startTime = now;
      }
      const progress = durationMs <= 0 ? 1 : (now - startTime) / durationMs;

      if (progress >= 1) {
        valueRef.current = target;
        setValue(target);
        frameRef.current = null;
        return;
      }

      const next = from + (target - from) * easeOutCubic(progress);
      valueRef.current = next;
      setValue(next);
      frameRef.current = requestAnimationFrame(tick);
    };

    frameRef.current = requestAnimationFrame(tick);

    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [target, durationMs]);

  return value;
}
