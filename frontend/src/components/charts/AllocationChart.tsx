import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AllocationRow } from "../../features/portfolio/portfolio-api";
import {
  allocationQuantityLabel,
  allocationQuantityValue,
} from "../../features/portfolio/allocation-display";

const chartColors = ["#167c7c", "#4f6f80", "#7a8b5d", "#a56b4f", "#5b6c93", "#8b6f95"];

type AllocationChartProps = {
  formatPercent: (value: string) => string;
  formatValue: (value: string, currency: string) => string;
  onSelectRow?: (row: AllocationRow) => void;
  rows: AllocationRow[];
  title: string;
};

export function AllocationChart({
  formatPercent,
  formatValue,
  onSelectRow,
  rows,
  title,
}: AllocationChartProps) {
  const chartRows = rows.slice(0, 8).map((row, index) => ({
    ...row,
    color: chartColors[index % chartColors.length],
    numericMarketValue: Number(row.market_value),
  }));

  return (
    <div className="allocation-chart" role="img" aria-label={`${title} chart`}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={chartRows}
          layout="vertical"
          margin={{ bottom: 4, left: 8, right: 12, top: 4 }}
        >
          <XAxis type="number" hide />
          <YAxis
            axisLine={false}
            dataKey="label"
            tickLine={false}
            type="category"
            width={110}
          />
          <Tooltip
            cursor={{ fill: "rgba(22, 124, 124, 0.08)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) {
                return null;
              }

              const row = payload[0]?.payload as AllocationRow | undefined;
              if (!row) {
                return null;
              }

              return (
                <div className="allocation-tooltip">
                  <strong>{row.label}</strong>
                  <span>{title}</span>
                  <dl>
                    <div>
                      <dt>Market value</dt>
                      <dd>{formatValue(row.market_value, row.currency)}</dd>
                    </div>
                    <div>
                      <dt>Portfolio share</dt>
                      <dd>{formatPercent(row.percent)}</dd>
                    </div>
                    <div>
                      <dt>{allocationQuantityLabel(row)}</dt>
                      <dd>{allocationQuantityValue(row)}</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Bar dataKey="numericMarketValue" radius={[0, 4, 4, 0]}>
            {chartRows.map((row) => (
              <Cell
                cursor={onSelectRow ? "pointer" : "default"}
                key={`${row.dimension}-${row.label}-${row.currency}`}
                fill={row.color}
                onClick={() => onSelectRow?.(row)}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
