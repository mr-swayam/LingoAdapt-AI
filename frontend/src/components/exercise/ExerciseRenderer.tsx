"use client";

import { useState } from "react";

import { PrimaryButton, TextInput } from "@/components/ui/form";
import type { Exercise, ExerciseFeedback, SubmittedAnswer } from "@/types/course";

import {
  ListeningAudioPlayer,
  MatchingAnswer,
  MultipleChoiceAnswer,
  ShortAnswerInput,
  SpeakingAnswer,
  TextAnswer,
  WordOrderAnswer,
} from "./AnswerInputs";
import type { MatchPair } from "./AnswerInputs";
import { FeedbackPanel } from "./FeedbackPanel";

/** Remount (via `key={exercise.id}` from the caller) whenever the exercise
 * changes, so each exercise's answer state starts fresh. */
export function ExerciseRenderer({
  exercise,
  result,
  submitting,
  accessToken,
  onSubmit,
  onSubmitAudio,
  onContinue,
}: {
  exercise: Exercise;
  result: ExerciseFeedback | null;
  submitting: boolean;
  accessToken: string;
  onSubmit: (answer: SubmittedAnswer) => void;
  onSubmitAudio: (audio: Blob) => void;
  onContinue: () => void;
}) {
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [orderedIds, setOrderedIds] = useState<string[]>([]);
  const [pairs, setPairs] = useState<MatchPair[]>([]);

  const answered = result !== null;

  function buildAnswer(): SubmittedAnswer | null {
    switch (exercise.type) {
      case "MULTIPLE_CHOICE":
        return selectedOptionId ? { option_id: selectedOptionId } : null;
      case "FILL_BLANK":
      case "TRANSLATION":
      case "SHORT_ANSWER":
        return text.trim() ? { text } : null;
      case "LISTENING":
        return text.trim() ? { text } : null;
      case "WORD_ORDER":
        return orderedIds.length === exercise.options.length ? { option_ids: orderedIds } : null;
      case "MATCHING": {
        const leftCount = exercise.options.filter((o) => o.match_group === "left").length;
        return pairs.length === leftCount ? { pairs } : null;
      }
      case "SPEAKING":
        return null; // SpeakingAnswer submits directly via onSubmitAudio
    }
  }

  const answer = buildAnswer();

  return (
    <div className="flex flex-col gap-6">
      <p className="text-lg font-medium text-slate-100">{exercise.prompt}</p>

      {exercise.type === "MULTIPLE_CHOICE" && (
        <MultipleChoiceAnswer
          exercise={exercise}
          value={selectedOptionId}
          onChange={setSelectedOptionId}
          disabled={answered}
          result={result}
        />
      )}
      {(exercise.type === "FILL_BLANK" || exercise.type === "TRANSLATION") && (
        <TextAnswer exercise={exercise} value={text} onChange={setText} disabled={answered} />
      )}
      {exercise.type === "SHORT_ANSWER" && (
        <ShortAnswerInput value={text} onChange={setText} disabled={answered} />
      )}
      {exercise.type === "LISTENING" && (
        <div className="flex flex-col gap-4">
          <ListeningAudioPlayer exerciseId={exercise.id} accessToken={accessToken} />
          <TextInput
            autoFocus
            disabled={answered}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type what you heard"
          />
        </div>
      )}
      {exercise.type === "SPEAKING" && (
        <SpeakingAnswer
          exercise={exercise}
          disabled={answered}
          submitting={submitting}
          onSubmitAudio={onSubmitAudio}
        />
      )}
      {exercise.type === "WORD_ORDER" && (
        <WordOrderAnswer
          exercise={exercise}
          value={orderedIds}
          onChange={setOrderedIds}
          disabled={answered}
        />
      )}
      {exercise.type === "MATCHING" && (
        <MatchingAnswer
          exercise={exercise}
          value={pairs}
          onChange={setPairs}
          disabled={answered}
        />
      )}

      {result && <FeedbackPanel exercise={exercise} result={result} />}

      {answered ? (
        <PrimaryButton onClick={onContinue}>Continue</PrimaryButton>
      ) : (
        exercise.type !== "SPEAKING" && (
          <PrimaryButton
            disabled={!answer || submitting}
            onClick={() => answer && onSubmit(answer)}
          >
            {submitting ? "Checking…" : "Check"}
          </PrimaryButton>
        )
      )}
    </div>
  );
}
