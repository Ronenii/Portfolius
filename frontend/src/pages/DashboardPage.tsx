import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CircleAlert,
  CircleCheck,
  Clock3,
  RefreshCw,
} from "lucide-react";
import { useMemo, useState, type KeyboardEvent } from "react";

import { AllocationChart } from "../components/charts/AllocationChart";
import { AllocationDonut } from "../components/charts/AllocationDonut";
import { AnimatedNumber } from "../components/ui/AnimatedNumber";
import Button from "../components/ui/Button";
import { TrendLoader } from "../components/ui/TrendLoader";
import { useAuth } from "../features/auth/AuthContext";
import { CompositionPopover } from "../features/portfolio/CompositionPopover";
import {
  getPortfolioBreakdowns,
  getPortfolioSnapshot,
  refreshPrices,
  type AllocationRow,
  type PortfolioBreakdowns,
  type PortfolioSnapshot,
} from "../features/portfolio/portfolio-api";
import SimulationPanel from "../features/portfolio/SimulationPanel";
import { ApiError, type BackendHealth, fetchBackendHealth } from "../lib/api";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const prodModeValues = new Set(["1", "true", "yes", "on"]);
const breakdownDimensions = [
  { key: "asset_class", label: "Asset class" },
  { key: "sector", label: "Sector" },
  { key: "country", label: "Country" },
  { key: "region", label: "Region" },
  { key: "currency", label: "Currency" },
  { key: "instrument", label: "Instrument" },
] as const;
const chartTypeOptions = [
  { key: "bar", label: "Bar" },
  { key: "donut", label: "Donut" },
  { key: "table", label: "Table" },
] as const;
const allocationChartTypeKey = "portfolius:allocation-chart-type";

type BreakdownDimension = (typeof breakdownDimensions)[number]["key"];
type AllocationChartType = (typeof chartTypeOptions)[number]["key"];

function isAllocationChartType(value: string | null): value is AllocationChartType {
  return chartTypeOptions.some((option) => option.key === value);
}

function readAllocationChartType(): AllocationChartType {
  try {
    const storedType = localStorage.getItem(allocationChartTypeKey);
    return isAllocationChartType(storedType) ? storedType : "bar";
  } catch {
    return "bar";
  }
}

function writeAllocationChartType(chartType: AllocationChartType) {
  try {
    localStorage.setItem(allocationChartTypeKey, chartType);
  } catch {
    // Client-side presentation preference only; ignore unavailable storage.
  }
}

function isProdMode() {
  return prodModeValues.has(
    String(import.meta.env.VITE_PROD_MODE ?? "").trim().toLowerCase()
  );
}

function statusCopy(health: BackendHealth | undefined, isLoading: boolean) {
  if (isLoading) {
    return "Checking backend";
  }

  return health?.status === "ok" ? "Backend healthy" : "Backend unavailable";
}

function detailCopy(health: BackendHealth | undefined, isLoading: boolean) {
  if (isLoading) {
    return "Waiting for /healthz";
  }

  return health?.status === "ok"
    ? "GET /healthz returned ok"
    : health?.message ?? "Health check did not return a result";
}

function StatusIcon({
  health,
  isLoading,
}: {
  health: BackendHealth | undefined;
  isLoading: boolean;
}) {
  if (isLoading) {
    return <Activity aria-hidden="true" className="health-icon health-icon--loading" />;
  }

  if (health?.status === "ok") {
    return <CircleCheck aria-hidden="true" className="health-icon health-icon--ok" />;
  }

  return <CircleAlert aria-hidden="true" className="health-icon health-icon--error" />;
}

function formatMoney(value: string | null | undefined, currency = "USD") {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("en", {
    currency,
    style: "currency",
  }).format(Number.isFinite(numericValue) ? numericValue : 0);
}

function formatPercent(value: string | null | undefined) {
  const numericValue = Number(value ?? 0);
  return `${new Intl.NumberFormat("en", {
    maximumFractionDigits: 2,
    minimumFractionDigits: Number.isInteger(numericValue) ? 0 : 1,
  }).format(Number.isFinite(numericValue) ? numericValue : 0)}%`;
}

function formatPriceDate(value: string | null | undefined) {
  if (!value) {
    return "Not reported";
  }

  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return "Not reported";
  }

  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

