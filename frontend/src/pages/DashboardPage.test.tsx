import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../app/query-client";
import { ApiError, fetchBackendHealth } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import {
  getComposition,
  getPortfolioBreakdowns,
  getPortfolioSnapshot,
  refreshPrices,
  type CompositionResponse,
  type PortfolioBreakdowns,
  type PortfolioSnapshot,
} from "../features/portfolio/portfolio-api";
import DashboardPage from "./DashboardPage";

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../features/portfolio/portfolio-api", () => ({
  getComposition: vi.fn(),
  getPortfolioBreakdowns: vi.fn(),
  getPortfolioSnapshot: vi.fn(),
  refreshPrices: vi.fn(),
  simulatePortfolio: vi.fn(),
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
    latest_price_date: "2026-06-05",
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

const assetClassComposition: CompositionResponse = {
  children: [
    {
      currency: "USD",
      holding_count: 1,
      instrument_id: 10,
      market_value: "750.00",
      name: "Vanguard S&P 500 ETF",
      percent_of_parent: "60",
      percent_of_portfolio: "37.5",
      symbol: "VOO",
    },
    {
      currency: "USD",
      holding_count: 1,
      instrument_id: 11,
      market_value: "500.00",
      name: "iShares Core US Aggregate Bond ETF",
      percent_of_parent: "40",
      percent_of_portfolio: "25",
      symbol: "AGG",
    },
  ],
  currency: "USD",
  dimension: "asset_class",
  key: "ETF",
  market_value: "1250.00",
  percent_of_portfolio: "62.5",
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
      latest_price_date: null,
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
    localStorage.clear();
    vi.unstubAllEnvs();
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
    vi.mocked(getComposition).mockResolvedValue(assetClassComposition);
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
    expect(within(summary).getByText("Latest price date: Jun 5, 2026")).toBeInTheDocument();
  });

  it("hides backend status in prod mode", async () => {
    vi.stubEnv("VITE_PROD_MODE", "true");

    renderDashboard();

    expect(screen.queryByText("Backend status")).not.toBeInTheDocument();
    expect(fetchBackendHealth).not.toHaveBeenCalled();
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

  it("renders chart type options and defaults to the bar chart", async () => {
    renderDashboard();

    expect(await screen.findByLabelText("Allocation chart type")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bar" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Donut" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
    expect(screen.getByRole("button", { name: "Table" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
    expect(await screen.findByRole("img", { name: "Asset class chart" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "ETF" })).toBeInTheDocument();
  });

  it("switches to donut and table views while keeping the allocation table visible", async () => {
    renderDashboard();

    await userEvent.click(await screen.findByRole("button", { name: "Donut" }));

    expect(screen.getByRole("button", { name: "Donut" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(
      await screen.findByRole("img", { name: "Asset class donut chart" })
    ).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "ETF" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Table" }));

    expect(screen.getByRole("button", { name: "Table" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.queryByRole("img", { name: "Asset class chart" })).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Asset class donut chart" })).not.toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "ETF" })).toBeInTheDocument();
  });

  it("persists the selected chart type across dashboard remounts", async () => {
    const firstRender = renderDashboard();

    await userEvent.click(await screen.findByRole("button", { name: "Donut" }));
    expect(localStorage.getItem("portfolius:allocation-chart-type")).toBe("donut");

    firstRender.unmount();
    renderDashboard();

    expect(await screen.findByRole("button", { name: "Donut" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(
      await screen.findByRole("img", { name: "Asset class donut chart" })
    ).toBeInTheDocument();
  });

  it("ignores an invalid stored chart type and falls back to bar", async () => {
    localStorage.setItem("portfolius:allocation-chart-type", "line");

    renderDashboard();

    expect(await screen.findByRole("button", { name: "Bar" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(await screen.findByRole("img", { name: "Asset class chart" })).toBeInTheDocument();
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

  it("shows child composition math for a selected allocation bucket", async () => {
    renderDashboard();

    await userEvent.click(
      await screen.findByRole("button", { name: /ETF USD composition/i })
    );

    expect(getComposition).toHaveBeenCalledWith(
      "access-token",
      "asset_class",
      "ETF",
      "USD"
    );
    expect(await screen.findByRole("heading", { name: "ETF composition" })).toBeInTheDocument();
    expect(screen.getByText("62.5% of portfolio")).toBeInTheDocument();
    expect(screen.getByText("VOO")).toBeInTheDocument();
    expect(screen.getByText("60% of slice · 37.5% of portfolio")).toBeInTheDocument();
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
