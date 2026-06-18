import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { useAuth } from "../auth/AuthContext";
import DashboardPage from "../../pages/DashboardPage";
import { ApiError, fetchBackendHealth } from "../../lib/api";
import {
  getComposition,
  getPortfolioBreakdowns,
  getPortfolioSnapshot,
  refreshPrices,
  type CompositionResponse,
  type PortfolioBreakdowns,
  type PortfolioSnapshot,
} from "./portfolio-api";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("./portfolio-api", () => ({
  getComposition: vi.fn(),
  getPortfolioBreakdowns: vi.fn(),
  getPortfolioSnapshot: vi.fn(),
  refreshPrices: vi.fn(),
  simulatePortfolio: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    fetchBackendHealth: vi.fn(),
  };
});

const snapshot: PortfolioSnapshot = {
  currency_totals: {
    USD: {
      cost_basis: "1000.00",
      currency: "USD",
      market_value: "1250.00",
      unrealized_gain: "250.00",
    },
  },
  holdings: [],
  summary: {
    base_currency: "USD",
    latest_price_date: "2026-06-05",
    missing_price_holdings: 0,
    priced_holdings: 2,
    total_cost_basis: "1000.00",
    total_market_value: "1250.00",
    total_unrealized_gain: "250.00",
  },
};

const breakdowns: PortfolioBreakdowns = {
  asset_class: [
    {
      currency: "USD",
      dimension: "asset_class",
      holding_count: 2,
      label: "ETF",
      market_value: "1250.00",
      percent: "62.5",
    },
    {
      currency: "USD",
      dimension: "asset_class",
      holding_count: 0,
      label: "Alternatives",
      market_value: "0",
      percent: "0",
    },
  ],
  country: [],
  currency: [],
  instrument: [],
  region: [],
  sector: [],
  unpriced_holding_count: 1,
};

const etfComposition: CompositionResponse = {
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
  unpriced_holding_count: 1,
};

const emptyComposition: CompositionResponse = {
  children: [],
  currency: "USD",
  dimension: "asset_class",
  key: "Alternatives",
  market_value: "0",
  percent_of_portfolio: "0",
  unpriced_holding_count: 1,
};

function renderDashboard() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <DashboardPage />
    </QueryClientProvider>
  );
}

describe("allocation composition drill-down", () => {
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
    vi.mocked(getPortfolioBreakdowns).mockResolvedValue(breakdowns);
    vi.mocked(getPortfolioSnapshot).mockResolvedValue(snapshot);
    vi.mocked(getComposition).mockResolvedValue(etfComposition);
    vi.mocked(refreshPrices).mockResolvedValue({
      failed: 0,
      requested: 0,
      skipped: 0,
      updated: 0,
    });
  });

  it("opens a row composition popover from keyboard focus and Enter", async () => {
    const user = userEvent.setup();
    renderDashboard();

    const row = await screen.findByRole("button", { name: /ETF USD composition/i });
    row.focus();
    await user.keyboard("{Enter}");

    expect(getComposition).toHaveBeenCalledWith("access-token", "asset_class", "ETF", "USD");
    const popover = await screen.findByRole("dialog", { name: "ETF composition" });
    expect(within(popover).getByText("60% of slice · 37.5% of portfolio")).toBeInTheDocument();
    expect(within(popover).getByText("VOO")).toBeInTheDocument();
    expect(within(popover).getByText("1 unpriced excluded")).toBeInTheDocument();
  });

  it("opens the same composition popover on row hover", async () => {
    const user = userEvent.setup();
    renderDashboard();

    await user.hover(await screen.findByRole("button", { name: /ETF USD composition/i }));

    expect(await screen.findByRole("dialog", { name: "ETF composition" })).toBeInTheDocument();
    expect(getComposition).toHaveBeenCalledWith("access-token", "asset_class", "ETF", "USD");
  });

  it("shows a loading composition state", async () => {
    const user = userEvent.setup();
    vi.mocked(getComposition).mockReturnValue(new Promise(() => undefined));

    renderDashboard();

    const etfRow = await screen.findByRole("button", { name: /ETF USD composition/i });
    etfRow.focus();
    expect(etfRow).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Loading composition")).toBeInTheDocument();
  });

  it("shows an error composition state", async () => {
    const user = userEvent.setup();
    vi.mocked(getComposition).mockRejectedValue(new ApiError(500, "Composition failed"));

    renderDashboard();

    await user.click(await screen.findByRole("button", { name: /ETF USD composition/i }));
    expect(await screen.findByText("Composition failed")).toBeInTheDocument();
  });

  it("shows an empty composition state", async () => {
    const user = userEvent.setup();
    vi.mocked(getComposition).mockResolvedValue(emptyComposition);

    renderDashboard();

    await user.click(
      await screen.findByRole("button", { name: /Alternatives USD composition/i })
    );
    expect(await screen.findByText("No child instruments")).toBeInTheDocument();
  });

  it("closes with Escape and replaces the open slice when another row opens", async () => {
    const user = userEvent.setup();
    vi.mocked(getComposition).mockImplementation((_token, _dimension, key) =>
      Promise.resolve(key === "ETF" ? etfComposition : emptyComposition)
    );

    renderDashboard();

    await user.click(await screen.findByRole("button", { name: /ETF USD composition/i }));
    expect(await screen.findByRole("dialog", { name: "ETF composition" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Alternatives USD composition/i }));
    expect(
      await screen.findByRole("dialog", { name: "Alternatives composition" })
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "ETF composition" })).not.toBeInTheDocument();

    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(
        screen.queryByRole("dialog", { name: "Alternatives composition" })
      ).not.toBeInTheDocument();
    });
  });
});
