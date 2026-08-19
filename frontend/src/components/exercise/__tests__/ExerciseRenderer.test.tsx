import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ExerciseRenderer } from "@/components/exercise/ExerciseRenderer";
import type { AnswerResult, Exercise } from "@/types/course";

const multipleChoice: Exercise = {
  id: "ex-1",
  type: "MULTIPLE_CHOICE",
  prompt: "Pick the greeting",
  payload: {},
  options: [
    { id: "opt-hello", text: "Hello", match_group: null },
    { id: "opt-bye", text: "Goodbye", match_group: null },
  ],
};

const fillBlank: Exercise = {
  id: "ex-2",
  type: "FILL_BLANK",
  prompt: "Complete the sentence",
  payload: { sentence: "___, how are you?" },
  options: [],
};

const shortAnswer: Exercise = {
  id: "ex-3",
  type: "SHORT_ANSWER",
  prompt: "Introduce yourself in one sentence.",
  payload: {},
  options: [],
};

describe("ExerciseRenderer - MULTIPLE_CHOICE", () => {
  it("disables Check until an option is selected, then submits the chosen option_id", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <ExerciseRenderer
        exercise={multipleChoice}
        result={null}
        submitting={false}
        accessToken="test-token"
        onSubmitAudio={vi.fn()}
        onSubmit={onSubmit}
        onContinue={vi.fn()}
      />,
    );

    expect(screen.getByText("Check")).toBeDisabled();

    await user.click(screen.getByText("Hello"));
    expect(screen.getByText("Check")).not.toBeDisabled();

    await user.click(screen.getByText("Check"));
    expect(onSubmit).toHaveBeenCalledWith({ option_id: "opt-hello" });
  });

  it("shows Continue instead of Check once a result is present, and calls onContinue", async () => {
    const onContinue = vi.fn();
    const result: AnswerResult = {
      is_correct: true,
      correct_answer: { option_id: "opt-hello", text: "Hello" },
      explanation: "Hello is a greeting.",
      lesson_completed: false,
      correct_count: 1,
      total_count: 4,
      xp_earned: 0,
      current_streak: null,
      new_achievements: [],
    };
    const user = userEvent.setup();
    render(
      <ExerciseRenderer
        exercise={multipleChoice}
        result={result}
        submitting={false}
        accessToken="test-token"
        onSubmitAudio={vi.fn()}
        onSubmit={vi.fn()}
        onContinue={onContinue}
      />,
    );

    expect(screen.queryByText("Check")).not.toBeInTheDocument();
    await user.click(screen.getByText("Continue"));
    expect(onContinue).toHaveBeenCalledOnce();
  });
});

describe("ExerciseRenderer - FILL_BLANK", () => {
  it("disables Check until text is entered, then submits it", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <ExerciseRenderer
        exercise={fillBlank}
        result={null}
        submitting={false}
        accessToken="test-token"
        onSubmitAudio={vi.fn()}
        onSubmit={onSubmit}
        onContinue={vi.fn()}
      />,
    );

    expect(screen.getByText("Check")).toBeDisabled();

    await user.type(screen.getByPlaceholderText("Type your answer"), "Hello");
    expect(screen.getByText("Check")).not.toBeDisabled();

    await user.click(screen.getByText("Check"));
    expect(onSubmit).toHaveBeenCalledWith({ text: "Hello" });
  });
});

describe("ExerciseRenderer - SHORT_ANSWER", () => {
  it("submits free-form text and shows the AI-graded feedback", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <ExerciseRenderer
        exercise={shortAnswer}
        result={null}
        submitting={false}
        accessToken="test-token"
        onSubmitAudio={vi.fn()}
        onSubmit={onSubmit}
        onContinue={vi.fn()}
      />,
    );

    expect(screen.getByText("Check")).toBeDisabled();

    await user.type(screen.getByPlaceholderText("Write your answer…"), "My name is Anna.");
    expect(screen.getByText("Check")).not.toBeDisabled();

    await user.click(screen.getByText("Check"));
    expect(onSubmit).toHaveBeenCalledWith({ text: "My name is Anna." });
  });

  it("renders the AI's corrected answer when the response is incorrect", () => {
    const result: AnswerResult = {
      is_correct: false,
      correct_answer: { corrected_answer: "My name is Anna and I am from Spain.", score: 0.3 },
      explanation: "Missing a verb.",
      lesson_completed: false,
      correct_count: 0,
      total_count: 1,
      xp_earned: 0,
      current_streak: null,
      new_achievements: [],
    };
    render(
      <ExerciseRenderer
        exercise={shortAnswer}
        result={result}
        submitting={false}
        accessToken="test-token"
        onSubmitAudio={vi.fn()}
        onSubmit={vi.fn()}
        onContinue={vi.fn()}
      />,
    );

    expect(
      screen.getByText("My name is Anna and I am from Spain."),
    ).toBeInTheDocument();
    expect(screen.getByText("Missing a verb.")).toBeInTheDocument();
  });
});
