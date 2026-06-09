import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { AllocationRow } from "../../features/portfolio/portfolio-api";

const chartColors = ["#167c7c", "#4f6f80", "#7a8b5d", "#a56b4f", "#5b6c93", "#8b6f95"];

type AllocationDonutProps = {
  formatPercent: (value: string) => string;
  formatValue: (value: string, currency: string) => string;
  onSelectRow?: (row: AllocationRow) => void;
  rows: AllocationRow[];
  title: string;
};

export function AllocationDonut({
  formatPercent,
  formatValue,
  onSelectRow,
  rows,
  title,
}: AllocationDonutProps) {
  const chartRows = rows.slice(0, 8).map((row, index) => ({
    ...row,
    color: chartColors[index % chartColors.length],
    numericMarketValue: Number(row.market_value),
  }));

  return (
    <div className="allocation-chart allocation-donut" role="img" aria-label={`${title} donut chart`}>
      <ResponsiveContainer width="100%" height={260}>
        <PieChart margin={{ bottom: 4, left: 4, right: 4, top: 4 }}>
          <Pie
            cx="50%"
            cy="50%"
            data={chartRows}
            dataKey="numericMarketValue"
            innerRadius="56%"
            outerRadius="82%"
            nameKey="label"
            paddingAngle={2}
          >
            {chartRows.map((row) => (
              <Cell
                cursor={onSelectRow ? "pointer" : "default"}
                key={`${row.dimension}-${row.label}-${row.currency}`}
                fill={row.color}
                onClick={() => onSelectRow?.(row)}
              />
            ))}
          </Pie>
          <Tooltip
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
                      <dt>Holdings</dt>
                      <dd>{row.holding_count}</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
