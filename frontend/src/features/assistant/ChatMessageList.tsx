import { Wrench } from "lucide-react";
import { useEffect, useRef } from "react";

import { TypewriterText } from "../../components/ui/TypewriterText";
import { TypingDots } from "../../components/ui/TypingDots";
import type { AssistantMessage } from "./assistant-api";

export type ThreadMessage = AssistantMessage & {
  pending?: boolean;
  used_tools?: string[];
};

const inlineFunctionCallPattern = /\s*<function=([^>]+)>.*?<\/function>\s*/gs;

function displayContent(content: string) {
  return content.replace(inlineFunctionCallPattern, "").trim();
}

function inlineTools(content: string) {
  return [...content.matchAll(inlineFunctionCallPattern)].map((match) => match[1]);
}

function messageTools(message: ThreadMessage) {
  return [...new Set([...(message.used_tools ?? []), ...inlineTools(message.content)])];
}

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
  if (tools.includes("get_instrument_prices")) {
    return "checked prices";
  }
  return `used ${tools.length} tool${tools.length === 1 ? "" : "s"}`;
}

export default function ChatMessageList({
  messages,
}: {
  messages: ThreadMessage[];
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll to the latest message whenever a new one is appended.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

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
        const tools = toolCopy(messageTools(message));
        const cleaned = displayContent(message.content);

        return (
          <article
            className={`assistant-message assistant-message--${message.role}`}
            key={message.id}
          >
            <p className="assistant-message-role">
              {message.role === "user" ? "You" : "Assistant"}
            </p>

            {message.pending ? (
              <TypingDots />
            ) : message.role === "assistant" ? (
              // TypewriterText animates once on mount (empty useEffect deps) and
              // then shows full text forever. Key stability via message.id means
              // it only re-mounts when a distinct message arrives.
              <TypewriterText text={cleaned} />
            ) : (
              <p>{cleaned}</p>
            )}

            {tools ? (
              <span className="assistant-tool-badge">
                <Wrench aria-hidden="true" />
                {tools}
              </span>
            ) : null}
          </article>
        );
      })}
      <div ref={bottomRef} aria-hidden="true" />
    </div>
  );
}
