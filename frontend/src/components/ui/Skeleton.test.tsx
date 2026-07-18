import { render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("renders a skeleton placeholder", () => {
    const { container } = render(<Skeleton />);

    expect(container.querySelector(".skeleton")).toBeInTheDocument();
  });

  it("is decorative and hidden from assistive tech", () => {
    const { container } = render(<Skeleton />);

    expect(container.querySelector(".skeleton")).toHaveAttribute(
      "aria-hidden",
      "true"
    );
  });

  it("coerces a numeric width/height to px and a string dimension verbatim", () => {
    const { container } = render(<Skeleton width={120} height="1.5rem" />);

    const el = container.querySelector(".skeleton") as HTMLElement;
    expect(el.style.width).toBe("120px");
    expect(el.style.height).toBe("1.5rem");
  });

  it("omits a dimension from style when its prop is undefined", () => {
    const { container } = render(<Skeleton width={120} />);

    const el = container.querySelector(".skeleton") as HTMLElement;
    expect(el.style.width).toBe("120px");
    expect(el.style.height).toBe("");
  });

  it("adds skeleton--circle when circle is set", () => {
    const { container } = render(<Skeleton circle />);

    expect(container.querySelector(".skeleton")).toHaveClass(
      "skeleton--circle"
    );
  });

  it("appends a passed className after the base class", () => {
    const { container } = render(<Skeleton className="foo" />);

    expect(container.querySelector(".skeleton")).toHaveClass("skeleton", "foo");
  });

  describe("reduced motion", () => {
    const originalMatchMedia = window.matchMedia;

    afterEach(() => {
      window.matchMedia = originalMatchMedia;
    });

    it("adds skeleton--static when the user prefers reduced motion", () => {
      window.matchMedia = ((query: string) => ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => false,
      })) as typeof window.matchMedia;

      const { container } = render(<Skeleton />);

      expect(container.querySelector(".skeleton")).toHaveClass(
        "skeleton--static"
      );
    });

    it("does not add skeleton--static when the user does not prefer reduced motion", () => {
      window.matchMedia = ((query: string) => ({
        matches: !query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => false,
      })) as typeof window.matchMedia;

      const { container } = render(<Skeleton />);

      expect(container.querySelector(".skeleton")).not.toHaveClass(
        "skeleton--static"
      );
    });
  });
});
