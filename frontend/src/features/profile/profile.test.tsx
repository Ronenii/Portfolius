import type { Session } from "@supabase/supabase-js";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { createAppRouter } from "../../app/router";
import { ApiError } from "../../lib/api";
import { supabase } from "../../lib/supabase";
import { getProfile, saveProfile } from "./profile-api";

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

vi.mock("./profile-api", () => ({
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

const savedProfile = {
  id: 1,
  user_id: "user-123",
  display_name: "Ronen",
  base_currency: "USD",
  time_horizon: "10+ years",
  investment_frequency: "monthly",
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

async function fillProfileForm() {
  await userEvent.type(await screen.findByLabelText("Display name"), "Ronen");
  await userEvent.selectOptions(screen.getByLabelText("Base currency"), "USD");
  await userEvent.selectOptions(screen.getByLabelText("Time horizon"), "10+ years");
  await userEvent.selectOptions(
    screen.getByLabelText("Investment frequency"),
    "monthly"
  );
}

describe("profile wizard", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    mockAuthState();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), {
          headers: { "Content-Type": "application/json" },
        })
      )
    );
  });

  it("routes missing profiles to setup", async () => {
    vi.mocked(getProfile).mockRejectedValue(new ApiError(404, "Profile not found"));

    renderRoute("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Profile setup" })
    ).toBeInTheDocument();
  });

  it("calls saveProfile with the completed form payload", async () => {
    vi.mocked(getProfile).mockRejectedValue(new ApiError(404, "Profile not found"));
    vi.mocked(saveProfile).mockResolvedValue(savedProfile);
    renderRoute("/profile/setup");

    await fillProfileForm();
    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => {
      expect(saveProfile).toHaveBeenCalledWith("access-token", {
        display_name: "Ronen",
        base_currency: "USD",
        time_horizon: "10+ years",
        investment_frequency: "monthly",
      });
    });
  });

  it("routes to dashboard after a successful save", async () => {
    vi.mocked(getProfile).mockRejectedValue(new ApiError(404, "Profile not found"));
    vi.mocked(saveProfile).mockResolvedValue(savedProfile);
    renderRoute("/profile/setup");

    await fillProfileForm();
    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));

    expect(
      await screen.findByRole("heading", { name: "Dashboard" })
    ).toBeInTheDocument();
  });

  it("disables submit while saving", async () => {
    vi.mocked(getProfile).mockRejectedValue(new ApiError(404, "Profile not found"));
    vi.mocked(saveProfile).mockReturnValue(new Promise(() => undefined));
    renderRoute("/profile/setup");

    await fillProfileForm();
    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));

    expect(screen.getByRole("button", { name: "Saving profile" })).toBeDisabled();
  });

  it("prevents submission with invalid required fields", async () => {
    vi.mocked(getProfile).mockRejectedValue(new ApiError(404, "Profile not found"));
    renderRoute("/profile/setup");

    await userEvent.click(await screen.findByRole("button", { name: "Save profile" }));

    expect(saveProfile).not.toHaveBeenCalled();
    expect(screen.getByText("Display name is required")).toBeInTheDocument();
  });
});
