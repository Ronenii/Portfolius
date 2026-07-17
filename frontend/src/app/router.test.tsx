import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import type { Session } from "@supabase/supabase-js";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "./query-client";
import { createAppRouter } from "./router";
import { listHoldings } from "../features/holdings/holdings-api";
import { ApiError } from "../lib/api";
import { supabase } from "../lib/supabase";
import { getProfile } from "../features/profile/profile-api";
import {
  getPortfolioBreakdowns,
  getPortfolioSnapshot,
  getProjection,
  type PortfolioBreakdowns,
  type PortfolioSnapshot,
  type ProjectionResponse,
} from "../features/portfolio/portfolio-api";

vi.mock("../lib/supabase", () => ({
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

vi.mock("../features/profile/profile-api", () => ({
  getProfile: vi.fn(),
  saveProfile: vi.fn(),
}));

vi.mock("../features/holdings/holdings-api", () => ({
  listHoldings: vi.fn(),
  createHolding: vi.fn(),
  updateHolding: vi.fn(),
  deleteHolding: vi.fn(),
}));

// The /dashboard route mounts several panels that each own a query against
// portfolio-api. Without this mock they'd all race to read the single
// globally-stubbed `fetch` Response body (only the first reader succeeds;
// Response bodies can only be consumed once), which is exactly the kind of
// non-deterministic setup that broke when a new panel (ProjectionPanel) was
// added. Stub the module directly so each query gets a deterministic,
// correctly-shaped fixture instead.
vi.mock("../features/portfolio/portfolio-api", () => ({
  getComposition: vi.fn(),
  getPortfolioBreakdowns: vi.fn(),
  getPortfolioSnapshot: vi.fn(),
  getProjection: vi.fn(),
  refreshPrices: vi.fn(),
  simulatePortfolio: vi.fn(),
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

const emptySnapshot: PortfolioSnapshot = {
  currency_totals: {},
  holdings: [],
  summary: {
    base_currency: "USD",
    latest_price_date: null,
    missing_price_holdings: 0,
    priced_holdings: 0,
    total_cost_basis: "0",
    total_market_value: "0",
    total_unrealized_gain: "0",
  },
};

const emptyBreakdowns: PortfolioBreakdowns = {
  asset_class: [],
  country: [],
  currency: [],
  instrument: [],
  region: [],
  sector: [],
  unpriced_holding_count: 0,
};

const emptyProjection: ProjectionResponse = {
  annual_return_expected: "0.06",
  base_currency: "USD",
  contribution_amount: "0",
  contribution_frequency: "monthly",
  horizon_years: 10,
  on_track: null,
  series: [
    { conservative: "0", expected: "0", optimistic: "0", cost_basis: "0", year: 0 },
  ],
  start_value: "0",
  target_amount: null,
  target_progress_percent: null,
  target_reached_year: null,
};

function mockAuthState(session: Session | null) {
  vi.mocked(supabase.auth.getSession).mockResolvedValue(
    {
      data: { session },
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

function renderRoute(path: string) {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider
        router={createAppRouter([path])}
        future={{ v7_startTransition: true }}
      />
    </QueryClientProvider>
  );
}

describe("app router foundation", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), {
          headers: { "Content-Type": "application/json" },
        })
      )
    );
  });

  it("renders the dashboard with the compact backend health signal", async () => {
    mockAuthState(mockSession);
    vi.mocked(getProfile).mockResolvedValue(mockProfile);
    vi.mocked(getPortfolioSnapshot).mockResolvedValue(emptySnapshot);
    vi.mocked(getPortfolioBreakdowns).mockResolvedValue(emptyBreakdowns);
    vi.mocked(getProjection).mockResolvedValue(emptyProjection);
    renderRoute("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Dashboard" })
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Backend healthy")).toBeInTheDocument();
    });
    expect(screen.getByText(/\/healthz$/)).toBeInTheDocument();
  });

  it("registers the login route", async () => {
    mockAuthState(null);
    renderRoute("/login");

    expect(
      await screen.findByRole("heading", { name: "Sign in" })
    ).toBeInTheDocument();
  });

  it("registers the profile setup route", async () => {
    mockAuthState(mockSession);
    vi.mocked(getProfile).mockRejectedValue(new ApiError(404, "Profile not found"));
    renderRoute("/profile/setup");

    expect(
      await screen.findByRole("heading", { name: "Profile setup" })
    ).toBeInTheDocument();
  });

  it("registers the holdings route", async () => {
    mockAuthState(mockSession);
    vi.mocked(getProfile).mockResolvedValue(mockProfile);
    vi.mocked(listHoldings).mockResolvedValue([]);
    renderRoute("/holdings");

    expect(
      await screen.findByRole("heading", { name: "Holdings" })
    ).toBeInTheDocument();
  });
});
