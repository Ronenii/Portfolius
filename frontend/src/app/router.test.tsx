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
  created_at: "2026-06-04T00:00:00Z",
  updated_at: "2026-06-04T00:00:00Z",
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
