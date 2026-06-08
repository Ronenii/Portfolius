import { Wrench } from "lucide-react";

import type { AssistantMessage } from "./assistant-api";

export type ThreadMessage = AssistantMessage & {
  pending?: boolean;
  used_tools?: string[];
};

function toolCopy(tools: string[] | undefined) {
  if (!tools || tools.length === 0) {
    return null;
  }
  if (tools.includes("simulate_trades")) {
    return "ran a simulation";
  }
  if (tools.includes("get_portfolio_breakdowns")) {
    return "checked allocation";
  }
  return `used ${tools.length} tool${tools.length === 1 ? "" : "s"}`;
}

export default function ChatMessageList({
  messages,
}: {
  messages: ThreadMessage[];
}) {
  if (messages.length === 0) {
    return (
      <div className="empty-state assistant-empty">
        <strong>No messages yet</strong>
        <span>Ask a portfolio question to start a grounded conversation.</span>
      </div>
    );
  }

  return (
    <div className="assistant-thread" role="log" aria-label="Assistant thread">
      {messages.map((message) => {
        const tools = toolCopy(message.used_tools);
        return (
          <article
            className={`assistant-message assistant-message--${message.role}`}
            key={message.id}
          >
            <p className="assistant-message-role">
              {message.role === "user" ? "You" : "Assistant"}
            </p>
            <p>{message.content}</p>
            {message.pending ? <span className="assistant-pending">Thinking</span> : null}
            {tools ? (
              <span className="assistant-tool-badge">
                <Wrench aria-hidden="true" />
                {tools}
              </span>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
