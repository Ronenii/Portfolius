import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { ProjectionYearPoint } from "../../features/portfolio/portfolio-api";
import { findMilestonePoint, ProjectionChart } from "./ProjectionChart";

const series: ProjectionYearPoint[] = [
  { year: 0, conservative: "10000", expected: "10000", optimistic: "10000" },
  { year: 1, conservative: "10800", expected: "11000", optimistic: "11200" },
];

function formatValue(value: string, currency: string) {
  return `${currency} ${value}`;
}

function renderChart() {
  return render(
    <ProjectionChart
      currency="USD"
      formatValue={formatValue}
      series={series}
      targetAmount={null}
      onTrack={null}
      targetReachedYear={null}
    />
  );
}

describe("ProjectionChart", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a toggle chip for each band, all pressed by default", () => {
    renderChart();

    expect(
      screen.getByRole("button", { name: "Conservative" })
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Expected" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(
      screen.getByRole("button", { name: "Optimistic" })
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("toggles a band off when its chip is clicked", async () => {
    renderChart();

    await userEvent.click(screen.getByRole("button", { name: "Conservative" }));

    expect(
      screen.getByRole("button", { name: "Conservative" })
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("refuses to hide the last visible band", async () => {
    renderChart();

    await userEvent.click(screen.getByRole("button", { name: "Conservative" }));
    await userEvent.click(screen.getByRole("button", { name: "Expected" }));

    expect(screen.getByRole("button", { name: "Optimistic" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Optimistic" }));
    expect(
      screen.getByRole("button", { name: "Optimistic" })
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("puts the band toggles outside the role=img chart element", () => {
    renderChart();

    const chart = screen.getByRole("img", { name: "Goal projection chart" });
    const toggles = screen.getByRole("group", {
      name: "Toggle projection bands",
    });

    expect(chart.contains(toggles)).toBe(false);
  });

  it("renders without crashing when motion is allowed (matchMedia reports no reduced-motion preference)", () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    })) as typeof window.matchMedia;

    renderChart();

    expect(
      screen.getByRole("img", { name: "Goal projection chart" })
    ).toBeInTheDocument();

    window.matchMedia = originalMatchMedia;
  });
});

describe("findMilestonePoint", () => {
  const rows = [
    { year: 0, numericExpected: 10000 },
    { year: 1, numericExpected: 11000 },
    { year: 2, numericExpected: 12100 },
  ];

  it("returns the matching row when on track and the year is present", () => {
    expect(findMilestonePoint(rows, true, 1)).toEqual({
      year: 1,
      numericExpected: 11000,
    });
  });

  it("returns undefined when not on track", () => {
    expect(findMilestonePoint(rows, false, 1)).toBeUndefined();
  });

  it("returns undefined when on track but the target year isn't in range", () => {
    expect(findMilestonePoint(rows, true, 10)).toBeUndefined();
  });

  it("returns undefined when targetReachedYear is null", () => {
    expect(findMilestonePoint(rows, true, null)).toBeUndefined();
  });
});
