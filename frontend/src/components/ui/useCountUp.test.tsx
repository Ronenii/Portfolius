import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { easeOutCubic, useCountUp } from "./useCountUp";

describe("easeOutCubic", () => {
  it("maps the endpoints to 0 and 1", () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
  });

  it("eases out (past the midpoint by t=0.5)", () => {
    // 1 - (1 - 0.5)^3 = 0.875
    expect(easeOutCubic(0.5)).toBeCloseTo(0.875, 5);
  });

  it("is monotonically increasing across the range", () => {
    let previous = -Infinity;
    for (let step = 0; step <= 10; step += 1) {
      const current = easeOutCubic(step / 10);
      expect(current).toBeGreaterThanOrEqual(previous);
      previous = current;
    }
  });

  it("clamps inputs outside [0, 1]", () => {
    expect(easeOutCubic(-1)).toBe(0);
    expect(easeOutCubic(2)).toBe(1);
  });
});

describe("useCountUp", () => {
  // The test environment mocks matchMedia to report reduced motion, so the hook
  // should snap straight to the target with no animation frames.
  it("returns the target immediately under reduced motion", () => {
    const { result } = renderHook(() => useCountUp(1250));
    expect(result.current).toBe(1250);
  });

  it("tracks a changing target under reduced motion", () => {
    const { result, rerender } = renderHook(({ target }) => useCountUp(target), {
      initialProps: { target: 100 },
    });
    expect(result.current).toBe(100);

    rerender({ target: 500 });
    expect(result.current).toBe(500);
  });
});
