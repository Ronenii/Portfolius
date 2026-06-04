import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "./query-client";
import { createAppRouter } from "./router";

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
  beforeEach(() => {
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
    renderRoute("/");

    expect(
      screen.getByRole("heading", { name: "Dashboard" })
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Backend healthy")).toBeInTheDocument();
    });
    expect(screen.getByText(/\/healthz$/)).toBeInTheDocument();
  });

  it("registers the login route", () => {
    renderRoute("/login");

    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("registers the profile setup route", () => {
    renderRoute("/profile/setup");

    expect(
      screen.getByRole("heading", { name: "Profile setup" })
    ).toBeInTheDocument();
  });

  it("registers the holdings route", () => {
    renderRoute("/holdings");

    expect(screen.getByRole("heading", { name: "Holdings" })).toBeInTheDocument();
  });
});
