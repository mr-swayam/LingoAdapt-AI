import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MessageBubble } from "@/app/(app)/tutor/[conversationId]/page";
import * as tutorApi from "@/lib/tutor-api";
import type { ConversationMessage } from "@/types/conversation";

vi.mock("@/lib/tutor-api");

const tutorMessage: ConversationMessage = {
  id: "msg-1",
  role: "TUTOR",
  content: "Hola! Como estas?",
  created_at: new Date().toISOString(),
};

const learnerMessage: ConversationMessage = {
  ...tutorMessage,
  id: "msg-2",
  role: "LEARNER",
};

const fakeBlob = new Blob(["fake-audio"], { type: "audio/mpeg" });

describe("MessageBubble - tutor voice replies", () => {
  it("always shows the reply text regardless of audio state", () => {
    render(
      <MessageBubble message={tutorMessage} conversationId="conv-1" accessToken="token" />,
    );
    expect(screen.getByText("Hola! Como estas?")).toBeInTheDocument();
  });

  it("does not show a play button for the learner's own messages", () => {
    render(
      <MessageBubble message={learnerMessage} conversationId="conv-1" accessToken="token" />,
    );
    expect(screen.queryByRole("button", { name: /play tutor reply audio/i })).not.toBeInTheDocument();
  });

  it("fetches and plays audio on click, then offers Replay", async () => {
    vi.mocked(tutorApi.getMessageAudio).mockResolvedValue(fakeBlob);
    const user = userEvent.setup();
    render(
      <MessageBubble message={tutorMessage} conversationId="conv-1" accessToken="token" />,
    );

    await user.click(screen.getByRole("button", { name: "Play tutor reply audio" }));
    expect(await screen.findByRole("button", { name: "Replay tutor reply audio" })).toBeInTheDocument();
  });

  it("shows a visible error and keeps the text readable when the fetch fails", async () => {
    vi.mocked(tutorApi.getMessageAudio).mockRejectedValue(new Error("network error"));
    const user = userEvent.setup();
    render(
      <MessageBubble message={tutorMessage} conversationId="conv-1" accessToken="token" />,
    );

    await user.click(screen.getByRole("button", { name: "Play tutor reply audio" }));
    expect(await screen.findByText(/couldn't play audio/i)).toBeInTheDocument();
    expect(screen.getByText("Hola! Como estas?")).toBeInTheDocument();
  });

  it("shows a visible error when the device blocks programmatic playback", async () => {
    vi.mocked(tutorApi.getMessageAudio).mockResolvedValue(fakeBlob);
    vi.spyOn(HTMLMediaElement.prototype, "play").mockRejectedValueOnce(
      new DOMException("blocked", "NotAllowedError"),
    );
    const user = userEvent.setup();
    render(
      <MessageBubble message={tutorMessage} conversationId="conv-1" accessToken="token" />,
    );

    await user.click(screen.getByRole("button", { name: "Play tutor reply audio" }));
    expect(await screen.findByText(/couldn't play audio/i)).toBeInTheDocument();
  });
});
