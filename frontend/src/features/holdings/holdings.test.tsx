import type { Session } from "@supabase/supabase-js";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { createAppRouter } from "../../app/router";
import { supabase } from "../../lib/supabase";
import { getProfile } from "../profile/profile-api";
import { listHoldings, type Holding } from "./holdings-api";

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

vi.mock("./holdings-api", () => ({
  listHoldings: vi.fn(),
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
  goal_target_amount: null,
  contribution_amount: null,
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

describe("holdings page", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    mockAuthState();
    vi.mocked(getProfile).mockResolvedValue(mockProfile);
    vi.mocked(listHoldings).mockResolvedValue([appleHolding]);
  });

  it("renders a shaped loading state while holdings are pending", async () => {
    vi.mocked(listHoldings).mockReturnValue(new Promise(() => undefined));

    renderHoldingsRoute();

    await screen.findByRole("heading", { name: "Holdings" });
    const loadingText = await screen.findByText("Loading holdings");
    const status = loadingText.closest('[role="status"]') as HTMLElement;
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status.querySelectorAll(".skeleton").length).toBeGreaterThan(0);
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

  it("shows an empty state linking to Transactions when there are no holdings", async () => {
    vi.mocked(listHoldings).mockResolvedValue([]);

    renderHoldingsRoute();

    expect(await screen.findByText("No holdings yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Transactions" })).toHaveAttribute(
      "href",
      "/transactions"
    );
  });

  it("links each row to its filtered transaction history", async () => {
    renderHoldingsRoute();

    const row = await screen.findByRole("row", { name: /AAPL/i });
    expect(
      within(row).getByRole("link", { name: "View transactions for AAPL" })
    ).toHaveAttribute("href", "/transactions?symbol=AAPL");
  });

  it("does not render create, edit, or delete controls", async () => {
    renderHoldingsRoute();

    await screen.findByRole("row", { name: /AAPL/i });

    expect(screen.queryByRole("button", { name: "Save holding" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Symbol")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit AAPL" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete AAPL" })).not.toBeInTheDocument();
  });
});
