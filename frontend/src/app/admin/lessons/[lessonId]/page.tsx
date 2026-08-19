"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { Field, PrimaryButton, Select, TextArea, TextInput } from "@/components/ui/form";
import { useRequireAuth } from "@/hooks/use-require-auth";
import {
  ApiError,
  createExercise,
  deleteExercise,
  getLesson,
  listSkills,
} from "@/lib/admin-api";
import type { Skill } from "@/types/admin";
import type { ExerciseAdmin, ExerciseType, LessonAdminDetail } from "@/types/admin";

const EXERCISE_TYPES: ExerciseType[] = [
  "MULTIPLE_CHOICE",
  "FILL_BLANK",
  "TRANSLATION",
  "WORD_ORDER",
  "MATCHING",
  "SHORT_ANSWER",
  "SPEAKING",
  "LISTENING",
];

export default function AdminLessonDetailPage({
  params,
}: {
  params: Promise<{ lessonId: string }>;
}) {
  const { lessonId } = use(params);
  const { status, user, accessToken } = useRequireAuth();
  const [lesson, setLesson] = useState<LessonAdminDetail | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    if (status !== "authenticated" || !accessToken) return;
    getLesson(lessonId, accessToken)
      .then((lessonData) => {
        setLesson(lessonData);
        return listSkills(lessonData.course_id, accessToken);
      })
      .then(setSkills)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load lesson."))
      .finally(() => setLoading(false));
  }, [status, accessToken, lessonId, refreshKey]);

  if (status !== "authenticated" || !user) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }
  if (!user.is_admin) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-red-300">Admin access required.</p>
      </div>
    );
  }

  function refresh() {
    setRefreshKey((k) => k + 1);
  }

  async function handleDeleteExercise(exerciseId: string) {
    if (!accessToken) return;
    setError(null);
    try {
      await deleteExercise(exerciseId, accessToken);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete that exercise.");
    }
  }

  if (loading || !lesson) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="text-slate-400">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center px-6 py-12">
      <div className="w-full max-w-2xl">
        <div className="mb-6 flex items-center gap-4">
          <Link href="/admin" className="text-slate-400 hover:text-slate-300">
            ←
          </Link>
          <h1 className="text-2xl font-semibold text-slate-50">{lesson.title}</h1>
        </div>

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

        <div className="mb-6 flex flex-col gap-2">
          {lesson.exercises.length === 0 && (
            <p className="text-sm text-slate-400">No exercises yet.</p>
          )}
          {lesson.exercises.map((exercise) => (
            <ExerciseRow
              key={exercise.id}
              exercise={exercise}
              onDelete={() => handleDeleteExercise(exercise.id)}
            />
          ))}
        </div>

        {showForm ? (
          <ExerciseFormCard
            lessonId={lessonId}
            courseSkills={skills}
            accessToken={accessToken ?? ""}
            onCreated={() => {
              setShowForm(false);
              refresh();
            }}
            onCancel={() => setShowForm(false)}
          />
        ) : (
          <PrimaryButton onClick={() => setShowForm(true)}>+ Add exercise</PrimaryButton>
        )}
      </div>
    </div>
  );
}

function ExerciseRow({
  exercise,
  onDelete,
}: {
  exercise: ExerciseAdmin;
  onDelete: () => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
      <div>
        <span className="mr-2 rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-400">
          {exercise.type}
        </span>
        <span className="text-sm text-slate-200">{exercise.prompt}</span>
      </div>
      <button onClick={onDelete} className="text-xs text-red-400 hover:text-red-300">
        Delete
      </button>
    </div>
  );
}

