import { apiRequest } from "../../lib/api";

export type AssistantMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type AssistantConversation = {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
};

export type AssistantConversationDetail = AssistantConversation & {
  messages: AssistantMessage[];
};

export type SendAssistantMessagePayload = {
  conversation_id?: number;
  message: string;
};

export type SendAssistantMessageResponse = {
  conversation_id: number;
  title: string;
  reply: string;
  used_tools: string[];
};

export function sendAssistantMessage(
  accessToken: string,
  payload: SendAssistantMessagePayload
) {
  return apiRequest<SendAssistantMessageResponse>("/api/v1/assistant/messages", {
    accessToken,
    body: payload,
    method: "POST",
  });
}

export function listConversations(accessToken: string) {
  return apiRequest<AssistantConversation[]>("/api/v1/assistant/conversations", {
    accessToken,
  });
}

export function getConversation(accessToken: string, conversationId: number) {
  return apiRequest<AssistantConversationDetail>(
    `/api/v1/assistant/conversations/${conversationId}`,
    { accessToken }
  );
}
