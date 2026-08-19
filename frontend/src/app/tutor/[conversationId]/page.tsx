"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useRef, useState } from "react";

import { PrimaryButton, TextArea } from "@/components/ui/form";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { SCENARIO_ICONS, SCENARIO_LABELS } from "@/lib/scenario-labels";
import {
  ApiError,
  endConversation,
  getConversation,
  getMessageAudio,
  sendMessage,
  sendVoiceMessage,
} from "@/lib/tutor-api";
import type { Conversation, ConversationMessage, Correction } from "@/types/conversation";

export default function TutorConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = use(params);
  const { status, accessToken } = useRequireAuth();

  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [correctionsByMessageId, setCorrectionsByMessageId] = useState<
    Record<string, Correction[]>
  >({});
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [ending, setEnding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const recorder = useAudioRecorder();

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    let cancelled = false;
    getConversation(conversationId, accessToken)
      .then((detail) => {
        if (cancelled) return;
        setConversation(detail);
        setMessages(detail.messages);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Couldn't load this conversation.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [status, accessToken, conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function applySentMessage(result: {
    learner_message: ConversationMessage;
    tutor_message: ConversationMessage;
    corrections: Correction[];
  }) {
    setMessages((prev) => [...prev, result.learner_message, result.tutor_message]);
    if (result.corrections.length > 0) {
      setCorrectionsByMessageId((prev) => ({
        ...prev,
        [result.learner_message.id]: result.corrections,
      }));
    }
  }

  async function handleSend() {
    const text = draft.trim();
    if (!text || !accessToken || sending) return;
    setSending(true);
    setError(null);
    setDraft("");
    try {
      applySentMessage(await sendMessage(conversationId, text, accessToken));
    } catch (err) {
      setDraft(text);
      setError(err instanceof ApiError ? err.message : "Couldn't send that message.");
    } finally {
      setSending(false);
    }
  }

  async function handleSendVoice(audio: Blob) {
    if (!accessToken || sending) return;
    setSending(true);
    setError(null);
    try {
      applySentMessage(await sendVoiceMessage(conversationId, audio, accessToken));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send that recording.");
    } finally {
      setSending(false);
      recorder.reset();
    }
  }

  if (status !== "authenticated") {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  async function handleEnd() {
    if (!accessToken || ending) return;
    setEnding(true);
    setError(null);
    try {
      const ended = await endConversation(conversationId, accessToken);
      setConversation(ended);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't end this conversation.");
    } finally {
      setEnding(false);
    }
  }

  const isActive = conversation?.status === "ACTIVE";

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-8">
      <div className="flex w-full max-w-2xl flex-1 flex-col">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link href="/tutor" className="text-slate-400 hover:text-slate-300">
              ←
            </Link>
            {conversation && (
              <div className="flex items-center gap-2">
                <span className="text-xl">{SCENARIO_ICONS[conversation.scenario]}</span>
                <h1 className="text-lg font-semibold text-slate-50">
                  {SCENARIO_LABELS[conversation.scenario]}
                </h1>
              </div>
            )}
          </div>
          {isActive && (
            <PrimaryButton onClick={handleEnd} disabled={ending} variant="secondary">
              {ending ? "Ending…" : "End conversation"}
            </PrimaryButton>
          )}
        </div>

        {error && <p className="mb-3 text-sm text-red-300">{error}</p>}
        {recorder.error && <p className="mb-3 text-sm text-red-300">{recorder.error}</p>}

        {loading ? (
          <p className="text-sm text-slate-400">Loading conversation…</p>
        ) : (
          <div className="flex flex-1 flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
              {messages.length === 0 && (
                <p className="text-center text-sm text-slate-400">
                  Say something to start the conversation.
                </p>
              )}
              {messages.map((message) => (
                <div key={message.id}>
                  <MessageBubble
                    message={message}
                    conversationId={conversationId}
                    accessToken={accessToken ?? ""}
                  />
                  {correctionsByMessageId[message.id]?.map((correction, i) => (
                    <CorrectionNote key={i} correction={correction} />
                  ))}
                </div>
              ))}
              {sending && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-sm bg-slate-800 px-4 py-2 text-sm text-slate-400">
                    {recorder.state === "recorded" ? "Transcribing…" : "Typing…"}
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {conversation?.status === "ENDED" ? (
              <div className="rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-400">
                This conversation has ended.
                {conversation.summary && <span> {conversation.summary}</span>}
              </div>
            ) : recorder.state === "recorded" && recorder.audioBlob ? (
              <RecordingPreview
                audioBlob={recorder.audioBlob}
                sending={sending}
                onSend={() => handleSendVoice(recorder.audioBlob!)}
                onDiscard={recorder.reset}
              />
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend();
                }}
                className="flex items-end gap-2"
              >
                <TextArea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Type your message…"
                  rows={2}
                  maxLength={2000}
                  disabled={sending}
                  className="flex-1 resize-none"
                />
                <PrimaryButton
                  type="button"
                  disabled={sending}
                  onClick={recorder.state === "recording" ? recorder.stop : recorder.start}
                  variant={recorder.state === "recording" ? "danger" : "secondary"}
                >
                  {recorder.state === "recording" ? "⏹" : "🎤"}
                </PrimaryButton>
                <PrimaryButton type="submit" disabled={sending || !draft.trim()}>
                  Send
                </PrimaryButton>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function RecordingPreview({
  audioBlob,
  sending,
  onSend,
  onDiscard,
}: {
  audioBlob: Blob;
  sending: boolean;
  onSend: () => void;
  onDiscard: () => void;
}) {
  const audioUrl = useMemo(() => URL.createObjectURL(audioBlob), [audioBlob]);
  useEffect(() => {
    return () => URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  return (
    <div className="flex items-center gap-2">
      <audio controls src={audioUrl} className="h-10 flex-1" />
      <PrimaryButton type="button" disabled={sending} onClick={onDiscard} variant="secondary">
        Discard
      </PrimaryButton>
      <PrimaryButton type="button" disabled={sending} onClick={onSend}>
        {sending ? "Sending…" : "Send"}
      </PrimaryButton>
    </div>
  );
}

function MessageBubble({
  message,
  conversationId,
  accessToken,
}: {
  message: ConversationMessage;
  conversationId: string;
  accessToken: string;
}) {
  const isLearner = message.role === "LEARNER";
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loadingAudio, setLoadingAudio] = useState(false);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  async function handlePlay() {
    if (audioUrl || loadingAudio) return;
    setLoadingAudio(true);
    try {
      const blob = await getMessageAudio(conversationId, message.id, accessToken);
      setAudioUrl(URL.createObjectURL(blob));
    } catch {
      // Playback is a nice-to-have on top of the text reply - fail silently.
    } finally {
      setLoadingAudio(false);
    }
  }

  return (
    <div className={`flex items-end gap-2 ${isLearner ? "justify-end" : "justify-start"}`}>
      {!isLearner && (
        <button
          type="button"
          onClick={handlePlay}
          disabled={loadingAudio}
          title="Listen"
          className="shrink-0 rounded-full border border-slate-700 p-1.5 text-xs text-slate-400 transition-colors hover:border-cyan-600 hover:text-cyan-300 disabled:opacity-50"
        >
          {loadingAudio ? "…" : "🔊"}
        </button>
      )}
      <div
        className={
          "max-w-[80%] rounded-2xl px-4 py-2 text-sm " +
          (isLearner
            ? "rounded-br-sm bg-cyan-500 text-slate-950"
            : "rounded-bl-sm bg-slate-800 text-slate-100")
        }
      >
        {message.content}
      </div>
      {audioUrl && <audio controls autoPlay src={audioUrl} className="h-8 max-w-[140px]" />}
    </div>
  );
}

function CorrectionNote({ correction }: { correction: Correction }) {
  return (
    <div className="mt-1 flex justify-end">
      <div className="max-w-[80%] rounded-xl border border-amber-900/60 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
        <p>
          <span className="line-through opacity-70">{correction.original}</span>
          {" → "}
          <span className="font-medium">{correction.corrected}</span>
        </p>
        <p className="mt-1 text-amber-300/80">{correction.explanation}</p>
      </div>
    </div>
  );
}
