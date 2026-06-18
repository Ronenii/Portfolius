import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollIntoView — stub it so components that call
// bottomRef.current?.scrollIntoView() don't throw during tests.
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => undefined;
}

// jsdom does not implement matchMedia. Provide a stub that reports reduced
// motion so motion-driven UI (count-up numerics, the trend loader) renders its
// static final state synchronously, keeping assertions deterministic.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string) =>
    ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}