function summaryState(snapshot: PortfolioSnapshot | undefined) {
  if (!snapshot) {
    return null;
  }

  if (snapshot.holdings.length === 0) {
    return {
      detail: "Add holdings to start tracking values and price coverage.",
      title: "No holdings yet",
    };
  }

  if (snapshot.summary.missing_price_holdings > 0) {
    return {
      detail: `${snapshot.summary.missing_price_holdings} holding${
        snapshot.summary.missing_price_holdings === 1 ? "" : "s"
      } need a refreshed daily close before totals are complete.`,
      title: "Prices missing",
    };
  }

  return null;
}

function breakdownRows(
  breakdowns: PortfolioBreakdowns | undefined,
  dimension: BreakdownDimension
): AllocationRow[] {
  return breakdowns?.[dimension] ?? [];
}

function snapshotErrorCopy(error: unknown) {
  if (error instanceof ApiError && error.status === 404) {
    return {
      detail: "Create a profile before the dashboard can calculate portfolio totals.",
      title: "No profile yet",
    };
  }

  return {
    detail: error instanceof Error ? error.message : "Snapshot request failed.",
    title: "Snapshot unavailable",
  };
}

export default function DashboardPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [selectedDimension, setSelectedDimension] = useState<BreakdownDimension>("asset_class");
  const [selectedChartType, setSelectedChartType] = useState<AllocationChartType>(
    readAllocationChartType
  );
  const [hoveredBucket, setHoveredBucket] = useState<AllocationRow | null>(null);
  const [pinnedBucket, setPinnedBucket] = useState<AllocationRow | null>(null);
  // Pinned (click) takes precedence over hovered (mouseenter/focus).
  const selectedBucket = pinnedBucket ?? hoveredBucket;
  const showBackendStatus = !isProdMode();
  const healthQuery = useQuery({
    enabled: showBackendStatus,
    queryKey: ["backend-health", apiUrl],
    queryFn: () => fetchBackendHealth(apiUrl),
  });
  const snapshotQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["portfolio-snapshot", accessToken],
    queryFn: () => getPortfolioSnapshot(accessToken ?? ""),
  });
  const breakdownsQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["portfolio-breakdowns", accessToken],
    queryFn: () => getPortfolioBreakdowns(accessToken ?? ""),
  });
  const refreshMutation = useMutation({
    mutationFn: () => refreshPrices(accessToken ?? ""),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["portfolio-snapshot"] });
      await queryClient.invalidateQueries({ queryKey: ["portfolio-breakdowns"] });
    },
  });

  const checkedAt = useMemo(
    () =>
      new Intl.DateTimeFormat("en", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date()),
    []
  );
  const selectedDimensionLabel =
    breakdownDimensions.find((dimension) => dimension.key === selectedDimension)?.label ??
    "Allocation";
  const baseCurrency = snapshotQuery.data?.summary.base_currency;
  const formatBaseCurrency = (amount: number) =>
    formatMoney(String(amount), baseCurrency);
  const selectedRows = breakdownRows(breakdownsQuery.data, selectedDimension);
  const selectedBucketKey = selectedBucket
    ? `${selectedBucket.dimension}-${selectedBucket.label}-${selectedBucket.currency}`
    : null;

  function selectDimension(dimension: BreakdownDimension) {
    setSelectedDimension(dimension);
    setPinnedBucket(null);
    setHoveredBucket(null);
  }

  // Preview on hover/focus — only takes effect when nothing is pinned.
  function hoverBucket(row: AllocationRow) {
    setHoveredBucket(row);
  }

  // Click pins the composition; clicking the same row again unpins.
  function pinBucket(row: AllocationRow) {
    setPinnedBucket((prev) =>
      prev?.dimension === row.dimension &&
      prev?.label === row.label &&
      prev?.currency === row.currency
        ? null
        : row
    );
    setHoveredBucket(row);
  }

  function closeBucket() {
    setPinnedBucket(null);
    setHoveredBucket(null);
  }

  function handleBucketKeyDown(event: KeyboardEvent<HTMLTableRowElement>, row: AllocationRow) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      pinBucket(row);
      return;
    }

    if (event.key === "Escape") {
      closeBucket();
    }
  }

  function selectChartType(chartType: AllocationChartType) {
    setSelectedChartType(chartType);
    writeAllocationChartType(chartType);
  }

  return (
    <section className="dashboard-page" aria-labelledby="dashboard-title">
      <header className="page-header">
        <div>
          <p className="eyebrow">Portfolio overview</p>
          <h1 id="dashboard-title">Dashboard</h1>
        </div>
        <Button
          disabled={!accessToken}
          icon={RefreshCw}
          loading={refreshMutation.isPending}
          type="button"
          onClick={() => refreshMutation.mutate()}
        >
          {refreshMutation.isPending ? "Refreshing" : "Refresh prices"}
        </Button>
      </header>

      <section className="dashboard-summary" aria-label="Portfolio summary">
        {snapshotQuery.isLoading ? (
          <TrendLoader
            label="Reading portfolio totals and price coverage"
            srLabel="Loading snapshot"
          />
        ) : null}

        {snapshotQuery.error ? (
          <div className="empty-state">
            <strong>{snapshotErrorCopy(snapshotQuery.error).title}</strong>
            <span>{snapshotErrorCopy(snapshotQuery.error).detail}</span>
          </div>
        ) : null}

        {snapshotQuery.data ? (
          <>
            <div className="kpi-grid">
              <article className="kpi-tile kpi-tile--primary">
                <p className="panel-label">Priced value</p>
                <strong>
                  <AnimatedNumber
                    format={formatBaseCurrency}
                    value={Number(snapshotQuery.data.summary.total_market_value)}
                  />
                </strong>
                <span>{snapshotQuery.data.summary.base_currency} priced holdings</span>
              </article>
              <article className="kpi-tile">
                <p className="panel-label">Cost basis</p>
                <strong>
                  <AnimatedNumber
                    format={formatBaseCurrency}
                    value={Number(snapshotQuery.data.summary.total_cost_basis)}
                  />
                </strong>
                <span>Base-currency holdings only</span>
              </article>
              <article className="kpi-tile">
                <p className="panel-label">Unrealized gain</p>
                <strong>
                  <AnimatedNumber
                    format={formatBaseCurrency}
                    value={Number(snapshotQuery.data.summary.total_unrealized_gain)}
                  />
                </strong>
                <span>Based on latest stored close</span>
              </article>
              <article className="kpi-tile">
                <p className="panel-label">Price coverage</p>
                <strong>
                  {snapshotQuery.data.summary.priced_holdings} priced /{" "}
                  {snapshotQuery.data.summary.missing_price_holdings} missing
                </strong>
                <span>
                  Latest price date:{" "}
                  {formatPriceDate(snapshotQuery.data.summary.latest_price_date)}
                </span>
              </article>
            </div>
            {summaryState(snapshotQuery.data) ? (
              <div className="empty-state">
                <strong>{summaryState(snapshotQuery.data)?.title}</strong>
                <span>{summaryState(snapshotQuery.data)?.detail}</span>
              </div>
            ) : null}
          </>
        ) : null}

        {refreshMutation.error ? (
          <p className="form-error" role="alert">
            {refreshMutation.error instanceof Error
              ? refreshMutation.error.message
              : "Refresh failed"}
          </p>
        ) : null}
      </section>

      <section className="allocation-panel" aria-labelledby="allocation-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Exposure</p>
            <h2 id="allocation-title">Allocation breakdown</h2>
          </div>
          {breakdownsQuery.data?.unpriced_holding_count ? (
            <span className="allocation-note">
              {breakdownsQuery.data.unpriced_holding_count} unpriced excluded
            </span>
          ) : null}
        </div>

        <div className="allocation-controls">
          <div className="segmented-control" aria-label="Allocation dimension">
            {breakdownDimensions.map((dimension) => (
              <button
                className={
                  selectedDimension === dimension.key
                    ? "segmented-button segmented-button--active"
                    : "segmented-button"
                }
                key={dimension.key}
                type="button"
                aria-pressed={selectedDimension === dimension.key}
                onClick={() => selectDimension(dimension.key)}
              >
                {dimension.label}
              </button>
            ))}
          </div>
          <div className="segmented-control" aria-label="Allocation chart type">
            {chartTypeOptions.map((chartType) => (
              <button
                className={
                  selectedChartType === chartType.key
                    ? "segmented-button segmented-button--active"
                    : "segmented-button"
                }
                key={chartType.key}
                type="button"
                aria-pressed={selectedChartType === chartType.key}
                onClick={() => selectChartType(chartType.key)}
              >
                {chartType.label}
              </button>
            ))}
          </div>
        </div>

        {breakdownsQuery.isLoading ? (
          <TrendLoader
            label="Reading priced exposure by dimension"
            srLabel="Loading allocations"
          />
        ) : null}

        {breakdownsQuery.error ? (
          <div className="empty-state">
            <strong>Allocation unavailable</strong>
            <span>
              {breakdownsQuery.error instanceof Error
                ? breakdownsQuery.error.message
                : "Breakdown request failed."}
            </span>
          </div>
        ) : null}

        {!breakdownsQuery.isLoading && !breakdownsQuery.error && selectedRows.length === 0 ? (
          <div className="empty-state">
            <strong>No allocation rows yet</strong>
            <span>Priced holdings will appear here after a refresh.</span>
          </div>
        ) : null}

        {selectedRows.length > 0 ? (
          <div
            className={
              selectedChartType === "table"
                ? "allocation-layout allocation-layout--table"
                : "allocation-layout"
            }
          >
            {selectedChartType === "bar" ? (
              <AllocationChart
                formatPercent={formatPercent}
                formatValue={formatMoney}
                onSelectRow={pinBucket}
                rows={selectedRows}
                title={selectedDimensionLabel}
              />
            ) : null}
            {selectedChartType === "donut" ? (
              <AllocationDonut
                formatPercent={formatPercent}
                formatValue={formatMoney}
                onSelectRow={pinBucket}
                rows={selectedRows}
                title={selectedDimensionLabel}
              />
            ) : null}
            <div className="allocation-table-wrap">
              <table className="allocation-table">
                <thead>
                  <tr>
                    <th scope="col">Label</th>
                    <th scope="col">Currency</th>
                    <th scope="col">Market value</th>
                    <th scope="col">Percent</th>
                    <th scope="col">Holdings</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedRows.map((row) => (
                    <tr
                      aria-expanded={
                        selectedBucketKey === `${row.dimension}-${row.label}-${row.currency}`
                      }
                      aria-label={`${row.label} ${row.currency} composition`}
                      className={
                        selectedBucketKey === `${row.dimension}-${row.label}-${row.currency}`
                          ? "allocation-row allocation-row--selected"
                          : "allocation-row"
                      }
                      key={`${selectedDimension}-${row.label}-${row.currency}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => pinBucket(row)}
                      onFocus={() => hoverBucket(row)}
                      onKeyDown={(event) => handleBucketKeyDown(event, row)}
                      onMouseEnter={() => hoverBucket(row)}
                    >
                      <td data-label="Label">{row.label}</td>
                      <td className="num" data-label="Currency">
                        {row.currency}
                      </td>
                      <td className="num" data-label="Market value">
                        {formatMoney(row.market_value, row.currency)}
                      </td>
                      <td className="num" data-label="Percent">
                        {formatPercent(row.percent)}
                      </td>
                      <td className="num" data-label="Holdings">
                        {row.holding_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {accessToken && selectedBucket ? (
          <CompositionPopover
            accessToken={accessToken}
            dimensionLabel={selectedDimensionLabel}
            formatPercent={formatPercent}
            formatValue={formatMoney}
            selectedBucket={selectedBucket}
            onClose={closeBucket}
          />
        ) : null}
      </section>

      {accessToken ? <SimulationPanel accessToken={accessToken} /> : null}

      {showBackendStatus ? (
        <div className="status-strip status-strip--secondary" aria-live="polite">
          <StatusIcon health={healthQuery.data} isLoading={healthQuery.isLoading} />
          <div>
            <p className="panel-label">Backend status</p>
            <strong>{statusCopy(healthQuery.data, healthQuery.isLoading)}</strong>
          </div>
          <span className="status-detail">
            {detailCopy(healthQuery.data, healthQuery.isLoading)}
          </span>
          <span className="status-endpoint num">
            {apiUrl.replace(/\/+$/, "")}/healthz
          </span>
          <span className="status-checked num">
            <Clock3 aria-hidden="true" />
            {checkedAt}
          </span>
        </div>
      ) : null}
    </section>
  );
}