function ExerciseFormCard({
  lessonId,
  courseSkills,
  accessToken,
  onCreated,
  onCancel,
}: {
  lessonId: string;
  courseSkills: Skill[];
  accessToken: string;
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [type, setType] = useState<ExerciseType>("MULTIPLE_CHOICE");
  const [prompt, setPrompt] = useState("");
  const [explanation, setExplanation] = useState("");
  const [difficulty, setDifficulty] = useState(0.5);
  const [skillId, setSkillId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Type-specific fields
  const [mcOptions, setMcOptions] = useState([{ text: "", correct: true }, { text: "", correct: false }]);
  const [sentence, setSentence] = useState("");
  const [answersCsv, setAnswersCsv] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [sourceLanguage, setSourceLanguage] = useState("");
  const [woWords, setWoWords] = useState("");
  const [pairs, setPairs] = useState([{ left: "", right: "" }]);
  const [modelAnswer, setModelAnswer] = useState("");
  const [rubric, setRubric] = useState("");
  const [phraseToSay, setPhraseToSay] = useState("");
  const [textToSpeak, setTextToSpeak] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim() || !skillId) {
      setError("Prompt and skill are required.");
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const base = {
        lesson_id: lessonId,
        skill_id: skillId,
        type,
        prompt: prompt.trim(),
        explanation: explanation.trim() || null,
        difficulty,
      };

      let extra: Partial<Parameters<typeof createExercise>[0]> = {};
      switch (type) {
        case "MULTIPLE_CHOICE":
          extra = {
            options: mcOptions
              .filter((o) => o.text.trim())
              .map((o) => ({ text: o.text.trim(), is_correct: o.correct })),
          };
          break;
        case "FILL_BLANK":
          extra = {
            payload: { sentence },
            correct_answer: { answers: splitCsv(answersCsv) },
          };
          break;
        case "TRANSLATION":
          extra = {
            payload: { source_text: sourceText, source_language: sourceLanguage },
            correct_answer: { answers: splitCsv(answersCsv) },
          };
          break;
        case "WORD_ORDER":
          extra = {
            options: splitCsv(woWords).map((w, i) => ({ text: w, correct_position: i })),
          };
          break;
        case "MATCHING":
          extra = {
            options: pairs
              .filter((p) => p.left.trim() && p.right.trim())
              .flatMap((p, i) => [
                { text: p.left.trim(), match_group: "left", match_key: String(i) },
                { text: p.right.trim(), match_group: "right", match_key: String(i) },
              ]),
          };
          break;
        case "SHORT_ANSWER":
          extra = { correct_answer: { model_answer: modelAnswer, rubric } };
          break;
        case "SPEAKING":
          extra = {
            payload: { phrase_to_say: phraseToSay },
            correct_answer: { answers: splitCsv(answersCsv) },
          };
          break;
        case "LISTENING":
          extra = {
            correct_answer: { text_to_speak: textToSpeak, answers: splitCsv(answersCsv) },
          };
          break;
      }

      await createExercise({ ...base, ...extra }, accessToken);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create that exercise.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6"
    >
      <Field label="Type" htmlFor="ex-type">
        <Select id="ex-type" value={type} onChange={(e) => setType(e.target.value as ExerciseType)}>
          {EXERCISE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
      </Field>

      <Field label="Skill" htmlFor="ex-skill">
        <Select id="ex-skill" value={skillId} onChange={(e) => setSkillId(e.target.value)}>
          <option value="">Select a skill…</option>
          {courseSkills.map((s) => (
            <option key={s.id} value={s.id}>
              {s.code}
            </option>
          ))}
        </Select>
        {courseSkills.length === 0 && (
          <p className="mt-1 text-xs text-amber-400">
            No skills loaded - add one from the course page first.
          </p>
        )}
      </Field>

      <Field label="Prompt" htmlFor="ex-prompt">
        <TextArea id="ex-prompt" rows={2} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      </Field>

      {type === "MULTIPLE_CHOICE" && (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-slate-300">Options</label>
          {mcOptions.map((opt, i) => (
            <div key={i} className="flex items-center gap-2">
              <TextInput
                value={opt.text}
                onChange={(e) => {
                  const next = [...mcOptions];
                  next[i] = { ...next[i], text: e.target.value };
                  setMcOptions(next);
                }}
                placeholder={`Option ${i + 1}`}
                className="flex-1"
              />
              <label className="flex items-center gap-1 text-xs text-slate-400">
                <input
                  type="radio"
                  name="mc-correct"
                  checked={opt.correct}
                  onChange={() =>
                    setMcOptions(mcOptions.map((o, j) => ({ ...o, correct: j === i })))
                  }
                />
                Correct
              </label>
            </div>
          ))}
          <button
            type="button"
            onClick={() => setMcOptions([...mcOptions, { text: "", correct: false }])}
            className="self-start text-xs text-cyan-400 hover:text-cyan-300"
          >
            + Add option
          </button>
        </div>
      )}

      {type === "FILL_BLANK" && (
        <>
          <Field label="Sentence (use ___ for the blank)" htmlFor="ex-sentence">
            <TextInput id="ex-sentence" value={sentence} onChange={(e) => setSentence(e.target.value)} />
          </Field>
          <Field label="Accepted answers (comma-separated)" htmlFor="ex-answers">
            <TextInput id="ex-answers" value={answersCsv} onChange={(e) => setAnswersCsv(e.target.value)} />
          </Field>
        </>
      )}

      {type === "TRANSLATION" && (
        <>
          <Field label="Source text" htmlFor="ex-source">
            <TextInput id="ex-source" value={sourceText} onChange={(e) => setSourceText(e.target.value)} />
          </Field>
          <Field label="Source language" htmlFor="ex-source-lang">
            <TextInput
              id="ex-source-lang"
              value={sourceLanguage}
              onChange={(e) => setSourceLanguage(e.target.value)}
            />
          </Field>
          <Field label="Accepted answers (comma-separated)" htmlFor="ex-answers2">
            <TextInput id="ex-answers2" value={answersCsv} onChange={(e) => setAnswersCsv(e.target.value)} />
          </Field>
        </>
      )}

      {type === "WORD_ORDER" && (
        <Field label="Words in correct order (comma-separated)" htmlFor="ex-words">
          <TextInput id="ex-words" value={woWords} onChange={(e) => setWoWords(e.target.value)} />
        </Field>
      )}

      {type === "MATCHING" && (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-slate-300">Pairs</label>
          {pairs.map((pair, i) => (
            <div key={i} className="flex gap-2">
              <TextInput
                placeholder="Left"
                value={pair.left}
                onChange={(e) => {
                  const next = [...pairs];
                  next[i] = { ...next[i], left: e.target.value };
                  setPairs(next);
                }}
                className="flex-1"
              />
              <TextInput
                placeholder="Right"
                value={pair.right}
                onChange={(e) => {
                  const next = [...pairs];
                  next[i] = { ...next[i], right: e.target.value };
                  setPairs(next);
                }}
                className="flex-1"
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() => setPairs([...pairs, { left: "", right: "" }])}
            className="self-start text-xs text-cyan-400 hover:text-cyan-300"
          >
            + Add pair
          </button>
        </div>
      )}

      {type === "SHORT_ANSWER" && (
        <>
          <Field label="Model answer" htmlFor="ex-model">
            <TextInput id="ex-model" value={modelAnswer} onChange={(e) => setModelAnswer(e.target.value)} />
          </Field>
          <Field label="Grading rubric" htmlFor="ex-rubric">
            <TextArea id="ex-rubric" rows={2} value={rubric} onChange={(e) => setRubric(e.target.value)} />
          </Field>
        </>
      )}

      {type === "SPEAKING" && (
        <>
          <Field label="Phrase to say" htmlFor="ex-phrase">
            <TextInput id="ex-phrase" value={phraseToSay} onChange={(e) => setPhraseToSay(e.target.value)} />
          </Field>
          <Field label="Accepted phrasings (comma-separated)" htmlFor="ex-answers3">
            <TextInput id="ex-answers3" value={answersCsv} onChange={(e) => setAnswersCsv(e.target.value)} />
          </Field>
        </>
      )}

      {type === "LISTENING" && (
        <>
          <Field label="Text to speak (hidden from learners)" htmlFor="ex-tts">
            <TextInput id="ex-tts" value={textToSpeak} onChange={(e) => setTextToSpeak(e.target.value)} />
          </Field>
          <Field label="Accepted answers (comma-separated)" htmlFor="ex-answers4">
            <TextInput id="ex-answers4" value={answersCsv} onChange={(e) => setAnswersCsv(e.target.value)} />
          </Field>
        </>
      )}

      <Field label="Explanation (optional)" htmlFor="ex-explanation">
        <TextArea
          id="ex-explanation"
          rows={2}
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
        />
      </Field>

      <Field label={`Difficulty: ${difficulty.toFixed(1)}`} htmlFor="ex-difficulty">
        <input
          id="ex-difficulty"
          type="range"
          min={0}
          max={1}
          step={0.1}
          value={difficulty}
          onChange={(e) => setDifficulty(Number(e.target.value))}
        />
      </Field>

      {error && <p className="text-sm text-red-300">{error}</p>}

      <div className="flex gap-2">
        <PrimaryButton type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Create exercise"}
        </PrimaryButton>
        <PrimaryButton type="button" onClick={onCancel} variant="secondary">
          Cancel
        </PrimaryButton>
      </div>
    </form>
  );
}

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}
