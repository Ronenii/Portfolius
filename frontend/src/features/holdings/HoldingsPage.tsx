import { useQuery } from "@tanstack/react-query";
import { ArrowLeftRight } from "lucide-react";
import { Link } from "react-router-dom";

import { TrendLoader } from "../../components/ui/TrendLoader";
import { useAuth } from "../auth/AuthContext";
import { listHoldings } from "./holdings-api";

function displayValue(value: string | null | undefined) {
  return value && value.trim() ? value : "-";
}

function formatDecimal(value: string) {
  const numericValue = Number(value);
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: 8,
  }).format(Number.isFinite(numericValue) ? numericValue : 0);
}

function formatMoney(value: string, currency = "USD") {
  const numericValue = Number(value);
  return new Intl.NumberFormat("en", {
    currency,
    style: "currency",
  }).format(Number.isFinite(numericValue) ? numericValue : 0);
}

export default function HoldingsPage() {
  const { accessToken } = useAuth();

  const holdingsQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["holdings", accessToken],
    queryFn: () => listHoldings(accessToken ?? ""),
  });

  const holdings = holdingsQuery.data ?? [];

  return (
    <section className="dashboard-page holdings-page" aria-labelledby="holdings-title">
      <header className="page-header">
        <div>
          <p className="eyebrow">Positions</p>
          <h1 id="holdings-title">Holdings</h1>
        </div>
      </header>

      <div className="holdings-workspace">
        <section className="holdings-panel" aria-labelledby="holdings-list-title">
          <div className="panel-heading">
            <div>
              <p className="panel-label">Read-only summary</p>
              <h2 id="holdings-list-title">Current positions</h2>
            </div>
          </div>

          {holdingsQuery.isLoading ? (
            <TrendLoader label="Loading holdings" />
          ) : null}

          {holdingsQuery.error ? (
            <p className="form-error">Holdings unavailable</p>
          ) : null}

          {!holdingsQuery.isLoading && !holdingsQuery.error && holdings.length === 0 ? (
            <div className="empty-state">
              <strong>No holdings yet</strong>
              <span>Record a transaction to start building this portfolio.</span>
              <Link className="button button--ghost" to="/transactions">
                Go to Transactions
              </Link>
            </div>
          ) : null}

          {holdings.length > 0 ? (
            <div className="holdings-table-wrap">
              <table className="holdings-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Name</th>
                    <th>Exchange</th>
                    <th>Currency</th>
                    <th className="num-col">Quantity</th>
                    <th className="num-col">Purchase cost</th>
                    <th className="actions-col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((holding) => (
                    <tr key={holding.id}>
                      <td data-label="Symbol">
                        <strong>{holding.instrument.symbol.toUpperCase()}</strong>
                      </td>
                      <td data-label="Name">{displayValue(holding.instrument.name)}</td>
                      <td data-label="Exchange">
                        {displayValue(holding.instrument.exchange)}
                      </td>
                      <td data-label="Currency">
                        {holding.instrument.currency?.toUpperCase() ?? "-"}
                      </td>
                      <td data-label="Quantity" className="num">
                        {formatDecimal(holding.quantity)}
                      </td>
                      <td data-label="Purchase cost" className="num">
                        {formatMoney(
                          holding.average_cost,
                          holding.instrument.currency ?? "USD"
                        )}
                      </td>
                      <td data-label="Actions">
                        <div className="row-actions">
                          <Link
                            aria-label={`View transactions for ${holding.instrument.symbol}`}
                            className="icon-button"
                            to={`/transactions?symbol=${encodeURIComponent(holding.instrument.symbol)}`}
                          >
                            <ArrowLeftRight aria-hidden="true" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </div>
    </section>
  );
}
