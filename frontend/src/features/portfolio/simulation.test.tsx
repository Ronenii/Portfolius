import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { searchInstruments } from "../instruments/instrument-search-api";
import { simulatePortfolio, type SimulationResponse } from "./portfolio-api";
import SimulationPanel from "./SimulationPanel";

vi.mock("../instruments/instrument-search-api", () => ({
  searchInstruments: vi.fn(),
}));

vi.mock("./portfolio-api", async () => {
  const actual =
    await vi.importActual<typeof import("./portfolio-api")>("./portfolio-api");
  return {
    ...actual,
    simulatePortfolio: vi.fn(),
  };
});

const simulationResponse: SimulationResponse = {
  current: {
    asset_class: [],
    country: [],
    currency: [],
    instrument: [
      {
        currency: "USD",
        dimension: "instrument",
        label: "VOO",
        market_value: "1000",
        percent: "100",
        position_count: 1,
        unit_quantity: "2",
      },
    ],
    region: [],
    sector: [],
    unpriced_holding_count: 0,
  },
  simulated: {
    asset_class: [],
    country: [],
    currency: [],
    instrument: [
      {
        currency: "USD",
        dimension: "instrument",
        label: "VOO",
        market_value: "500",
        percent: "50",
        position_count: 1,
        unit_quantity: "1",
      },
      {
        currency: "USD",
        dimension: "instrument",
        label: "QQQ",
        market_value: "500",
        percent: "50",
        position_count: 1,
        unit_quantity: "1",
      },
    ],
    region: [],
    sector: [],
    unpriced_holding_count: 0,
  },
  delta: [
    {
      currency: "USD",
      dimension: "instrument",
      label: "VOO",
      percent_after: "50",
      percent_before: "100",
      percent_change: "-50",
    },
    {
      currency: "USD",
      dimension: "instrument",
      label: "QQQ",
      percent_after: "50",
      percent_before: "0.00",
      percent_change: "50",
    },
  ],
  warnings: ["Sell for VOO capped at held quantity 2."],
};

function renderPanel() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <SimulationPanel accessToken="access-token" />
    </QueryClientProvider>
  );
}

describe("SimulationPanel", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(searchInstruments).mockResolvedValue([
      {
        asset_class: "ETF",
        country: "United States",
        currency: "USD",
        exchange: "NASDAQ",
        name: "Invesco QQQ Trust",
        region: "North America",
        sector: "Technology",
        source: "local",
        symbol: "QQQ",
      },
    ]);
    vi.mocked(simulatePortfolio).mockResolvedValue(simulationResponse);
  });

  it("adds a buy leg and calls the simulate API with the basket", async () => {
    renderPanel();

    await userEvent.selectOptions(screen.getByLabelText("Action"), "buy");
    await userEvent.type(screen.getByLabelText("Symbol"), "QQ");
    await userEvent.click(await screen.findByRole("option", { name: /QQQ/ }));
    await userEvent.type(screen.getByLabelText("Quantity"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Add leg" }));
    await userEvent.click(screen.getByRole("button", { name: "Simulate" }));

    await waitFor(() => {
      expect(simulatePortfolio).toHaveBeenCalledWith("access-token", [
        {
          action: "buy",
          price: null,
          quantity: "2",
          symbol: "QQQ",
        },
      ]);
    });
  });

  it("renders before after and change rows for the selected dimension", async () => {
    renderPanel();

    await userEvent.type(screen.getByLabelText("Symbol"), "QQQ");
    await userEvent.type(screen.getByLabelText("Quantity"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Add leg" }));
    await userEvent.click(screen.getByRole("button", { name: "Simulate" }));

    const table = await screen.findByRole("table", { name: "Simulation delta" });

    expect(within(table).getByRole("cell", { name: "VOO" })).toBeInTheDocument();
    expect(within(table).getByRole("cell", { name: "100%" })).toBeInTheDocument();
    expect(within(table).getAllByRole("cell", { name: "50%" })).toHaveLength(3);
    expect(within(table).getByRole("cell", { name: "-50%" })).toBeInTheDocument();
    expect(within(table).getByRole("cell", { name: "QQQ" })).toBeInTheDocument();
  });

  it("marks the simulation dimension control for mobile overflow styling", async () => {
    renderPanel();

    await userEvent.type(screen.getByLabelText("Symbol"), "QQQ");
    await userEvent.type(screen.getByLabelText("Quantity"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Add leg" }));
    await userEvent.click(screen.getByRole("button", { name: "Simulate" }));

    const dimensionControl = await screen.findByLabelText("Simulation dimension");

    expect(dimensionControl).toHaveClass("simulation-dimension-control");
  });

  it("displays warnings from the simulation response", async () => {
    renderPanel();

    await userEvent.type(screen.getByLabelText("Symbol"), "VOO");
    await userEvent.type(screen.getByLabelText("Quantity"), "5");
    await userEvent.click(screen.getByRole("button", { name: "Add leg" }));
    await userEvent.click(screen.getByRole("button", { name: "Simulate" }));

    expect(
      await screen.findByText("Sell for VOO capped at held quantity 2.")
    ).toBeInTheDocument();
  });

  it("disables simulation when there are no legs", async () => {
    renderPanel();

    const simulateButton = screen.getByRole("button", { name: "Simulate" });
    expect(simulateButton).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Symbol"), "QQQ");
    await userEvent.type(screen.getByLabelText("Quantity"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Add leg" }));
    expect(simulateButton).toBeEnabled();

    await userEvent.click(screen.getByRole("button", { name: "Remove QQQ buy leg" }));
    expect(simulateButton).toBeDisabled();
  });
});
