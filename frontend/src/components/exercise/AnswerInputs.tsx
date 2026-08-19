"use client";

import { useEffect, useMemo, useState } from "react";

import { PrimaryButton, TextArea, TextInput } from "@/components/ui/form";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";
import { getExerciseAudio } from "@/lib/course-api";
import type { ExerciseFeedback, Exercise } from "@/types/course";

function optionClasses(state: "idle" | "selected" | "correct" | "incorrect" | "reveal-correct") {
  const base =
    "w-full rounded-lg border px-4 py-3 text-left text-sm transition-colors disabled:cursor-not-allowed";
  switch (state) {
    case "correct":
      return `${base} border-emerald-500 bg-emerald-500/10 text-emerald-300`;
    case "incorrect":
      return `${base} border-red-500 bg-red-500/10 text-red-300`;
    case "reveal-correct":
      return `${base} border-emerald-700 text-emerald-400`;
    case "selected":
      return `${base} border-cyan-500 bg-cyan-500/10 text-slate-100`;
    default:
      return `${base} border-slate-800 bg-slate-950 text-slate-200 hover:border-slate-700`;
  }
}

export function MultipleChoiceAnswer({
  exercise,
  value,
  onChange,
  disabled,
  result,
}: {
  exercise: Exercise;
  value: string | null;
  onChange: (optionId: string) => void;
  disabled: boolean;
  result: ExerciseFeedback | null;
}) {
  const correctOptionId = result ? (result.correct_answer.option_id as string) : null;

  return (
    <div className="flex flex-col gap-3">
      {exercise.options.map((option) => {
        let state: Parameters<typeof optionClasses>[0] = "idle";
        if (result) {
          if (option.id === correctOptionId) state = "correct";
          else if (option.id === value) state = "incorrect";
        } else if (option.id === value) {
          state = "selected";
        }
        return (
          <button
            key={option.id}
            type="button"
            disabled={disabled}
            onClick={() => onChange(option.id)}
            className={optionClasses(state)}
          >
            {option.text}
          </button>
        );
      })}
    </div>
  );
}

export function TextAnswer({
  exercise,
  value,
  onChange,
  disabled,
}: {
  exercise: Exercise;
  value: string;
  onChange: (text: string) => void;
  disabled: boolean;
}) {
  const sentence = exercise.payload.sentence as string | undefined;
  const sourceText = exercise.payload.source_text as string | undefined;
  const sourceLanguage = exercise.payload.source_language as string | undefined;

  return (
    <div className="flex flex-col gap-4">
      {sentence && (
        <p className="rounded-lg border border-slate-800 bg-slate-950 px-4 py-3 text-lg text-slate-100">
          {sentence}
        </p>
      )}
      {sourceText && (
        <p className="rounded-lg border border-slate-800 bg-slate-950 px-4 py-3 text-lg text-slate-100">
          {sourceText}
          {sourceLanguage && <span className="ml-2 text-sm text-slate-400">({sourceLanguage})</span>}
        </p>
      )}
      <TextInput
        autoFocus
        disabled={disabled}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Type your answer"
      />
    </div>
  );
}

