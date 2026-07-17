import { apiRequest } from "../../lib/api";
import type { ImportRow } from "../../lib/csv";

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

export type Transaction = {
  id: number;
  instrument: Instrument;
  action: "buy" | "sell";
  quantity: string;
  price: string;
  fees: string;
  currency: string;
  trade_date: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type TransactionPayload = {
  symbol: string;
  name?: string | null;
  exchange?: string | null;
  currency?: string | null;
  asset_class?: string | null;
  sector?: string | null;
  country?: string | null;
  region?: string | null;
  action: "buy" | "sell";
  quantity: string;
  price: string;
  fees: string;
  trade_date: string;
  notes?: string | null;
};

export function listTransactions(accessToken: string, symbol?: string) {
  const query = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
  return apiRequest<Transaction[]>(`/api/v1/transactions${query}`, { accessToken });
}

export function createTransaction(accessToken: string, payload: TransactionPayload) {
  return apiRequest<Transaction>("/api/v1/transactions", {
    accessToken,
    body: payload,
    method: "POST",
  });
}

export function updateTransaction(
  accessToken: string,
  transactionId: number,
  payload: TransactionPayload
) {
  return apiRequest<Transaction>(`/api/v1/transactions/${transactionId}`, {
    accessToken,
    body: payload,
    method: "PUT",
  });
}

export function deleteTransaction(accessToken: string, transactionId: number) {
  return apiRequest<void>(`/api/v1/transactions/${transactionId}`, {
    accessToken,
    method: "DELETE",
  });
}

export type ImportResultRow = {
  row: number;
  status: "imported" | "failed";
  reason: string | null;
};

export type ImportResponse = { results: ImportResultRow[] };

export function importTransactions(
  accessToken: string,
  rows: ImportRow[]
): Promise<ImportResponse> {
  return apiRequest<ImportResponse>("/api/v1/transactions/import", {
    accessToken,
    body: { rows },
    method: "POST",
  });
}
