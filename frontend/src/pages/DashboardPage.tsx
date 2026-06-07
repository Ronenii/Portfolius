import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CircleAlert,
  CircleCheck,
  Clock3,
  RefreshCw,
} from "lucide-react";
import { useMemo } from "react";

import { useAuth } from "../features/auth/AuthContext";
import {
  getPortfolioSnapshot,
  refreshPrices,
  type PortfolioSnapshot,
} from "../features/portfolio/portfolio-api";
import { ApiError, type BackendHealth, fetchBackendHealth } from "../lib/api";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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
  const healthQuery = useQuery({
    queryKey: ["backend-health", apiUrl],
    queryFn: () => fetchBackendHealth(apiUrl),
  });
  const snapshotQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["portfolio-snapshot", accessToken],
    queryFn: () => getPortfolioSnapshot(accessToken ?? ""),
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
