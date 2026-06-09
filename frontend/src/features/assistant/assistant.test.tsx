import type { Session } from "@supabase/supabase-js";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { createAppRouter } from "../../app/router";
import { ApiError } from "../../lib/api";
import { supabase } from "../../lib/supabase";
import { getProfile } from "../profile/profile-api";
import {
  getConversation,
  listConversations,
  sendAssistantMessage,
  type AssistantConversation,
  type AssistantConversationDetail,
} from "./assistant-api";

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

vi.mock("./assistant-api", () => ({
  getConversation: vi.fn(),
  listConversations: vi.fn(),
  sendAssistantMessage: vi.fn(),
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

const conversationSummary: AssistantConversation = {
  id: 7,
  title: "Regional exposure",
  created_at: "2026-06-08T10:00:00Z",
  updated_at: "2026-06-08T10:00:00Z",
};

const conversationDetail: AssistantConversationDetail = {
  ...conversationSummary,
  messages: [
    {
      id: 1,
      role: "user",
      content: "How regional am I?",
      created_at: "2026-06-08T10:00:00Z",
    },
    {
      id: 2,
      role: "assistant",
      content: "You are mostly US-weighted today.",
      created_at: "2026-06-08T10:00:01Z",
    },
  ],
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

function renderAssistantRoute() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider
        router={createAppRouter(["/dashboard"])}
        future={{ v7_startTransition: true }}
      />
    </QueryClientProvider>
  );
}

async function openAssistant() {
  await userEvent.click(await screen.findByRole("button", { name: "Open assistant" }));
}

describe("assistant page", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    mockAuthState();
    vi.mocked(getProfile).mockResolvedValue(mockProfile);
    vi.mocked(listConversations).mockResolvedValue([]);
    vi.mocked(sendAssistantMessage).mockResolvedValue({
      conversation_id: 8,
      title: "What if I buy VXUS?",
      reply: "That would add international exposure.",
      used_tools: ["simulate_trades"],
    });
    vi.mocked(getConversation).mockResolvedValue(conversationDetail);
  });

  it("sends a message and renders the assistant reply with tool grounding", async () => {
    renderAssistantRoute();
    await openAssistant();

    await userEvent.type(
      await screen.findByLabelText("Message"),
      "What if I buy VXUS?"
    );
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(sendAssistantMessage).toHaveBeenCalledWith("access-token", {
        message: "What if I buy VXUS?",
      });
    });
    expect(
      await screen.findByText("That would add international exposure.")
    ).toBeInTheDocument();
    expect(screen.getByText("ran a simulation")).toBeInTheDocument();
  });

  it("renders assistant not configured when the API returns 503", async () => {
    vi.mocked(sendAssistantMessage).mockRejectedValue(
      new ApiError(503, "Assistant is not configured")
    );
    renderAssistantRoute();
    await openAssistant();

    await userEvent.type(await screen.findByLabelText("Message"), "Analyze this");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Assistant is not configured")).toBeInTheDocument();
  });

  it("loads a selected past conversation", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversationSummary]);
    renderAssistantRoute();
    await openAssistant();

    await userEvent.click(
      await screen.findByRole("button", { name: "Conversation history" })
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Regional exposure" })
    );

    await waitFor(() => {
      expect(getConversation).toHaveBeenCalledWith("access-token", 7);
    });
    const thread = await screen.findByRole("log", { name: "Assistant thread" });
    expect(within(thread).getByText("How regional am I?")).toBeInTheDocument();
    expect(
      within(thread).getByText("You are mostly US-weighted today.")
    ).toBeInTheDocument();
  });

  it("marks the assistant widget for mobile sheet styling", async () => {
    renderAssistantRoute();
    await openAssistant();

    expect(screen.getByLabelText("Portfolio assistant")).toHaveClass(
      "assistant-mobile-sheet"
    );
  });

  it("shows a pending indicator while waiting for a reply", async () => {
    let resolveReply: (
      value: Awaited<ReturnType<typeof sendAssistantMessage>>
    ) => void = () => undefined;
    vi.mocked(sendAssistantMessage).mockReturnValue(
      new Promise((resolve) => {
        resolveReply = resolve;
      })
    );
    renderAssistantRoute();
    await openAssistant();

    await userEvent.type(await screen.findByLabelText("Message"), "Check this");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByText("Thinking")).toBeInTheDocument();
    resolveReply({
      conversation_id: 8,
      title: "Check this",
      reply: "Here is the analysis.",
      used_tools: [],
    });
    expect(await screen.findByText("Here is the analysis.")).toBeInTheDocument();
  });
});
