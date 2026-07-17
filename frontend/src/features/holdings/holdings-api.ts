import { apiRequest } from "../../lib/api";

export type Instrument = {
  id: number;
  symbol: string;
  name: string | null;
  exchange: string;
  currency: string | null;
  asset_class: string | null;
  sector: string | null;
  country: string | null;
  region: string | null;
};

export type Holding = {
  id: number;
  instrument: Instrument;
  quantity: string;
  average_cost: string;
  created_at: string;
  updated_at: string;
};

export function listHoldings(accessToken: string) {
  return apiRequest<Holding[]>("/api/v1/holdings", { accessToken });
}
