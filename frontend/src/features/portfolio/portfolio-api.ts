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
  holding_count: number;
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
  holding_count: number;
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
