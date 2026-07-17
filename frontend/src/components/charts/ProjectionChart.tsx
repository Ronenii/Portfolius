import { useState } from "react";

import {
  Area,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ProjectionYearPoint } from "../../features/portfolio/portfolio-api";

// Shared across chart components in this codebase (also duplicated in
// AllocationChart.tsx/AllocationDonut.tsx) - the choice of which three
// entries represent conservative/expected/optimistic is arbitrary and only
// meant to keep the three bands visually distinct.
const chartColors = ["#167c7c", "#4f6f80", "#7a8b5d", "#a56b4f", "#5b6c93", "#8b6f95"];

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

type BandKey = "conservative" | "expected" | "optimistic" | "costBasis";

const BAND_KEYS: BandKey[] = [
  "conservative",
  "expected",
  "optimistic",
  "costBasis",
];

const BAND_LABELS: Record<BandKey, string> = {
  conservative: "Conservative",
  expected: "Expected",
  optimistic: "Optimistic",
  costBasis: "Cost basis",
};

// chartColors[3] is reserved for the target ReferenceLine (below) - band
// colors are looked up explicitly here rather than positionally by index so
// the two can never collide.
const BAND_COLORS: Record<BandKey, string> = {
  conservative: chartColors[0],
  expected: chartColors[1],
  optimistic: chartColors[2],
  costBasis: chartColors[4],
};

type MilestoneRow = { numericExpected: number; year: number };

export function findMilestonePoint<T extends MilestoneRow>(
  chartRows: T[],
  onTrack: boolean | null,
  targetReachedYear: number | null
): T | undefined {
  if (onTrack !== true || targetReachedYear == null) {
    return undefined;
  }
  return chartRows.find((row) => row.year === targetReachedYear);
}

type ProjectionChartProps = {
  currency: string;
  formatValue: (value: string, currency: string) => string;
  onTrack: boolean | null;
  series: ProjectionYearPoint[];
  targetAmount: string | null;
  targetReachedYear: number | null;
};

export function ProjectionChart({
  currency,
  formatValue,
  onTrack,
  series,
  targetAmount,
  targetReachedYear,
}: ProjectionChartProps) {
  const chartRows = series.map((point) => ({
    ...point,
    numericConservative: Number(point.conservative),
    numericExpected: Number(point.expected),
    numericOptimistic: Number(point.optimistic),
    numericCostBasis: Number(point.cost_basis),
  }));

  const numericTarget = targetAmount == null ? null : Number(targetAmount);
  const animationsEnabled = !prefersReducedMotion();
  const milestonePoint = findMilestonePoint(
    chartRows,
    onTrack,
    targetReachedYear
  );

  const [hiddenBands, setHiddenBands] = useState<Set<BandKey>>(
    () => new Set()
  );
  const visibleCount = BAND_KEYS.length - hiddenBands.size;

  function toggleBand(band: BandKey) {
    setHiddenBands((current) => {
      if (!current.has(band) && visibleCount <= 1) {
        return current;
      }
      const next = new Set(current);
      if (next.has(band)) {
        next.delete(band);
      } else {
        next.add(band);
      }
      return next;
    });
  }

  return (
    <div className="projection-chart-wrap">
      <div className="projection-chart" role="img" aria-label="Goal projection chart">
        <ResponsiveContainer width="100%" height={260}>
        <ComposedChart
          data={chartRows}
          margin={{ bottom: 4, left: 8, right: 12, top: 4 }}
        >
          <XAxis dataKey="year" axisLine={false} tickLine={false} />
          <YAxis type="number" hide domain={["dataMin", "auto"]} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) {
                return null;
              }

              const row = payload[0]?.payload as ProjectionYearPoint | undefined;
              if (!row) {
                return null;
              }

              return (
                <div className="projection-tooltip">
                  <strong>Year {row.year}</strong>
                  <dl>
                    <div>
                      <dt>Conservative</dt>
                      <dd>{formatValue(row.conservative, currency)}</dd>
                    </div>
                    <div>
                      <dt>Expected</dt>
                      <dd>{formatValue(row.expected, currency)}</dd>
                    </div>
                    <div>
                      <dt>Optimistic</dt>
                      <dd>{formatValue(row.optimistic, currency)}</dd>
                    </div>
                    <div>
                      <dt>Cost basis</dt>
                      <dd>{formatValue(row.cost_basis, currency)}</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Area
            dataKey="numericConservative"
            fill={chartColors[0]}
            fillOpacity={0.15}
            stroke={chartColors[0]}
            type="monotone"
            hide={hiddenBands.has("conservative")}
            isAnimationActive={animationsEnabled}
            animationDuration={800}
            animationEasing="ease-out"
          />
          <Area
            dataKey="numericExpected"
            fill={chartColors[1]}
            fillOpacity={0.15}
            stroke={chartColors[1]}
            type="monotone"
            hide={hiddenBands.has("expected")}
            isAnimationActive={animationsEnabled}
            animationDuration={800}
            animationEasing="ease-out"
          />
          <Area
            dataKey="numericOptimistic"
            fill={chartColors[2]}
            fillOpacity={0.15}
            stroke={chartColors[2]}
            type="monotone"
            hide={hiddenBands.has("optimistic")}
            isAnimationActive={animationsEnabled}
            animationDuration={800}
            animationEasing="ease-out"
          />
          <Line
            dataKey="numericCostBasis"
            dot={false}
            hide={hiddenBands.has("costBasis")}
            stroke={BAND_COLORS.costBasis}
            strokeDasharray="2 2"
            strokeWidth={2}
            type="monotone"
            isAnimationActive={animationsEnabled}
            animationDuration={800}
            animationEasing="ease-out"
          />
          {numericTarget != null && (
            <ReferenceLine
              y={numericTarget}
              stroke={chartColors[3]}
              strokeDasharray="4 4"
              label={{ value: "Target", position: "insideTopRight", fill: chartColors[3] }}
            />
          )}
          {milestonePoint && (
            <ReferenceDot
              className="projection-milestone-dot"
              fill={chartColors[0]}
              label={{
                fill: chartColors[0],
                fontSize: 12,
                position: "top",
                value: "Target reached",
              }}
              r={6}
              stroke="#fff"
              strokeWidth={2}
              x={milestonePoint.year}
              y={milestonePoint.numericExpected}
            />
          )}
        </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div
        className="projection-band-toggles"
        role="group"
        aria-label="Toggle projection bands"
      >
        {BAND_KEYS.map((band) => {
          const isVisible = !hiddenBands.has(band);
          return (
            <button
              key={band}
              type="button"
              className={
                isVisible
                  ? "projection-band-toggle"
                  : "projection-band-toggle projection-band-toggle--muted"
              }
              aria-pressed={isVisible}
              disabled={isVisible && visibleCount === 1}
              onClick={() => toggleBand(band)}
            >
              <span
                aria-hidden="true"
                className="projection-band-swatch"
                style={{ backgroundColor: BAND_COLORS[band] }}
              />
              {BAND_LABELS[band]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
