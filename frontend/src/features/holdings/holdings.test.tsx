import type { Session } from "@supabase/supabase-js";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { createAppRouter } from "../../app/router";
import { ApiError } from "../../lib/api";
import { supabase } from "../../lib/supabase";
import { searchInstruments } from "../instruments/instrument-search-api";
import { getProfile } from "../profile/profile-api";
import {
  createHolding,
  deleteHolding,
  listHoldings,
  updateHolding,
  type Holding,
} from "./holdings-api";

vi.mock("../../lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      onAuthStateChange: vi.fn(),
      signInWithOAuth: vi.fn(),
      signInWithOtp: vi.fn(),
      signOut: vi.fn(),
    },
  },
}));

vi.mock("../profile/profile-api", () => ({
  getProfile: vi.fn(),
  saveProfile: vi.fn(),
}));

vi.mock("../instruments/instrument-search-api", () => ({
  searchInstruments: vi.fn(),
}));

vi.mock("./holdings-api", () => ({
  listHoldings: vi.fn(),
  createHolding: vi.fn(),
  updateHolding: vi.fn(),
  deleteHolding: vi.fn(),
}));

const mockSession = {
  access_token: "access-token",
  refresh_token: "refresh-token",
  expires_in: 3600,
  token_type: "bearer",
  user: { id: "user-123", email: "investor@example.com" },
} as Session;

const mockProfile = {
  id: 1,
  user_id: "user-123",
  display_name: "Ronen",
  base_currency: "USD",
  time_horizon: "10+ years",
  investment_frequency: "monthly",
  risk_tolerance: null,
  interest_tags: [],
  excluded_sectors: [],
  goals_note: null,
  created_at: "2026-06-04T00:00:00Z",
  updated_at: "2026-06-04T00:00:00Z",
};

const appleHolding: Holding = {
  id: 1,
  instrument: {
    id: 10,
    symbol: "AAPL",
    name: "Apple Inc.",
    exchange: "NASDAQ",
    currency: "USD",
    asset_class: "Equity",
    sector: "Technology",
    country: "United States",
    region: "North America",
  },
  quantity: "12.5",
  average_cost: "145.20",
  created_at: "2026-06-04T00:00:00Z",
  updated_at: "2026-06-04T00:00:00Z",
};

const teslaHolding: Holding = {
  ...appleHolding,
  id: 2,
  instrument: {
    ...appleHolding.instrument,
    id: 11,
    symbol: "TSLA",
    name: "Tesla",
  },
  quantity: "3",
  average_cost: "180.00",
};

const indiaSearchResult = {
  symbol: "INDA",
  name: "iShares MSCI India ETF",
  exchange: "BATS",
  currency: "USD",
  asset_class: "ETF",
  sector: "Broad Market",
  country: "India",
  region: "Asia",
  source: "fmp",
};

function mockAuthState() {
  vi.mocked(supabase.auth.getSession).mockResolvedValue(
    {
      data: { session: mockSession },
      error: null,
    } as Awaited<ReturnType<typeof supabase.auth.getSession>>
  );
  vi.mocked(supabase.auth.onAuthStateChange).mockReturnValue({
    data: {
      subscription: {
        id: "subscription-id",
        callback: vi.fn(),
        unsubscribe: vi.fn(),
      },
    },
  });
}

function renderHoldingsRoute() {
  const queryClient = createQueryClient();
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider
        router={createAppRouter(["/holdings"])}
        future={{ v7_startTransition: true }}
      />
    </QueryClientProvider>
  );
  return { ...rendered, queryClient };
}

async function fillHoldingForm(symbol = "msft") {
  await userEvent.clear(await screen.findByLabelText("Symbol"));
  await userEvent.type(screen.getByLabelText("Symbol"), symbol);
  await userEvent.clear(screen.getByLabelText("Name"));
  await userEvent.type(screen.getByLabelText("Name"), "Microsoft");
  await userEvent.clear(screen.getByLabelText("Exchange"));
  await userEvent.type(screen.getByLabelText("Exchange"), "nasdaq");
  await userEvent.clear(screen.getByLabelText("Currency"));
  await userEvent.type(screen.getByLabelText("Currency"), "usd");
  await userEvent.clear(screen.getByLabelText("Asset class"));
  await userEvent.type(screen.getByLabelText("Asset class"), "Equity");
  await userEvent.clear(screen.getByLabelText("Sector"));
  await userEvent.type(screen.getByLabelText("Sector"), "Technology");
  await userEvent.clear(screen.getByLabelText("Country"));
  await userEvent.type(screen.getByLabelText("Country"), "United States");
  await userEvent.clear(screen.getByLabelText("Region"));
  await userEvent.type(screen.getByLabelText("Region"), "North America");
  await userEvent.clear(screen.getByLabelText("Quantity"));
  await userEvent.type(screen.getByLabelText("Quantity"), "4.25");
  await userEvent.clear(screen.getByLabelText("Purchase cost"));
  await userEvent.type(screen.getByLabelText("Purchase cost"), "312.50");
}

