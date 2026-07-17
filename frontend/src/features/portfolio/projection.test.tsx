import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { ApiError } from "../../lib/api";
import { getProjection, type ProjectionResponse } from "./portfolio-api";
import ProjectionPanel from "./ProjectionPanel";

vi.mock("./portfolio-api", async () => {
  const actual =
    await vi.importActual<typeof import("./portfolio-api")>("./portfolio-api");
  return {
    ...actual,
    getProjection: vi.fn(),
  };
});

const projectionWithTarget: ProjectionResponse = {
  base_currency: "USD",
  start_value: "10000",
  target_amount: "50000",
  horizon_years: 10,
  contribution_amount: "500",
  contribution_frequency: "monthly",
  annual_return_expected: "6",
  series: [
    {
      year: 0,
      conservative: "10000",
      expected: "10000",
      optimistic: "10000",
      cost_basis: "9000",
    },
    {
      year: 1,
      conservative: "11000",
      expected: "11600",
      optimistic: "12200",
      cost_basis: "9500",
    },
  ],
  target_progress_percent: "20",
  on_track: true,
  target_reached_year: 2036,
};

const projectionWithoutGoal: ProjectionResponse = {
  ...projectionWithTarget,
  target_amount: null,
  target_progress_percent: null,
  on_track: null,
  target_reached_year: null,
};

function renderPanel() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <ProjectionPanel accessToken="access-token" />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ProjectionPanel", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the projection chart, progress bar, and on-track verdict when a target is set", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();

    expect(
      await screen.findByRole("img", { name: "Goal projection chart" })
    ).toBeInTheDocument();
    expect(screen.getByText(/20%/)).toBeInTheDocument();
    expect(screen.getByText(/On track/)).toBeInTheDocument();
    expect(screen.getByText(/2036/)).toBeInTheDocument();
  });

  it("shows a goal-setup prompt instead of a progress bar when no goal is set", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithoutGoal);

    renderPanel();

    expect(
      await screen.findByRole("img", { name: "Goal projection chart" })
    ).toBeInTheDocument();
    expect(
      screen.getByText("Set a goal target in your profile to track progress toward it.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/On track/)).not.toBeInTheDocument();
  });

  it("shows a profile setup prompt (not a generic error) on a 404", async () => {
    vi.mocked(getProjection).mockRejectedValue(new ApiError(404, "Not found"));

    renderPanel();

    expect(
      await screen.findByText("Create a profile to see your goal projection.")
    ).toBeInTheDocument();
    expect(screen.queryByText("Projection unavailable")).not.toBeInTheDocument();
  });

  it("shows a generic error state for non-404 failures", async () => {
    vi.mocked(getProjection).mockRejectedValue(new Error("Projection request failed."));

    renderPanel();

    expect(await screen.findByText("Projection unavailable")).toBeInTheDocument();
  });

  it("marks the horizon option matching the initial fetch as active", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();

    const activeButton = await screen.findByRole("button", { name: "10y" });
    expect(activeButton).toHaveAttribute("aria-pressed", "true");
  });

  it("refetches with a years override when a horizon option is clicked", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });
    expect(getProjection).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("button", { name: "5y" }));

    await waitFor(() => {
      expect(getProjection).toHaveBeenLastCalledWith("access-token", {
        years: 5,
      });
    });
  });

  it("debounces a contribution slider change into a committed override", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });
    expect(getProjection).toHaveBeenCalledTimes(1);

    const slider = screen.getByLabelText("Contribution amount");
    fireEvent.change(slider, { target: { value: "800" } });

    // Still debounced immediately after the change.
    expect(getProjection).toHaveBeenCalledTimes(1);

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 400));
    });

    await waitFor(() => {
      expect(getProjection).toHaveBeenLastCalledWith("access-token", {
        contribution: "800",
      });
    });
  });

  it("shows the computed expected annual return as static, non-editable text", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });

    expect(screen.getByText("6%")).toBeInTheDocument();
    expect(
      screen.queryByRole("slider", { name: "Expected annual return" })
    ).not.toBeInTheDocument();
  });

  it("shows a tooltip trigger explaining how the expected annual return is computed", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });

    expect(
      screen.getByRole("button", { name: "How is this calculated?" })
    ).toBeInTheDocument();
  });

  it("hides the reset control until an override is active, then reverts on click", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });

    expect(
      screen.queryByRole("button", { name: "Reset to my profile values" })
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "5y" }));

    const resetButton = await screen.findByRole("button", {
      name: "Reset to my profile values",
    });
    await userEvent.click(resetButton);

    await waitFor(() => {
      expect(getProjection).toHaveBeenLastCalledWith("access-token", {});
    });
    expect(
      screen.queryByRole("button", { name: "Reset to my profile values" })
    ).not.toBeInTheDocument();
  });

  it("shows an updating indicator while a background refetch is in flight", async () => {
    // The initial load resolves instantly, but the background refetch
    // triggered by the horizon click resolves on a real macrotask tick (as a
    // live network request would) so the transient "isFetching" render has a
    // window to be observed before `userEvent.click` settles.
    let callCount = 0;
    vi.mocked(getProjection).mockImplementation(() => {
      callCount += 1;
      if (callCount === 1) {
        return Promise.resolve(projectionWithTarget);
      }
      return new Promise((resolve) => {
        setTimeout(() => resolve(projectionWithTarget), 20);
      });
    });

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });
    expect(screen.queryByText("Updating…")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "5y" }));

    expect(await screen.findByText("Updating…")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("Updating…")).not.toBeInTheDocument();
    });
  });
});
