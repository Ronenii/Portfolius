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

export type HoldingPayload = {
  symbol: string;
  name?: string | null;
  exchange?: string | null;
  currency?: string | null;
  asset_class?: string | null;
  sector?: string | null;
  country?: string | null;
  region?: string | null;
  quantity: string;
  average_cost: string;
};

export function listHoldings(accessToken: string) {
  return apiRequest<Holding[]>("/api/v1/holdings", { accessToken });
}

export function createHolding(accessToken: string, payload: HoldingPayload) {
  return apiRequest<Holding>("/api/v1/holdings", {
    accessToken,
    body: payload,
    method: "POST",
  });
}

export function updateHolding(
  accessToken: string,
  holdingId: number,
  payload: HoldingPayload
) {
  return apiRequest<Holding>(`/api/v1/holdings/${holdingId}`, {
    accessToken,
    body: payload,
    method: "PUT",
  });
}

export function deleteHolding(accessToken: string, holdingId: number) {
  return apiRequest<void>(`/api/v1/holdings/${holdingId}`, {
    accessToken,
    method: "DELETE",
  });
}