describe("holdings page", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    mockAuthState();
    vi.mocked(getProfile).mockResolvedValue(mockProfile);
    vi.mocked(listHoldings).mockResolvedValue([appleHolding]);
    vi.mocked(createHolding).mockResolvedValue(teslaHolding);
    vi.mocked(updateHolding).mockResolvedValue(appleHolding);
    vi.mocked(deleteHolding).mockResolvedValue(undefined);
    vi.mocked(searchInstruments).mockResolvedValue([]);
  });

  it("lists fetched holdings", async () => {
    renderHoldingsRoute();

    expect(await screen.findByRole("heading", { name: "Holdings" })).toBeInTheDocument();
    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.getByText("12.5")).toBeInTheDocument();
    expect(screen.getByText("$145.20")).toBeInTheDocument();
  });

  it("formats decimal fields in the holdings table without trailing zero noise", async () => {
    vi.mocked(listHoldings).mockResolvedValue([
      {
        ...appleHolding,
        quantity: "12.50000000",
        average_cost: "145.20000000",
      },
    ]);

    renderHoldingsRoute();

    const row = await screen.findByRole("row", { name: /AAPL/i });
    expect(within(row).getByText("12.5")).toBeInTheDocument();
    expect(within(row).getByText("$145.20")).toBeInTheDocument();
    expect(within(row).queryByText("12.50000000")).not.toBeInTheDocument();
    expect(within(row).queryByText("145.20000000")).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no holdings", async () => {
    vi.mocked(listHoldings).mockResolvedValue([]);

    renderHoldingsRoute();

    expect(await screen.findByText("No holdings yet")).toBeInTheDocument();
  });

  it("calls createHolding with string decimal fields", async () => {
    vi.mocked(listHoldings).mockResolvedValue([]);
    const { queryClient } = renderHoldingsRoute();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    await fillHoldingForm();
    await userEvent.click(screen.getByRole("button", { name: "Save holding" }));

    await waitFor(() => {
      expect(createHolding).toHaveBeenCalledWith("access-token", {
        symbol: "msft",
        name: "Microsoft",
        exchange: "nasdaq",
        currency: "usd",
        asset_class: "Equity",
        sector: "Technology",
        country: "United States",
        region: "North America",
        quantity: "4.25",
        average_cost: "312.50",
      });
    });
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["holdings"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-snapshot"],
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-breakdowns"],
      });
    });
  });

  it("autofills instrument metadata from a selected search result", async () => {
    vi.mocked(listHoldings).mockResolvedValue([]);
    vi.mocked(searchInstruments).mockResolvedValue([indiaSearchResult]);
    renderHoldingsRoute();

    await userEvent.type(await screen.findByLabelText("Symbol"), "IND");
    await userEvent.click(await screen.findByRole("option", { name: /INDA/i }));
    await userEvent.type(screen.getByLabelText("Quantity"), "2");
    await userEvent.type(screen.getByLabelText("Purchase cost"), "44.50");
    await userEvent.click(screen.getByRole("button", { name: "Save holding" }));

    await waitFor(() => {
      expect(createHolding).toHaveBeenCalledWith("access-token", {
        symbol: "INDA",
        name: "iShares MSCI India ETF",
        exchange: "BATS",
        currency: "USD",
        asset_class: "ETF",
        sector: "Broad Market",
        country: "India",
        region: "Asia",
        quantity: "2",
        average_cost: "44.50",
      });
    });
  });

  it("calls updateHolding for the selected holding", async () => {
    const { queryClient } = renderHoldingsRoute();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const row = await screen.findByRole("row", { name: /AAPL/i });
    await userEvent.click(within(row).getByRole("button", { name: "Edit AAPL" }));
    await userEvent.clear(screen.getByLabelText("Quantity"));
    await userEvent.type(screen.getByLabelText("Quantity"), "20");
    await userEvent.click(screen.getByRole("button", { name: "Save holding" }));

    await waitFor(() => {
      expect(updateHolding).toHaveBeenCalledWith(
        "access-token",
        1,
        expect.objectContaining({
          symbol: "AAPL",
          quantity: "20",
          average_cost: "145.20",
        })
      );
    });
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["holdings"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-snapshot"],
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-breakdowns"],
      });
    });
  });

  it("deletes a holding only after confirmation", async () => {
    const { queryClient } = renderHoldingsRoute();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const row = await screen.findByRole("row", { name: /AAPL/i });
    await userEvent.click(within(row).getByRole("button", { name: "Delete AAPL" }));

    expect(deleteHolding).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Confirm delete AAPL" }));

    await waitFor(() => {
      expect(deleteHolding).toHaveBeenCalledWith("access-token", 1);
    });
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["holdings"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-snapshot"],
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-breakdowns"],
      });
    });
  });

  it("shows server mutation errors", async () => {
    vi.mocked(listHoldings).mockResolvedValue([]);
    vi.mocked(createHolding).mockRejectedValue(
      new ApiError(400, "Quantity must be greater than zero")
    );
    renderHoldingsRoute();

    await fillHoldingForm("bad");
    await userEvent.click(screen.getByRole("button", { name: "Save holding" }));

    expect(await screen.findByText("Quantity must be greater than zero")).toBeInTheDocument();
  });
});
