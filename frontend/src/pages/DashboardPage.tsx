import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CircleAlert,
  CircleCheck,
  Clock3,
  RefreshCw,
} from "lucide-react";
import { useMemo, useState } from "react";

import { AllocationChart } from "../components/charts/AllocationChart";
import { useAuth } from "../features/auth/AuthContext";
import {
  getPortfolioBreakdowns,
  getPortfolioSnapshot,
  refreshPrices,
  type AllocationRow,
  type PortfolioBreakdowns,
  type PortfolioSnapshot,
} from "../features/portfolio/portfolio-api";
import { ApiError, type BackendHealth, fetchBackendHealth } from "../lib/api";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const breakdownDimensions = [
  { key: "asset_class", label: "Asset class" },
  { key: "sector", label: "Sector" },
  { key: "country", label: "Country" },
  { key: "region", label: "Region" },
  { key: "currency", label: "Currency" },
  { key: "instrument", label: "Instrument" },
] as const;

type BreakdownDimension = (typeof breakdownDimensions)[number]["key"];

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
  const healthQuery = useQuery({
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
  const selectedRows = breakdownRows(breakdownsQuery.data, selectedDimension);

  return (
    <section className="dashboard-page" aria-labelledby="dashboard-title">
      <header className="page-header">
        <div>
          <p className="eyebrow">Portfolio overview</p>
          <h1 id="dashboard-title">Dashboard</h1>
        </div>
        <button
          className="button button--primary"
          disabled={!accessToken || refreshMutation.isPending}
          type="button"
          onClick={() => refreshMutation.mutate()}
        >
          <RefreshCw aria-hidden="true" />
          {refreshMutation.isPending ? "Refreshing" : "Refresh prices"}
        </button>
      </header>

      <section className="dashboard-summary" aria-label="Portfolio summary">
        {snapshotQuery.isLoading ? (
          <div className="empty-state">
            <strong>Loading snapshot</strong>
            <span>Reading portfolio totals and price coverage.</span>
          </div>
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
              <article className="kpi-tile">
                <p className="panel-label">Priced value</p>
                <strong className="num">
                  {formatMoney(
                    snapshotQuery.data.summary.total_market_value,
                    snapshotQuery.data.summary.base_currency
                  )}
                </strong>
                <span>{snapshotQuery.data.summary.base_currency} priced holdings</span>
              </article>
              <article className="kpi-tile">
                <p className="panel-label">Cost basis</p>
                <strong className="num">
                  {formatMoney(
                    snapshotQuery.data.summary.total_cost_basis,
                    snapshotQuery.data.summary.base_currency
                  )}
                </strong>
                <span>Base-currency holdings only</span>
              </article>
              <article className="kpi-tile">
                <p className="panel-label">Unrealized gain</p>
                <strong className="num">
                  {formatMoney(
                    snapshotQuery.data.summary.total_unrealized_gain,
                    snapshotQuery.data.summary.base_currency
                  )}
                </strong>
                <span>Based on latest stored close</span>
              </article>
              <article className="kpi-tile">
                <p className="panel-label">Price coverage</p>
                <strong className="num">
                  {snapshotQuery.data.summary.priced_holdings} priced /{" "}
                  {snapshotQuery.data.summary.missing_price_holdings} missing
                </strong>
                <span>Latest price date: Not reported</span>
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
              onClick={() => setSelectedDimension(dimension.key)}
            >
              {dimension.label}
            </button>
          ))}
        </div>

        {breakdownsQuery.isLoading ? (
          <div className="empty-state">
            <strong>Loading allocations</strong>
            <span>Reading priced exposure by dimension.</span>
          </div>
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
          <div className="allocation-layout">
            <AllocationChart
              formatPercent={formatPercent}
              formatValue={formatMoney}
              rows={selectedRows}
              title={selectedDimensionLabel}
            />
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
                    <tr key={`${selectedDimension}-${row.label}-${row.currency}`}>
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
      </section>

      <div className="status-strip status-strip--secondary" aria-live="polite">
        <StatusIcon health={healthQuery.data} isLoading={healthQuery.isLoading} />
        <div>
          <p className="panel-label">Backend status</p>
          <strong>{statusCopy(healthQuery.data, healthQuery.isLoading)}</strong>
        </div>
        <span className="status-detail">{detailCopy(healthQuery.data, healthQuery.isLoading)}</span>
        <span className="status-endpoint num">{apiUrl.replace(/\/+$/, "")}/healthz</span>
        <span className="status-checked num">
          <Clock3 aria-hidden="true" />
          {checkedAt}
        </span>
      </div>
    </section>
  );
}
