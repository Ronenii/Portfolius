import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, MessageCircle, SendHorizonal, SquarePen, X } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import { ApiError } from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import {
  getConversation,
  listConversations,
  sendAssistantMessage,
  type AssistantConversation,
  type AssistantConversationDetail,
} from "./assistant-api";
import ChatMessageList, { type ThreadMessage } from "./ChatMessageList";

function conversationMessages(
  selectedConversation: AssistantConversationDetail | undefined,
  optimisticMessages: ThreadMessage[]
): ThreadMessage[] {
  const real = selectedConversation?.messages ?? [];
  const realKeys = new Set(real.map((m) => `${m.role}\0${m.content}`));
  const deduped = optimisticMessages.filter(
    (m) => !m.content || !realKeys.has(`${m.role}\0${m.content}`)
  );
  return [...real, ...deduped];
}

function pendingUserMessage(content: string): ThreadMessage {
  return {
    id: Date.now() * -1,
    role: "user",
    content,
    created_at: new Date().toISOString(),
  };
}

function pendingAssistantMessage(): ThreadMessage {
  return {
    id: Date.now() * -1 - 1,
    role: "assistant",
    content: "",
    created_at: new Date().toISOString(),
    pending: true,
  };
}

function assistantReplyMessage(
  response: Awaited<ReturnType<typeof sendAssistantMessage>>
): ThreadMessage {
  return {
    id: Date.now() * -1 - 2,
    role: "assistant",
    content: response.reply,
    created_at: new Date().toISOString(),
    used_tools: response.used_tools,
  };
}

export default function AssistantWidget() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(
    null
  );
  const [message, setMessage] = useState("");
  const [optimisticMessages, setOptimisticMessages] = useState<ThreadMessage[]>([]);

  const conversationsQuery = useQuery({
    enabled: Boolean(accessToken && isOpen),
    queryKey: ["assistant-conversations", accessToken],
    queryFn: () => listConversations(accessToken ?? ""),
  });

  const selectedConversationQuery = useQuery({
    enabled: Boolean(accessToken && selectedConversationId),
    queryKey: ["assistant-conversation", accessToken, selectedConversationId],
    queryFn: () => getConversation(accessToken ?? "", selectedConversationId ?? 0),
  });

  const sendMutation = useMutation({
    mutationFn: (nextMessage: string) =>
      sendAssistantMessage(accessToken ?? "", {
        conversation_id: selectedConversationId ?? undefined,
        message: nextMessage,
      }),
    onMutate: (nextMessage) => {
      setOptimisticMessages([
        pendingUserMessage(nextMessage),
        pendingAssistantMessage(),
      ]);
    },
    onSuccess: async (response) => {
      setSelectedConversationId(response.conversation_id);
      setOptimisticMessages([assistantReplyMessage(response)]);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["assistant-conversations"] }),
        queryClient.invalidateQueries({
          queryKey: ["assistant-conversation", accessToken, response.conversation_id],
        }),
      ]);
    },
  });

  const threadMessages = useMemo(
    () => conversationMessages(selectedConversationQuery.data, optimisticMessages),
    [optimisticMessages, selectedConversationQuery.data]
  );

  function selectConversation(conversation: AssistantConversation) {
    setSelectedConversationId(conversation.id);
    setOptimisticMessages([]);
    setShowHistory(false);
  }

  function startNewChat() {
    setSelectedConversationId(null);
    setOptimisticMessages([]);
    setShowHistory(false);
    sendMutation.reset();
  }

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage || sendMutation.isPending) {
      return;
    }
    setMessage("");
    sendMutation.mutate(trimmedMessage);
  }

  const isNotConfigured =
    sendMutation.error instanceof ApiError && sendMutation.error.status === 503;

  if (!isOpen) {
    return (
      <button
        type="button"
        className="assistant-launcher"
        aria-label="Open assistant"
        onClick={() => setIsOpen(true)}
      >
        <MessageCircle aria-hidden="true" />
      </button>
    );
  }

  return (
    <section className="assistant-widget" aria-label="Portfolio assistant">
      <header className="assistant-widget-header">
        <div className="assistant-widget-identity">
          <span className="assistant-widget-avatar" aria-hidden="true">
            <MessageCircle />
          </span>
          <div>
            <p className="assistant-widget-title">Portfolio chat</p>
            <p className="assistant-widget-subtitle">Grounded in your holdings</p>
          </div>
        </div>
        <div className="assistant-widget-actions">
          <button
            type="button"
            className="assistant-icon-button"
            aria-label="Conversation history"
            aria-pressed={showHistory}
            onClick={() => setShowHistory((open) => !open)}
          >
            <History aria-hidden="true" />
          </button>
          <button
            type="button"
            className="assistant-icon-button"
            aria-label="New chat"
            onClick={startNewChat}
          >
            <SquarePen aria-hidden="true" />
          </button>
          <button
            type="button"
            className="assistant-icon-button"
            aria-label="Close assistant"
            onClick={() => setIsOpen(false)}
          >
            <X aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className="assistant-widget-body">
        {showHistory ? (
          <div className="assistant-history" aria-label="Conversations">
            {conversationsQuery.isLoading ? (
              <div className="empty-state assistant-empty">
                <strong>Loading conversations</strong>
                <span>Reading saved assistant threads.</span>
              </div>
            ) : null}
            {conversationsQuery.data?.length === 0 ? (
              <div className="empty-state assistant-empty">
                <strong>No conversations yet</strong>
                <span>Your first question will start one.</span>
              </div>
            ) : null}
            <div className="assistant-conversation-list">
              {(conversationsQuery.data ?? []).map((conversation) => (
                <button
                  className={
                    selectedConversationId === conversation.id
                      ? "assistant-conversation assistant-conversation--active"
                      : "assistant-conversation"
                  }
                  key={conversation.id}
                  type="button"
                  onClick={() => selectConversation(conversation)}
                >
                  {conversation.title}
                </button>
              ))}
            </div>
          </div>
        ) : selectedConversationQuery.isLoading ? (
          <div className="empty-state assistant-empty">
            <strong>Loading conversation</strong>
            <span>Reading saved messages.</span>
          </div>
        ) : (
          <ChatMessageList messages={threadMessages} />
        )}
      </div>

      {isNotConfigured ? (
        <p className="form-error assistant-widget-error" role="alert">
          Assistant is not configured
        </p>
      ) : null}
      {sendMutation.error && !isNotConfigured ? (
        <p className="form-error assistant-widget-error" role="alert">
          {sendMutation.error instanceof Error
            ? sendMutation.error.message
            : "Assistant request failed"}
        </p>
      ) : null}

      <form className="assistant-composer" onSubmit={submitMessage}>
        <label className="sr-only" htmlFor="assistant-message">
          Message
        </label>
        <textarea
          id="assistant-message"
          placeholder="Ask about your portfolio…"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <button
          type="submit"
          className="assistant-send-button"
          aria-label="Send"
          disabled={!message.trim() || sendMutation.isPending}
        >
          <SendHorizonal aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}
