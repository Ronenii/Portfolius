import type { Session } from "@supabase/supabase-js";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { createAppRouter } from "../../app/router";
import { supabase } from "../../lib/supabase";
import { getProfile } from "../profile/profile-api";
import { importTransactions, type ImportResponse } from "./transactions-api";

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

vi.mock("./transactions-api", () => ({
  listTransactions: vi.fn(),
  createTransaction: vi.fn(),
  updateTransaction: vi.fn(),
  deleteTransaction: vi.fn(),
  importTransactions: vi.fn(),
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

function renderImportRoute() {
  const queryClient = createQueryClient();
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider
        router={createAppRouter(["/transactions/import"])}
        future={{ v7_startTransition: true }}
      />
    </QueryClientProvider>
  );
  return { ...rendered, queryClient };
}

function csvFile(text: string, name = "transactions.csv") {
  return new File([text], name, { type: "text/csv" });
}

async function uploadFile(text: string, name?: string) {
  const input = screen.getByLabelText(/drag and drop a csv file/i);
  await userEvent.upload(input, csvFile(text, name));
}

describe("import page", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    mockAuthState();
    vi.mocked(getProfile).mockResolvedValue(mockProfile);
  });

  it("renders a preview with valid and invalid rows flagged after uploading a transactions CSV", async () => {
    renderImportRoute();
    await screen.findByRole("heading", { name: "Import CSV" });

    const csv =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,buy,AAPL,10,145.20,1.50,Initial buy\n" +
      "2026-01-06,buy,TSLA,abc,180.00,0,\n";
    await uploadFile(csv);

    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
    expect(
      screen.getByText(/Quantity must be a number greater than 0/)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import 1 valid row" })
    ).toBeInTheDocument();
  });

  it("imports only the valid rows, in order, when the import action is clicked", async () => {
    vi.mocked(importTransactions).mockResolvedValue({
      results: [{ row: 1, status: "imported", reason: null }],
    });
    renderImportRoute();
    await screen.findByRole("heading", { name: "Import CSV" });

    const csv =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,buy,AAPL,10,145.20,1.50,Initial buy\n" +
      "2026-01-06,buy,TSLA,abc,180.00,0,\n";
    await uploadFile(csv);

    await userEvent.click(
      await screen.findByRole("button", { name: "Import 1 valid row" })
    );

    await waitFor(() => {
      expect(importTransactions).toHaveBeenCalledWith("access-token", [
        {
          symbol: "AAPL",
          action: "buy",
          quantity: "10",
          price: "145.20",
          fees: "1.50",
          trade_date: "2026-01-05",
          notes: "Initial buy",
        },
      ]);
    });
  });

  it("disables the import action after a successful import so the same rows cannot be re-submitted", async () => {
    vi.mocked(importTransactions).mockResolvedValue({
      results: [{ row: 1, status: "imported", reason: null }],
    });
    renderImportRoute();
    await screen.findByRole("heading", { name: "Import CSV" });

    const csv =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,buy,AAPL,10,145.20,1.50,Initial buy\n";
    await uploadFile(csv);

    await userEvent.click(
      await screen.findByRole("button", { name: "Import 1 valid row" })
    );

    // Once the import succeeds the action is disabled (the backend is not
    // idempotent, so a re-click would double the transactions).
    const doneButton = await screen.findByRole("button", {
      name: /load a new file to import again/i,
    });
    expect(doneButton).toBeDisabled();

    await userEvent.click(doneButton);
    expect(importTransactions).toHaveBeenCalledTimes(1);
  });

  it("reports a partial success without blocking the imported row", async () => {
    const response: ImportResponse = {
      results: [
        { row: 1, status: "imported", reason: null },
        { row: 2, status: "failed", reason: "Cannot sell 5 units; only 2 held." },
      ],
    };
    vi.mocked(importTransactions).mockResolvedValue(response);
    renderImportRoute();
    await screen.findByRole("heading", { name: "Import CSV" });

    const csv =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,buy,AAPL,10,145.20,1.50,Initial buy\n" +
      "2026-01-06,sell,TSLA,5,180.00,0,\n";
    await uploadFile(csv);

    await userEvent.click(
      await screen.findByRole("button", { name: "Import 2 valid rows" })
    );

    expect(
      await screen.findByText(/Cannot sell 5 units; only 2 held\./)
    ).toBeInTheDocument();
    expect(await screen.findByText(/1 imported, 1 failed/)).toBeInTheDocument();
  });

  it("maps a positions-template CSV to opening-balance buy rows dated today", async () => {
    vi.mocked(importTransactions).mockResolvedValue({
      results: [{ row: 1, status: "imported", reason: null }],
    });
    renderImportRoute();
    await screen.findByRole("heading", { name: "Import CSV" });

    const csv = "symbol,quantity,average_cost\n" + "MSFT,5,300.00\n";
    await uploadFile(csv);

    await userEvent.click(
      await screen.findByRole("button", { name: "Import 1 valid row" })
    );

    const today = new Date().toISOString().slice(0, 10);
    await waitFor(() => {
      expect(importTransactions).toHaveBeenCalledWith("access-token", [
        {
          symbol: "MSFT",
          action: "buy",
          quantity: "5",
          price: "300.00",
          fees: "0",
          trade_date: today,
          notes: null,
        },
      ]);
    });
  });
});
