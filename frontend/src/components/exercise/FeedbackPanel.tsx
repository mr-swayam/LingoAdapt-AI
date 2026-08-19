import type { ExerciseFeedback, Exercise } from "@/types/course";

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
        {result.is_correct ? "Correct!" : "Almost!"}
      </p>

      {isSpeaking ? (
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
