import type { ExerciseFeedback, Exercise } from "@/types/course";

const LISTENING_HEADLINES: Record<string, string> = {
  EXACT: "Perfect!",
  NORMALIZED: "Correct!",
  MINOR_ERROR: "Close - small slip",
  PARTIAL: "Partially correct",
  MAJOR_ERROR: "Not quite",
  INCORRECT: "Let's try again",
};

function ListeningWordChips({ result }: { result: ExerciseFeedback }) {
  const correct = (result.correct_answer.words_correct as string[] | undefined) ?? [];
  const missing = (result.correct_answer.words_missing as string[] | undefined) ?? [];
  const incorrect = (result.correct_answer.words_incorrect as string[] | undefined) ?? [];
  const expected = result.correct_answer.expected_sentence as string | undefined;
  const explanation = result.correct_answer.explanation as string | undefined;

  return (
    <div className="mb-2 flex flex-col gap-2 text-sm text-slate-300">
      {explanation && <p className="text-slate-400">{explanation}</p>}
      {expected && (
        <p>
          <span className="text-slate-400">Expected: </span>
          &ldquo;{expected}&rdquo;
        </p>
      )}
      {(correct.length > 0 || missing.length > 0 || incorrect.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {correct.map((word, i) => (
            <span
              key={`c-${i}-${word}`}
              className="rounded border border-emerald-700 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300"
            >
              {word}
            </span>
          ))}
          {missing.map((word, i) => (
            <span
              key={`m-${i}-${word}`}
              className="rounded border border-dashed border-amber-700 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300"
              title="Missing"
            >
              {word}
            </span>
          ))}
          {incorrect.map((word, i) => (
            <span
              key={`i-${i}-${word}`}
              className="rounded border border-red-700 bg-red-500/10 px-2 py-0.5 text-xs text-red-300 line-through"
              title="Heard incorrectly"
            >
              {word}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function CorrectAnswerSummary({
  exercise,
  result,
}: {
  exercise: Exercise;
  result: ExerciseFeedback;
}) {
  switch (exercise.type) {
    case "MULTIPLE_CHOICE":
      return <p>{result.correct_answer.text as string}</p>;
    case "FILL_BLANK":
    case "TRANSLATION":
    case "LISTENING":
      return <p>{(result.correct_answer.answers as string[]).join(" / ")}</p>;
    case "WORD_ORDER":
      return <p>{(result.correct_answer.order as string[]).join(" ")}</p>;
    case "MATCHING": {
      const pairs = result.correct_answer.pairs as { left: string; right: string }[];
      return (
        <ul className="flex flex-col gap-0.5">
          {pairs.map((pair) => (
            <li key={pair.left}>
              {pair.left} → {pair.right}
            </li>
          ))}
        </ul>
      );
    }
    case "SHORT_ANSWER":
      return <p>{result.correct_answer.corrected_answer as string}</p>;
    default:
      return null;
  }
}

export function FeedbackPanel({
  exercise,
  result,
}: {
  exercise: Exercise;
  result: ExerciseFeedback;
}) {
  const isSpeaking = exercise.type === "SPEAKING";
  const isListening = exercise.type === "LISTENING";
  const listeningCategory = result.correct_answer.category as string | undefined;

  const headline = isListening && listeningCategory
    ? (LISTENING_HEADLINES[listeningCategory] ?? (result.is_correct ? "Correct!" : "Almost!"))
    : result.is_correct
      ? "Correct!"
      : "Almost!";

  return (
    <div
      className={`rounded-xl border p-4 ${
        result.is_correct
          ? "border-emerald-800 bg-emerald-950/40"
          : "border-amber-800 bg-amber-950/40"
      }`}
    >
      <p
        className={`mb-2 font-semibold ${
          result.is_correct ? "text-emerald-300" : "text-amber-300"
        }`}
      >
        {headline}
      </p>

      {isListening ? (
        <ListeningWordChips result={result} />
      ) : isSpeaking ? (
        <div className="mb-2 flex flex-col gap-1 text-sm text-slate-300">
          <p>
            <span className="text-slate-400">You said: </span>
            &ldquo;{result.correct_answer.transcript as string}&rdquo;
          </p>
          <p className="text-slate-400">{result.correct_answer.feedback as string}</p>
        </div>
      ) : (
        !result.is_correct && (
          <div className="mb-2 text-sm text-slate-300">
            <span className="text-slate-400">Correct answer: </span>
            <CorrectAnswerSummary exercise={exercise} result={result} />
          </div>
        )
      )}
      {result.explanation && <p className="text-sm text-slate-400">{result.explanation}</p>}
    </div>
  );
}
