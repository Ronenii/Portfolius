import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../app/query-client";
import { ApiError, fetchBackendHealth } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import {
  getPortfolioBreakdowns,
  getPortfolioSnapshot,
  refreshPrices,
  type PortfolioBreakdowns,
  type PortfolioSnapshot,
} from "../features/portfolio/portfolio-api";
import DashboardPage from "./DashboardPage";

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../features/portfolio/portfolio-api", () => ({
  getPortfolioBreakdowns: vi.fn(),
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

const pricedBreakdowns: PortfolioBreakdowns = {
  asset_class: [
    {
      currency: "USD",
      dimension: "asset_class",
      holding_count: 1,
      label: "ETF",
      market_value: "1250.00",
      percent: "62.5",
    },
  ],
  country: [
    {
      currency: "USD",
      dimension: "country",
      holding_count: 1,
      label: "United States",
      market_value: "1250.00",
      percent: "100",
    },
  ],
  currency: [
    {
      currency: "USD",
      dimension: "currency",
      holding_count: 1,
      label: "USD",
      market_value: "1250.00",
      percent: "100",
    },
  ],
  instrument: [
    {
      currency: "USD",
      dimension: "instrument",
      holding_count: 1,
      label: "VOO",
      market_value: "1250.00",
      percent: "100",
    },
  ],
  region: [
    {
      currency: "USD",
      dimension: "region",
      holding_count: 1,
      label: "North America",
      market_value: "1250.00",
      percent: "100",
    },
  ],
  sector: [
    {
      currency: "USD",
      dimension: "sector",
      holding_count: 1,
      label: "Broad Market",
      market_value: "1250.00",
      percent: "100",
    },
  ],
  unpriced_holding_count: 0,
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
    vi.mocked(getPortfolioBreakdowns).mockResolvedValue(pricedBreakdowns);
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

    const summary = await screen.findByLabelText("Portfolio summary");

    expect(await within(summary).findByText("$1,250.00")).toBeInTheDocument();
    expect(within(summary).getByText("$1,000.00")).toBeInTheDocument();
    expect(within(summary).getByText("$250.00")).toBeInTheDocument();
    expect(within(summary).getByText("1 priced / 0 missing")).toBeInTheDocument();
  });

  it("renders the asset class breakdown by default", async () => {
    renderDashboard();

    expect(await screen.findByRole("heading", { name: "Allocation breakdown" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Asset class" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(await screen.findByRole("cell", { name: "ETF" })).toBeInTheDocument();
  });

  it("updates table labels when the breakdown dimension changes", async () => {
    renderDashboard();

    await userEvent.click(await screen.findByRole("button", { name: "Sector" }));

    expect(screen.getByRole("button", { name: "Sector" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("cell", { name: "Broad Market" })).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "ETF" })).not.toBeInTheDocument();
  });

  it("renders an empty state when the selected breakdown has no rows", async () => {
    vi.mocked(getPortfolioBreakdowns).mockResolvedValue({
      ...pricedBreakdowns,
      sector: [],
    });

    renderDashboard();

    await userEvent.click(await screen.findByRole("button", { name: "Sector" }));

    expect(screen.getByText("No allocation rows yet")).toBeInTheDocument();
  });

  it("renders breakdown percentages and market values from the API", async () => {
    renderDashboard();

    expect(await screen.findByRole("cell", { name: "$1,250.00" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "62.5%" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "1" })).toBeInTheDocument();
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
