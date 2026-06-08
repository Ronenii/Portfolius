import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import type { Session } from "@supabase/supabase-js";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { createAppRouter } from "../../app/router";
import { supabase } from "../../lib/supabase";
import { getProfile } from "../profile/profile-api";

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

function mockAuthState(session: typeof mockSession | null) {
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
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider
        router={createAppRouter([path])}
        future={{ v7_startTransition: true }}
      />
    </QueryClientProvider>
  );
}

describe("auth flow", () => {
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

  it("calls Google OAuth when the Google button is pressed", async () => {
    mockAuthState(null);
    renderRoute("/login");

    await userEvent.click(
      await screen.findByRole("button", { name: "Continue with Google" })
    );

    expect(supabase.auth.signInWithOAuth).toHaveBeenCalledWith({
      provider: "google",
    });
  });

  it("calls magic-link sign-in with the typed email", async () => {
    mockAuthState(null);
    renderRoute("/login");

    await userEvent.type(
      await screen.findByLabelText("Email address"),
      "investor@example.com"
    );
    await userEvent.click(screen.getByRole("button", { name: "Send magic link" }));

    expect(supabase.auth.signInWithOtp).toHaveBeenCalledWith({
      email: "investor@example.com",
    });
  });

  it("keeps magic-link submit disabled for empty or invalid email", async () => {
    mockAuthState(null);
    renderRoute("/login");

    const emailInput = await screen.findByLabelText("Email address");
    const submitButton = screen.getByRole("button", { name: "Send magic link" });

    expect(submitButton).toBeDisabled();

    await userEvent.type(emailInput, "not-an-email");

    expect(submitButton).toBeDisabled();
  });

  it("does not show the login page to authenticated users", async () => {
    mockAuthState(mockSession);
    vi.mocked(getProfile).mockResolvedValue(mockProfile);
    renderRoute("/login");

    await waitFor(() => {
      expect(
        screen.queryByRole("heading", { name: "Sign in" })
      ).not.toBeInTheDocument();
    });
    expect(
      await screen.findByRole("heading", { name: "Dashboard" })
    ).toBeInTheDocument();
  });

  it("routes unauthenticated users to login", async () => {
    mockAuthState(null);
    renderRoute("/");

    expect(
      await screen.findByRole("heading", { name: "Sign in" })
    ).toBeInTheDocument();
  });
});
