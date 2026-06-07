import { apiRequest } from "../../lib/api";

export type InstrumentSearchResult = {
  symbol: string;
  name: string | null;
  exchange: string | null;
  currency: string | null;
  asset_class: string | null;
  sector: string | null;
  country: string | null;
  region: string | null;
  source: string;
};

export function searchInstruments(accessToken: string, query: string) {
  return apiRequest<InstrumentSearchResult[]>(
    `/api/v1/instruments/search?query=${encodeURIComponent(query)}`,
    { accessToken }
  );
}
