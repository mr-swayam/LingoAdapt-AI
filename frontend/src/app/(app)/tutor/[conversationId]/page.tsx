"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { use, useEffect, useMemo, useRef, useState } from "react";

import { PrimaryButton, TextArea } from "@/components/ui/form";
import { SkeletonText } from "@/components/ui/Skeleton";
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
      <div className="flex flex-1 flex-col items-center px-6 py-8">
        <div className="w-full max-w-2xl">
          <SkeletonText lines={4} />
        </div>
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
          <SkeletonText lines={4} />
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
                  <div className="flex items-center gap-2 rounded-2xl rounded-bl-sm bg-slate-800 px-4 py-2.5 text-sm text-slate-400">
                    <TypingDots />
                    <span className="sr-only">
                      {recorder.state === "recorded" ? "Transcribing" : "Tutor is typing"}
                    </span>
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

/** Replaces the previous static "Typing…"/"Transcribing…" text with an
 * animated indicator - design.md §9 calls for one explicitly. The actual
 * status is still conveyed to screen readers via the sr-only text next to
 * this in the caller; these dots are decorative only. */
function TypingDots() {
  const reduceMotion = useReducedMotion();
  return (
    <span className="flex gap-1" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-slate-400"
          animate={reduceMotion ? { opacity: 0.6 } : { opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
        />
      ))}
    </span>
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

type AudioState = "idle" | "loading" | "playing" | "paused" | "error";

/** Text is always shown regardless of this state - voice playback is
 * strictly additive, so any audio failure here must never hide or block
 * the reply text above it. Exported (rather than a page-local function) so
 * its play/pause/replay/error state machine can be unit-tested directly. */
export function MessageBubble({
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
  const [audioState, setAudioState] = useState<AudioState>("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  async function handlePlayPause() {
    if (audioState === "playing") {
      audioRef.current?.pause();
      setAudioState("paused");
      return;
    }
    if (audioState === "paused" && audioRef.current) {
      try {
        await audioRef.current.play();
        setAudioState("playing");
      } catch {
        setAudioState("error");
      }
      return;
    }
    if (audioState === "loading") return; // in-flight fetch already covers this click

    setAudioState("loading");
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const blob = await getMessageAudio(conversationId, message.id, accessToken);
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      // Wait a tick for the <audio> element to mount with the new src.
      requestAnimationFrame(async () => {
        const el = audioRef.current;
        if (!el) return;
        el.playbackRate = 1.0; // sensible, explicit default - never sped up/slowed silently
        try {
          await el.play();
          setAudioState("playing");
        } catch {
          // Browser/device blocked programmatic playback (autoplay policy) -
          // the user can still press play again via the native control, or
          // just keep reading the text, which is already visible above.
          setAudioState("error");
        }
      });
    } catch {
      if (!controller.signal.aborted) setAudioState("error");
    }
  }

  function handleReplay() {
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = 0;
    el.play().then(
      () => setAudioState("playing"),
      () => setAudioState("error"),
    );
  }

  const canReplay = audioUrl !== null && audioState !== "loading";

  return (
    <div className={`flex items-end gap-2 ${isLearner ? "justify-end" : "justify-start"}`}>
      {!isLearner && (
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={handlePlayPause}
            disabled={audioState === "loading"}
            aria-label={audioState === "playing" ? "Pause tutor reply audio" : "Play tutor reply audio"}
            title={audioState === "playing" ? "Pause" : "Listen"}
            className="rounded-full border border-slate-700 p-1.5 text-xs text-slate-400 transition-colors hover:border-cyan-600 hover:text-cyan-300 disabled:opacity-50"
          >
            {audioState === "loading" ? "…" : audioState === "playing" ? "⏸" : "🔊"}
          </button>
          {canReplay && (
            <button
              type="button"
              onClick={handleReplay}
              aria-label="Replay tutor reply audio"
              title="Replay"
              className="rounded-full border border-slate-700 p-1.5 text-xs text-slate-400 transition-colors hover:border-cyan-600 hover:text-cyan-300"
            >
              ↺
            </button>
          )}
        </div>
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
      {audioState === "error" && (
        <p className="text-xs text-red-300" role="status">
          Couldn&apos;t play audio - you can still read the reply.
        </p>
      )}
      {audioUrl && (
        <audio
          ref={audioRef}
          src={audioUrl}
          className="hidden"
          onPause={() => setAudioState((s) => (s === "playing" ? "paused" : s))}
          onEnded={() => setAudioState("paused")}
          onError={() => setAudioState("error")}
        />
      )}
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
