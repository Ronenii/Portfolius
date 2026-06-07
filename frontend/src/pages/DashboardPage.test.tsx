import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../app/query-client";
import { ApiError, fetchBackendHealth } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import {
  getPortfolioSnapshot,
  refreshPrices,
  type PortfolioSnapshot,
} from "../features/portfolio/portfolio-api";
import DashboardPage from "./DashboardPage";

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../features/portfolio/portfolio-api", () => ({
  getPortfolioSnapshot: vi.fn(),
  refreshPrices: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    fetchBackendHealth: vi.fn(),
  };
});

const pricedSnapshot: PortfolioSnapshot = {
  summary: {
    base_currency: "USD",
    total_market_value: "1250.00",
    total_cost_basis: "1000.00",
    total_unrealized_gain: "250.00",
    priced_holdings: 1,
    missing_price_holdings: 0,
  },
  holdings: [
    {
      holding_id: 1,
      instrument: {
        id: 10,
        symbol: "VOO",
        name: "Vanguard S&P 500 ETF",
        exchange: "NYSEARCA",
        currency: "USD",
        asset_class: "ETF",
        sector: "Broad Market",
        country: "United States",
        region: "North America",
      },
      quantity: "2.5",
      average_cost: "400.00",
      cost_basis: "1000.00",
      market_value: "1250.00",
      unrealized_gain: "250.00",
      unrealized_gain_percent: "25.00",
      price_status: "priced",
    },
  ],
  currency_totals: {
    USD: {
      currency: "USD",
      market_value: "1250.00",
      cost_basis: "1000.00",
      unrealized_gain: "250.00",
    },
  },
};

function emptySnapshot(): PortfolioSnapshot {
  return {
    ...pricedSnapshot,
    summary: {
      base_currency: "USD",
      total_market_value: "0",
      total_cost_basis: "0",
      total_unrealized_gain: "0",
      priced_holdings: 0,
      missing_price_holdings: 0,
    },
    holdings: [],
    currency_totals: {},
  };
}

function renderDashboard() {
  const queryClient = createQueryClient();
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <DashboardPage />
      </QueryClientProvider>
    ),
  };
}

describe("DashboardPage", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      accessToken: "access-token",
      isLoading: false,
      session: null,
      signInWithGoogle: vi.fn(),
      signInWithMagicLink: vi.fn(),
      signOut: vi.fn(),
      user: null,
    });
    vi.mocked(fetchBackendHealth).mockResolvedValue({ status: "ok" });
    vi.mocked(getPortfolioSnapshot).mockResolvedValue(pricedSnapshot);
    vi.mocked(refreshPrices).mockResolvedValue({
      requested: 1,
      updated: 1,
      skipped: 0,
      failed: 0,
    });
  });

  it("renders a loading state while the snapshot query is pending", async () => {
    vi.mocked(getPortfolioSnapshot).mockReturnValue(new Promise(() => undefined));

    renderDashboard();

    expect(await screen.findByText("Loading snapshot")).toBeInTheDocument();
  });

  it("renders an empty holdings state for zero holdings", async () => {
    vi.mocked(getPortfolioSnapshot).mockResolvedValue(emptySnapshot());

    renderDashboard();

    expect(await screen.findByText("No holdings yet")).toBeInTheDocument();
  });

  it("renders missing price copy when holdings are unpriced", async () => {
    vi.mocked(getPortfolioSnapshot).mockResolvedValue({
      ...pricedSnapshot,
      summary: {
        ...pricedSnapshot.summary,
        priced_holdings: 0,
        missing_price_holdings: 1,
      },
      holdings: [
        {
          ...pricedSnapshot.holdings[0],
          market_value: null,
          price_status: "missing_price",
          unrealized_gain: null,
          unrealized_gain_percent: null,
        },
      ],
    });

    renderDashboard();

    expect(await screen.findByText("Prices missing")).toBeInTheDocument();
  });

  it("renders summary values when priced data is returned", async () => {
    renderDashboard();

    expect(await screen.findByText("$1,250.00")).toBeInTheDocument();
    expect(screen.getByText("$1,000.00")).toBeInTheDocument();
    expect(screen.getByText("$250.00")).toBeInTheDocument();
    expect(screen.getByText("1 priced / 0 missing")).toBeInTheDocument();
  });

  it("refreshes prices and invalidates portfolio queries", async () => {
    const { queryClient } = renderDashboard();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    await userEvent.click(await screen.findByRole("button", { name: "Refresh prices" }));

    await waitFor(() => {
      expect(refreshPrices).toHaveBeenCalledWith("access-token");
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["portfolio-snapshot"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["portfolio-breakdowns"] });
  });

  it("renders refresh failure copy", async () => {
    vi.mocked(refreshPrices).mockRejectedValue(new ApiError(500, "Refresh failed"));

    renderDashboard();
    await userEvent.click(await screen.findByRole("button", { name: "Refresh prices" }));

    expect(await screen.findByText("Refresh failed")).toBeInTheDocument();
  });
});
