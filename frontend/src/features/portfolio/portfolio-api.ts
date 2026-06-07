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

export function refreshPrices(accessToken: string) {
  return apiRequest<RefreshPricesResult>("/api/v1/jobs/refresh-prices", {
    accessToken,
    method: "POST",
  });
}