export function ShortAnswerInput({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (text: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <TextArea
        autoFocus
        disabled={disabled}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Write your answer…"
        rows={4}
      />
      <p className="text-xs text-slate-400">Graded by AI - feedback may take a few seconds.</p>
    </div>
  );
}

export function WordOrderAnswer({
  exercise,
  value,
  onChange,
  disabled,
}: {
  exercise: Exercise;
  value: string[];
  onChange: (optionIds: string[]) => void;
  disabled: boolean;
}) {
  const byId = Object.fromEntries(exercise.options.map((o) => [o.id, o.text]));
  const bank = exercise.options.filter((o) => !value.includes(o.id));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex min-h-14 flex-wrap gap-2 rounded-lg border border-dashed border-slate-700 p-3">
        {value.length === 0 && <span className="text-sm text-slate-400">Tap words below…</span>}
        {value.map((id) => (
          <button
            key={id}
            type="button"
            disabled={disabled}
            onClick={() => onChange(value.filter((v) => v !== id))}
            className="rounded-lg border border-cyan-500 bg-cyan-500/10 px-3 py-1.5 text-sm text-slate-100"
          >
            {byId[id]}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {bank.map((option) => (
          <button
            key={option.id}
            type="button"
            disabled={disabled}
            onClick={() => onChange([...value, option.id])}
            className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-sm text-slate-200 hover:border-slate-700"
          >
            {option.text}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SpeakingAnswer({
  exercise,
  disabled,
  submitting,
  onSubmitAudio,
}: {
  exercise: Exercise;
  disabled: boolean;
  submitting: boolean;
  onSubmitAudio: (audio: Blob) => void;
}) {
  const phrase = exercise.payload.phrase_to_say as string | undefined;
  const { state, audioBlob, error, start, stop, reset } = useAudioRecorder();
  // Derived directly from audioBlob rather than mirrored into its own
  // state - avoids a setState-in-effect render cascade for a value that's
  // just a transformation of state React already has.
  const audioUrl = useMemo(() => (audioBlob ? URL.createObjectURL(audioBlob) : null), [audioBlob]);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  return (
    <div className="flex flex-col gap-4">
      {phrase && (
        <p className="rounded-lg border border-slate-800 bg-slate-950 px-4 py-3 text-lg text-slate-100">
          {phrase}
        </p>
      )}
      {error && <p className="text-sm text-red-300">{error}</p>}

      {state === "idle" && (
        <PrimaryButton type="button" onClick={start} disabled={disabled}>
          🎤 Start recording
        </PrimaryButton>
      )}
      {state === "recording" && (
        <PrimaryButton type="button" onClick={stop} variant="danger">
          ⏹ Stop recording
        </PrimaryButton>
      )}
      {state === "recorded" && audioUrl && (
        <div className="flex flex-col gap-3">
          <audio controls src={audioUrl} className="w-full" />
          <div className="flex gap-2">
            <PrimaryButton
              type="button"
              disabled={disabled || submitting}
              onClick={() => audioBlob && onSubmitAudio(audioBlob)}
            >
              {submitting ? "Checking…" : "Submit recording"}
            </PrimaryButton>
            <PrimaryButton
              type="button"
              disabled={disabled || submitting}
              onClick={reset}
              variant="secondary"
            >
              Re-record
            </PrimaryButton>
          </div>
        </div>
      )}
    </div>
  );
}

export function ListeningAudioPlayer({
  exerciseId,
  accessToken,
}: {
  exerciseId: string;
  accessToken: string;
}) {
  // No re-fetch-on-change reset needed: the caller (ExerciseRenderer) is
  // remounted with key={exercise.id} whenever the exercise changes, so a
  // new exercise always means a fresh mount with fresh initial state here.
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    getExerciseAudio(exerciseId, accessToken)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setAudioUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load the audio.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [exerciseId, accessToken]);

  if (loading) return <p className="text-sm text-slate-400">Loading audio…</p>;
  if (error) return <p className="text-sm text-red-300">{error}</p>;
  if (!audioUrl) return null;
  return <audio controls autoPlay src={audioUrl} className="w-full" />;
}

export type MatchPair = { left_option_id: string; right_option_id: string };

export function MatchingAnswer({
  exercise,
  value,
  onChange,
  disabled,
}: {
  exercise: Exercise;
  value: MatchPair[];
  onChange: (pairs: MatchPair[]) => void;
  disabled: boolean;
}) {
  const [selectedLeft, setSelectedLeft] = useState<string | null>(null);

  const leftOptions = exercise.options.filter((o) => o.match_group === "left");
  const rightOptions = exercise.options.filter((o) => o.match_group === "right");
  const pairedLeft = new Set(value.map((p) => p.left_option_id));
  const pairedRight = new Set(value.map((p) => p.right_option_id));

  function handleLeftClick(id: string) {
    if (pairedLeft.has(id)) {
      onChange(value.filter((p) => p.left_option_id !== id));
      setSelectedLeft(null);
      return;
    }
    setSelectedLeft(id);
  }

  function handleRightClick(id: string) {
    if (pairedRight.has(id)) {
      onChange(value.filter((p) => p.right_option_id !== id));
      return;
    }
    if (!selectedLeft) return;
    onChange([...value, { left_option_id: selectedLeft, right_option_id: id }]);
    setSelectedLeft(null);
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="flex flex-col gap-2">
        {leftOptions.map((option) => (
          <button
            key={option.id}
            type="button"
            disabled={disabled}
            onClick={() => handleLeftClick(option.id)}
            className={optionClasses(
              pairedLeft.has(option.id)
                ? "correct"
                : option.id === selectedLeft
                  ? "selected"
                  : "idle",
            )}
          >
            {option.text}
          </button>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {rightOptions.map((option) => (
          <button
            key={option.id}
            type="button"
            disabled={disabled}
            onClick={() => handleRightClick(option.id)}
            className={optionClasses(pairedRight.has(option.id) ? "correct" : "idle")}
          >
            {option.text}
          </button>
        ))}
      </div>
    </div>
  );
}
