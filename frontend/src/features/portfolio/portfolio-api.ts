import { apiRequest } from "../../lib/api";
import type { Instrument } from "../holdings/holdings-api";

export type PortfolioHoldingSnapshot = {
  holding_id: number;
  instrument: Instrument;
  quantity: string;
  average_cost: string;
  cost_basis: string;
  market_value: string | null;
  unrealized_gain: string | null;
  unrealized_gain_percent: string | null;
  price_status: "priced" | "missing_price";
};

export type PortfolioSummary = {
  base_currency: string;
  total_market_value: string;
  total_cost_basis: string;
  total_unrealized_gain: string;
  priced_holdings: number;
  missing_price_holdings: number;
  latest_price_date: string | null;
};

export type CurrencyTotal = {
  currency: string;
  market_value: string;
  cost_basis: string;
  unrealized_gain: string;
};

export type PortfolioSnapshot = {
  summary: PortfolioSummary;
  holdings: PortfolioHoldingSnapshot[];
  currency_totals: Record<string, CurrencyTotal>;
};

export type AllocationRow = {
  dimension: string;
  label: string;
  currency: string;
  market_value: string;
  percent: string;
  position_count: number;
  unit_quantity: string | null;
};

export type PortfolioBreakdowns = {
  instrument: AllocationRow[];
  asset_class: AllocationRow[];
  sector: AllocationRow[];
  country: AllocationRow[];
  region: AllocationRow[];
  currency: AllocationRow[];
  unpriced_holding_count: number;
};

export type CompositionRow = {
  instrument_id: number;
  symbol: string;
  name: string;
  currency: string;
  market_value: string;
  unit_quantity: string;
  percent_of_parent: string;
  percent_of_portfolio: string;
};

export type CompositionResponse = {
  dimension: string;
  key: string;
  currency: string;
  market_value: string;
  percent_of_portfolio: string;
  children: CompositionRow[];
  unpriced_holding_count: number;
};

export type TradeLeg = {
  instrument_id?: number | null;
  symbol?: string | null;
  action: "buy" | "sell";
  quantity: string;
  price?: string | null;
};

export type AllocationDelta = {
  dimension: string;
  label: string;
  currency: string;
  percent_before: string;
  percent_after: string;
  percent_change: string;
};

export type SimulationResponse = {
  current: PortfolioBreakdowns;
  simulated: PortfolioBreakdowns;
  delta: AllocationDelta[];
  warnings: string[];
};

export type RefreshPricesResult = {
  requested: number;
  updated: number;
  skipped: number;
  failed: number;
};

export type ProjectionYearPoint = {
  year: number;
  conservative: string;
  expected: string;
  optimistic: string;
  cost_basis: string;
};

export type ProjectionResponse = {
  base_currency: string;
  start_value: string;
  target_amount: string | null;
  horizon_years: number;
  contribution_amount: string;
  contribution_frequency: string;
  annual_return_expected: string;
  series: ProjectionYearPoint[];
  target_progress_percent: string | null;
  on_track: boolean | null;
  target_reached_year: number | null;
};

export type ProjectionOverrides = {
  target?: string;
  contribution?: string;
  annualReturn?: string;
  years?: number;
};

export function getPortfolioSnapshot(accessToken: string) {
  return apiRequest<PortfolioSnapshot>("/api/v1/portfolio/snapshot", {
    accessToken,
  });
}

export function getPortfolioBreakdowns(accessToken: string) {
  return apiRequest<PortfolioBreakdowns>("/api/v1/portfolio/breakdowns", {
    accessToken,
  });
}

export function getComposition(
  accessToken: string,
  dimension: string,
  key: string,
  currency?: string
) {
  const path = `/api/v1/portfolio/breakdowns/${encodeURIComponent(
    dimension
  )}/${encodeURIComponent(key)}/composition`;
  const query = currency ? `?currency=${encodeURIComponent(currency)}` : "";
  return apiRequest<CompositionResponse>(`${path}${query}`, {
    accessToken,
  });
}

export function refreshPrices(accessToken: string) {
  return apiRequest<RefreshPricesResult>("/api/v1/jobs/refresh-prices", {
    accessToken,
    method: "POST",
  });
}

export function simulatePortfolio(accessToken: string, legs: TradeLeg[]) {
  return apiRequest<SimulationResponse>("/api/v1/portfolio/simulate", {
    accessToken,
    body: { legs },
    method: "POST",
  });
}

export function getProjection(
  accessToken: string,
  overrides: ProjectionOverrides = {}
) {
  const params = new URLSearchParams();
  if (overrides.target !== undefined) params.set("target", overrides.target);
  if (overrides.contribution !== undefined)
    params.set("contribution", overrides.contribution);
  if (overrides.annualReturn !== undefined)
    params.set("annual_return", overrides.annualReturn);
  if (overrides.years !== undefined)
    params.set("years", String(overrides.years));

  const query = params.toString();
  return apiRequest<ProjectionResponse>(
    `/api/v1/portfolio/projection${query ? `?${query}` : ""}`,
    { accessToken }
  );
}
