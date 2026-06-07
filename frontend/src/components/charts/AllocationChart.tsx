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

const chartColors = ["#167c7c", "#4f6f80", "#7a8b5d", "#a56b4f", "#5b6c93", "#8b6f95"];

type AllocationChartProps = {
  formatPercent: (value: string) => string;
  formatValue: (value: string, currency: string) => string;
  rows: AllocationRow[];
  title: string;
};

export function AllocationChart({
  formatPercent,
  formatValue,
  rows,
  title,
}: AllocationChartProps) {
  const chartRows = rows.slice(0, 8).map((row, index) => ({
    ...row,
    color: chartColors[index % chartColors.length],
    numericMarketValue: Number(row.market_value),
  }));

  return (
    <div className="allocation-chart" aria-label={`${title} chart`}>
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
            formatter={(_value, _name, props) => {
              const row = props.payload as AllocationRow | undefined;
              return row ? [formatValue(row.market_value, row.currency), "Market value"] : null;
            }}
            labelFormatter={(_label, payload) => {
              const row = payload[0]?.payload as AllocationRow | undefined;
              return row ? `${row.label} - ${formatPercent(row.percent)}` : "";
            }}
          />
          <Bar dataKey="numericMarketValue" radius={[0, 4, 4, 0]}>
            {chartRows.map((row) => (
              <Cell key={`${row.dimension}-${row.label}-${row.currency}`} fill={row.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
