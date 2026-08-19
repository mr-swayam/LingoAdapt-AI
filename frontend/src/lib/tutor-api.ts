import { apiRequest, apiRequestBlob } from "@/lib/api-client";
import type {
  Conversation,
  ConversationDetail,
  ConversationScenario,
  SendMessageResponse,
  VoiceSendMessageResponse,
} from "@/types/conversation";

export { ApiError } from "@/lib/api-client";

export function startConversation(
  scenario: ConversationScenario,
  accessToken: string,
): Promise<Conversation> {
  return apiRequest("/tutor/conversations", {
    method: "POST",
    accessToken,
    body: JSON.stringify({ scenario }),
  });
}

export function listConversations(accessToken: string): Promise<Conversation[]> {
  return apiRequest("/tutor/conversations", { accessToken });
}

export function getConversation(
  conversationId: string,
  accessToken: string,
): Promise<ConversationDetail> {
  return apiRequest(`/tutor/conversations/${conversationId}`, { accessToken });
}

export function sendMessage(
  conversationId: string,
  text: string,
  accessToken: string,
): Promise<SendMessageResponse> {
  return apiRequest(`/tutor/conversations/${conversationId}/messages`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({ text }),
  });
}

export function sendVoiceMessage(
  conversationId: string,
  audio: Blob,
  accessToken: string,
): Promise<VoiceSendMessageResponse> {
  const form = new FormData();
  form.append("file", audio, "speech.webm");
  return apiRequest(`/tutor/conversations/${conversationId}/voice-messages`, {
    method: "POST",
    accessToken,
    body: form,
  });
}

export function getMessageAudio(
  conversationId: string,
  messageId: string,
  accessToken: string,
): Promise<Blob> {
  return apiRequestBlob(`/tutor/conversations/${conversationId}/messages/${messageId}/audio`, {
    accessToken,
  });
}

export function endConversation(
  conversationId: string,
  accessToken: string,
): Promise<Conversation> {
  return apiRequest(`/tutor/conversations/${conversationId}/end`, {
    method: "POST",
    accessToken,
  });
}
