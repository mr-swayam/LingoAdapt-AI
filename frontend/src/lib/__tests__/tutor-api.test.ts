import { afterEach, describe, expect, it, vi } from "vitest";

import {
  endConversation,
  getConversation,
  getMessageAudio,
  listConversations,
  sendMessage,
  sendVoiceMessage,
  startConversation,
} from "@/lib/tutor-api";

describe("tutor-api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("startConversation sends the scenario and returns the parsed conversation", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "c1", scenario: "RESTAURANT", status: "ACTIVE" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const conversation = await startConversation("RESTAURANT", "tok123");

    expect(conversation.id).toBe("c1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/tutor/conversations");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer tok123");
    expect(JSON.parse(init.body)).toEqual({ scenario: "RESTAURANT" });
  });

  it("listConversations returns the parsed list", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: "c1" }, { id: "c2" }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const conversations = await listConversations("tok123");

    expect(conversations).toHaveLength(2);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/tutor/conversations");
  });

  it("getConversation requests the specific conversation id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "c1", messages: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getConversation("c1", "tok123");

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/tutor/conversations/c1");
  });

  it("sendMessage posts the text and returns reply plus corrections", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        learner_message: { id: "m1" },
        tutor_message: { id: "m2" },
        corrections: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await sendMessage("c1", "hello there", "tok123");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/tutor/conversations/c1/messages");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ text: "hello there" });
  });

  it("sendVoiceMessage posts the audio as multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        learner_message: { id: "m1" },
        tutor_message: { id: "m2" },
        corrections: [],
        transcript: "hello there",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const audio = new Blob(["fake-audio"], { type: "audio/webm" });

    const result = await sendVoiceMessage("c1", audio, "tok123");

    expect(result.transcript).toBe("hello there");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/tutor/conversations/c1/voice-messages");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.headers["Content-Type"]).toBeUndefined(); // browser sets the multipart boundary
  });

  it("getMessageAudio requests the message's audio endpoint and returns a blob", async () => {
    const fakeBlob = new Blob(["fake-wav-bytes"], { type: "audio/wav" });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => fakeBlob,
    });
    vi.stubGlobal("fetch", fetchMock);

    const blob = await getMessageAudio("c1", "m2", "tok123");

    expect(blob).toBe(fakeBlob);
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/tutor/conversations/c1/messages/m2/audio");
  });

  it("endConversation posts to the end endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "c1", status: "ENDED" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const conversation = await endConversation("c1", "tok123");

    expect(conversation.status).toBe("ENDED");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/tutor/conversations/c1/end");
    expect(init.method).toBe("POST");
  });
});
