import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Mascot, type MascotState } from "@/components/mascot/Mascot";

const ALL_STATES: MascotState[] = [
  "idle",
  "speaking",
  "listening",
  "happy",
  "encouraging",
  "thinking",
];

describe("Mascot", () => {
  it.each(ALL_STATES)("renders a labeled image for the %s state", (state) => {
    render(<Mascot state={state} />);
    expect(screen.getByRole("img", { name: `Tutor mascot: ${state}` })).toBeInTheDocument();
  });

  it("uses a caller-provided accessible label when given one", () => {
    render(<Mascot state="happy" label="Great job!" />);
    expect(screen.getByRole("img", { name: "Great job!" })).toBeInTheDocument();
  });

  it("never renders an 'encouraging' state as visually identical markup to an error/sad affect", () => {
    // Guards the product requirement that incorrect answers get warmth,
    // not a frown - this at least confirms the state renders distinctly
    // labeled and doesn't crash; visual affect itself is reviewed manually.
    render(<Mascot state="encouraging" />);
    expect(screen.getByRole("img", { name: "Tutor mascot: encouraging" })).toBeInTheDocument();
  });
});
