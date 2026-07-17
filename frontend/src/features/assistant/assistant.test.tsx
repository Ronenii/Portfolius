import type { Session } from "@supabase/supabase-js";
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
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
import ChatMessageList, { type ThreadMessage } from "./ChatMessageList";

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
  goal_target_amount: null,
  contribution_amount: null,
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

  it("renders a price check tool badge", async () => {
    vi.mocked(sendAssistantMessage).mockResolvedValue({
      conversation_id: 8,
      title: "ETF ideas",
      reply: "IEMG and VGK are priced options to compare.",
      used_tools: ["get_instrument_prices"],
    });
    renderAssistantRoute();
    await openAssistant();

    await userEvent.type(await screen.findByLabelText("Message"), "What ETFs?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(
      await screen.findByText("IEMG and VGK are priced options to compare.")
    ).toBeInTheDocument();
    expect(screen.getByText("checked prices")).toBeInTheDocument();
  });

  it("keeps tool badges after the saved conversation replaces optimistic messages", async () => {
    vi.mocked(sendAssistantMessage).mockResolvedValue({
      conversation_id: 8,
      title: "What if I buy VXUS?",
      reply: "That would add international exposure.",
      used_tools: ["simulate_trades"],
    });
    vi.mocked(getConversation).mockResolvedValue({
      id: 8,
      title: "What if I buy VXUS?",
      created_at: "2026-06-08T10:00:00Z",
      updated_at: "2026-06-08T10:00:01Z",
      messages: [
        {
          id: 10,
          role: "user",
          content: "What if I buy VXUS?",
          created_at: "2026-06-08T10:00:00Z",
        },
        {
          id: 11,
          role: "assistant",
          content: "That would add international exposure.",
          created_at: "2026-06-08T10:00:01Z",
        },
      ],
    });
    renderAssistantRoute();
    await openAssistant();

    await userEvent.type(
      await screen.findByLabelText("Message"),
      "What if I buy VXUS?"
    );
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(getConversation).toHaveBeenCalledWith("access-token", 8);
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

  it("shows a tool badge for leaked function call markup in saved messages", async () => {
    vi.mocked(listConversations).mockResolvedValue([conversationSummary]);
    vi.mocked(getConversation).mockResolvedValue({
      ...conversationDetail,
      messages: [
        conversationDetail.messages[0],
        {
          id: 3,
          role: "assistant",
          content:
            "You could consider broad international ETFs. <function=get_portfolio_breakdowns></function>",
          created_at: "2026-06-08T10:00:02Z",
        },
      ],
    });
    renderAssistantRoute();
    await openAssistant();

    await userEvent.click(
      await screen.findByRole("button", { name: "Conversation history" })
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Regional exposure" })
    );

    const thread = await screen.findByRole("log", { name: "Assistant thread" });
    expect(
      within(thread).getByText("You could consider broad international ETFs.")
    ).toBeInTheDocument();
    expect(within(thread).getByText("checked allocation")).toBeInTheDocument();
    expect(within(thread).queryByText(/function=get_portfolio_breakdowns/)).not.toBeInTheDocument();
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

    expect(screen.getByRole("status", { name: "Thinking" })).toBeInTheDocument();
    await act(async () => {
      resolveReply({
        conversation_id: 8,
        title: "Check this",
        reply: "Here is the analysis.",
        used_tools: [],
      });
    });
    expect(await screen.findByText("Here is the analysis.")).toBeInTheDocument();
  });

  it("keeps the sent thread visible while the saved conversation reloads", async () => {
    let resolveReply: (
      value: Awaited<ReturnType<typeof sendAssistantMessage>>
    ) => void = () => undefined;
    vi.mocked(sendAssistantMessage).mockReturnValue(
      new Promise((resolve) => {
        resolveReply = resolve;
      })
    );
    vi.mocked(getConversation).mockReturnValue(new Promise(() => undefined));
    renderAssistantRoute();
    await openAssistant();

    await userEvent.type(await screen.findByLabelText("Message"), "Check this");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await act(async () => {
      resolveReply({
        conversation_id: 8,
        title: "Check this",
        reply: "Here is the analysis.",
        used_tools: [],
      });
    });

    expect(await screen.findByText("Here is the analysis.")).toBeInTheDocument();
    expect(screen.getByText("Check this")).toBeInTheDocument();
    expect(screen.queryByText("Loading conversation")).not.toBeInTheDocument();
  });
});

describe("ChatMessageList markdown rendering", () => {
  afterEach(() => {
    cleanup();
  });

  function msg(content: string): ThreadMessage {
    return { id: 1, role: "assistant", content, created_at: "2026-06-15T00:00:00Z" };
  }

  it("renders **bold** as <strong>, not literal asterisks", () => {
    render(<ChatMessageList messages={[msg("North America is **66%** of your portfolio.")]} />);
    // No literal asterisks should appear in the rendered output
    expect(document.body.textContent).not.toContain("**");
    // The <strong> must exist inside the assistant bubble
    const bubble = document.querySelector(".assistant-message--assistant");
    const strong = bubble?.querySelector("strong");
    expect(strong).not.toBeNull();
    expect(strong?.textContent).toBe("66%");
  });

  it("renders a bullet list as <li> elements, not raw hyphens", () => {
    render(
      <ChatMessageList
        messages={[msg("Steps:\n- Buy VWO\n- Buy IEUR")]}
      />
    );
    const items = document.querySelectorAll("li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("Buy VWO");
    expect(items[1].textContent).toBe("Buy IEUR");
  });

  it("strips <function=...> markup before markdown rendering", () => {
    render(
      <ChatMessageList
        messages={[
          msg("Checking your mix. <function=get_portfolio_breakdowns></function>"),
        ]}
      />
    );
    const text = screen.getByText("Checking your mix.");
    expect(text).toBeInTheDocument();
    expect(text.textContent).not.toContain("<function=");
  });
});
