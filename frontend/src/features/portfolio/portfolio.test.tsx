import { describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "../../lib/api";
import {
  getComposition,
  getPortfolioBreakdowns,
  getPortfolioSnapshot,
  refreshPrices,
} from "./portfolio-api";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>(
    "../../lib/api"
  );
  return {
    ...actual,
    apiRequest: vi.fn(),
  };
});

describe("portfolio-api", () => {
  it("requests the portfolio snapshot with a bearer token", async () => {
    const snapshot = {
      summary: {
        base_currency: "USD",
        total_market_value: "1000",
        total_cost_basis: "800",
        total_unrealized_gain: "200",
        priced_holdings: 1,
        missing_price_holdings: 0,
      },
      holdings: [],
      currency_totals: {},
    };
    vi.mocked(apiRequest).mockResolvedValue(snapshot);

    await expect(getPortfolioSnapshot("access-token")).resolves.toEqual(snapshot);

    expect(apiRequest).toHaveBeenCalledWith("/api/v1/portfolio/snapshot", {
      accessToken: "access-token",
    });
  });

  it("requests allocation breakdowns with a bearer token", async () => {
    const breakdowns = {
      instrument: [],
      asset_class: [],
      sector: [],
      country: [],
      region: [],
      currency: [],
      unpriced_holding_count: 0,
    };
    vi.mocked(apiRequest).mockResolvedValue(breakdowns);

    await expect(getPortfolioBreakdowns("access-token")).resolves.toEqual(breakdowns);

    expect(apiRequest).toHaveBeenCalledWith("/api/v1/portfolio/breakdowns", {
      accessToken: "access-token",
    });
  });

  it("requests composition with encoded key and optional currency", async () => {
    const composition = {
      dimension: "asset_class",
      key: "International ETF",
      currency: "EUR",
      market_value: "180",
      percent_of_portfolio: "100",
      children: [],
      unpriced_holding_count: 0,
    };
    vi.mocked(apiRequest).mockResolvedValue(composition);

    await expect(
      getComposition("access-token", "asset_class", "International ETF", "EUR")
    ).resolves.toEqual(composition);

    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/portfolio/breakdowns/asset_class/International%20ETF/composition?currency=EUR",
      { accessToken: "access-token" }
    );
  });

  it("posts refresh requests with a bearer token and no body", async () => {
    const result = { requested: 2, updated: 1, skipped: 1, failed: 0 };
    vi.mocked(apiRequest).mockResolvedValue(result);

    await expect(refreshPrices("access-token")).resolves.toEqual(result);

    expect(apiRequest).toHaveBeenCalledWith("/api/v1/jobs/refresh-prices", {
      accessToken: "access-token",
      method: "POST",
    });
  });

  it("surfaces API errors from portfolio requests", async () => {
    const apiError = new ApiError(404, "Profile not found");
    vi.mocked(apiRequest).mockRejectedValue(apiError);

    await expect(getPortfolioSnapshot("access-token")).rejects.toBe(apiError);
  });
});
