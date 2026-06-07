import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import InstrumentSearchInput from "./InstrumentSearchInput";
import { searchInstruments, type InstrumentSearchResult } from "./instrument-search-api";

vi.mock("./instrument-search-api", async () => {
  const actual = await vi.importActual<typeof import("./instrument-search-api")>(
    "./instrument-search-api"
  );
  return {
    ...actual,
    searchInstruments: vi.fn(),
  };
});

const indaResult: InstrumentSearchResult = {
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

function renderSearchInput(onSelect = vi.fn()) {
  return {
    onSelect,
    ...render(
      <QueryClientProvider client={createQueryClient()}>
        <InstrumentSearchInput
          accessToken="access-token"
          id="instrument-search"
          label="Symbol"
          value=""
          onChange={vi.fn()}
          onSelect={onSelect}
        />
      </QueryClientProvider>
    ),
  };
}

describe("InstrumentSearchInput", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("does not search for one-character input", async () => {
    vi.mocked(searchInstruments).mockResolvedValue([indaResult]);
    renderSearchInput();

    await userEvent.type(screen.getByLabelText("Symbol"), "I");

    await waitFor(() => {
      expect(searchInstruments).not.toHaveBeenCalled();
    });
  });

  it("waits for a 350ms debounce before searching", async () => {
    vi.useFakeTimers();
    vi.mocked(searchInstruments).mockResolvedValue([indaResult]);
    renderSearchInput();

    fireEvent.change(screen.getByLabelText("Symbol"), {
      target: { value: "VT" },
    });

    await act(async () => {
      vi.advanceTimersByTime(349);
      await Promise.resolve();
    });
    expect(searchInstruments).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(1);
      await Promise.resolve();
    });
    expect(searchInstruments).toHaveBeenCalledWith("access-token", "VT");
  });

  it("shows matching instruments and calls onSelect", async () => {
    vi.useFakeTimers();
    vi.mocked(searchInstruments).mockResolvedValue([indaResult]);
    const { onSelect } = renderSearchInput();

    fireEvent.change(screen.getByLabelText("Symbol"), {
      target: { value: "IND" },
    });
    await act(async () => {
      vi.advanceTimersByTime(350);
      await Promise.resolve();
    });
    fireEvent.click(screen.getByRole("option", { name: /INDA/i }));

    expect(searchInstruments).toHaveBeenCalledWith("access-token", "IND");
    expect(onSelect).toHaveBeenCalledWith(indaResult);
  });
});
