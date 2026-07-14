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
  createTransaction,
  deleteTransaction,
  listTransactions,
  updateTransaction,
  type Transaction,
} from "./transactions-api";

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

vi.mock("./transactions-api", () => ({
  listTransactions: vi.fn(),
  createTransaction: vi.fn(),
  updateTransaction: vi.fn(),
  deleteTransaction: vi.fn(),
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

const appleBuy: Transaction = {
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
  action: "buy",
  quantity: "12.5",
  price: "145.20",
  fees: "1.50",
  currency: "USD",
  trade_date: "2026-06-01",
  notes: "Initial position",
  created_at: "2026-06-04T00:00:00Z",
  updated_at: "2026-06-04T00:00:00Z",
};

const teslaSell: Transaction = {
  ...appleBuy,
  id: 2,
  instrument: {
    ...appleBuy.instrument,
    id: 11,
    symbol: "TSLA",
    name: "Tesla",
  },
  action: "sell",
  quantity: "3",
  price: "180.00",
  fees: "0",
  trade_date: "2026-06-10",
  notes: null,
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

function renderTransactionsRoute() {
  const queryClient = createQueryClient();
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider
        router={createAppRouter(["/transactions"])}
        future={{ v7_startTransition: true }}
      />
    </QueryClientProvider>
  );
  return { ...rendered, queryClient };
}

async function fillTransactionForm(symbol = "msft") {
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
  await userEvent.selectOptions(screen.getByLabelText("Action"), "buy");
  await userEvent.clear(screen.getByLabelText("Quantity"));
  await userEvent.type(screen.getByLabelText("Quantity"), "4.25");
  await userEvent.clear(screen.getByLabelText("Price"));
  await userEvent.type(screen.getByLabelText("Price"), "312.50");
  await userEvent.clear(screen.getByLabelText("Fees"));
  await userEvent.type(screen.getByLabelText("Fees"), "2.00");
  const tradeDateInput = screen.getByLabelText("Trade date") as HTMLInputElement;
  await userEvent.clear(tradeDateInput);
  await userEvent.type(tradeDateInput, "2026-07-01");
  await userEvent.clear(screen.getByLabelText("Notes"));
  await userEvent.type(screen.getByLabelText("Notes"), "Adding shares");
}

describe("transactions page", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    mockAuthState();
    vi.mocked(getProfile).mockResolvedValue(mockProfile);
    vi.mocked(listTransactions).mockResolvedValue([appleBuy]);
    vi.mocked(createTransaction).mockResolvedValue(teslaSell);
    vi.mocked(updateTransaction).mockResolvedValue(appleBuy);
    vi.mocked(deleteTransaction).mockResolvedValue(undefined);
    vi.mocked(searchInstruments).mockResolvedValue([]);
  });

  it("lists fetched transactions", async () => {
    renderTransactionsRoute();

    expect(await screen.findByRole("heading", { name: "Transactions" })).toBeInTheDocument();
    const row = await screen.findByRole("row", { name: /AAPL/i });
    expect(within(row).getByText("AAPL")).toBeInTheDocument();
    expect(within(row).getByText("Buy")).toBeInTheDocument();
    expect(within(row).getByText("12.5")).toBeInTheDocument();
    expect(within(row).getByText("$145.20")).toBeInTheDocument();
  });

  it("shows an empty state when there are no transactions", async () => {
    vi.mocked(listTransactions).mockResolvedValue([]);

    renderTransactionsRoute();

    expect(await screen.findByText("No transactions yet")).toBeInTheDocument();
  });

  it("calls createTransaction with the expected payload shape", async () => {
    vi.mocked(listTransactions).mockResolvedValue([]);
    const { queryClient } = renderTransactionsRoute();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    await fillTransactionForm();
    await userEvent.click(screen.getByRole("button", { name: "Save transaction" }));

    await waitFor(() => {
      expect(createTransaction).toHaveBeenCalledWith("access-token", {
        symbol: "msft",
        name: "Microsoft",
        exchange: "nasdaq",
        currency: "usd",
        asset_class: "Equity",
        sector: "Technology",
        country: "United States",
        region: "North America",
        action: "buy",
        quantity: "4.25",
        price: "312.50",
        fees: "2.00",
        trade_date: "2026-07-01",
        notes: "Adding shares",
      });
    });
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["transactions"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-snapshot"],
      });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["holdings"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-breakdowns"],
      });
    });
  });

  it("autofills instrument metadata from a selected search result", async () => {
    vi.mocked(listTransactions).mockResolvedValue([]);
    vi.mocked(searchInstruments).mockResolvedValue([indiaSearchResult]);
    renderTransactionsRoute();

    await userEvent.type(await screen.findByLabelText("Symbol"), "IND");
    await userEvent.click(await screen.findByRole("option", { name: /INDA/i }));
    await userEvent.type(screen.getByLabelText("Quantity"), "2");
    await userEvent.type(screen.getByLabelText("Price"), "44.50");
    await userEvent.click(screen.getByRole("button", { name: "Save transaction" }));

    await waitFor(() => {
      expect(createTransaction).toHaveBeenCalledWith(
        "access-token",
        expect.objectContaining({
          symbol: "INDA",
          name: "iShares MSCI India ETF",
          exchange: "BATS",
          currency: "USD",
          asset_class: "ETF",
          sector: "Broad Market",
          country: "India",
          region: "Asia",
          action: "buy",
          quantity: "2",
          price: "44.50",
          fees: "0",
        })
      );
    });
  });

  it("pre-populates the form when editing a transaction", async () => {
    renderTransactionsRoute();

    const row = await screen.findByRole("row", { name: /AAPL/i });
    await userEvent.click(within(row).getByRole("button", { name: "Edit AAPL" }));

    expect(await screen.findByLabelText("Symbol")).toHaveValue("AAPL");
    expect(screen.getByLabelText("Quantity")).toHaveValue("12.5");
    expect(screen.getByLabelText("Price")).toHaveValue("145.20");
    expect(screen.getByLabelText("Fees")).toHaveValue("1.50");
    expect(screen.getByLabelText("Action")).toHaveValue("buy");
    expect(screen.getByLabelText("Trade date")).toHaveValue("2026-06-01");
    expect(screen.getByLabelText("Notes")).toHaveValue("Initial position");
  });

  it("calls updateTransaction for the selected transaction", async () => {
    const { queryClient } = renderTransactionsRoute();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const row = await screen.findByRole("row", { name: /AAPL/i });
    await userEvent.click(within(row).getByRole("button", { name: "Edit AAPL" }));
    await userEvent.clear(screen.getByLabelText("Quantity"));
    await userEvent.type(screen.getByLabelText("Quantity"), "20");
    await userEvent.click(screen.getByRole("button", { name: "Save transaction" }));

    await waitFor(() => {
      expect(updateTransaction).toHaveBeenCalledWith(
        "access-token",
        1,
        expect.objectContaining({
          symbol: "AAPL",
          quantity: "20",
          price: "145.20",
        })
      );
    });
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["transactions"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-snapshot"],
      });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["holdings"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-breakdowns"],
      });
    });
  });

  it("deletes a transaction only after confirmation", async () => {
    const { queryClient } = renderTransactionsRoute();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const row = await screen.findByRole("row", { name: /AAPL/i });
    await userEvent.click(within(row).getByRole("button", { name: "Delete AAPL" }));

    expect(deleteTransaction).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Confirm delete AAPL" }));

    await waitFor(() => {
      expect(deleteTransaction).toHaveBeenCalledWith("access-token", 1);
    });
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["transactions"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-snapshot"],
      });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["holdings"] });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["portfolio-breakdowns"],
      });
    });
  });

  it("shows server mutation errors", async () => {
    vi.mocked(listTransactions).mockResolvedValue([]);
    vi.mocked(createTransaction).mockRejectedValue(
      new ApiError(422, "Cannot sell 20 units; only 10 held.")
    );
    renderTransactionsRoute();

    await fillTransactionForm("bad");
    await userEvent.click(screen.getByRole("button", { name: "Save transaction" }));

    expect(
      await screen.findByText("Cannot sell 20 units; only 10 held.")
    ).toBeInTheDocument();
  });
});
