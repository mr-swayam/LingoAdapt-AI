import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ListeningAudioPlayer } from "@/components/exercise/AnswerInputs";
import * as courseApi from "@/lib/course-api";

vi.mock("@/lib/course-api");

const fakeBlob = new Blob(["fake-audio"], { type: "audio/wav" });

describe("ListeningAudioPlayer", () => {
  it("shows a loading message while audio is being fetched, then a Listen button", async () => {
    vi.mocked(courseApi.getExerciseAudio).mockResolvedValue(fakeBlob);
    render(<ListeningAudioPlayer exerciseId="ex-1" accessToken="token" />);

    expect(screen.getByText("Loading audio…")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Listen to audio" })).toBeInTheDocument();
  });

  it("does NOT auto-play - playback only starts after the user presses Listen", async () => {
    vi.mocked(courseApi.getExerciseAudio).mockResolvedValue(fakeBlob);
    const playSpy = vi.spyOn(HTMLMediaElement.prototype, "play");
    render(<ListeningAudioPlayer exerciseId="ex-1" accessToken="token" />);

    await screen.findByRole("button", { name: "Listen to audio" });
    expect(playSpy).not.toHaveBeenCalled();
  });

  it("switches to a Replay button after the first successful play", async () => {
    vi.mocked(courseApi.getExerciseAudio).mockResolvedValue(fakeBlob);
    const user = userEvent.setup();
    render(<ListeningAudioPlayer exerciseId="ex-1" accessToken="token" />);

    const listenButton = await screen.findByRole("button", { name: "Listen to audio" });
    await user.click(listenButton);

    expect(await screen.findByRole("button", { name: "Replay audio" })).toBeInTheDocument();
  });

  it("shows an error message and reports the error state when the fetch fails", async () => {
    vi.mocked(courseApi.getExerciseAudio).mockRejectedValue(new Error("network error"));
    const onStateChange = vi.fn();
    render(
      <ListeningAudioPlayer exerciseId="ex-1" accessToken="token" onStateChange={onStateChange} />,
    );

    expect(
      await screen.findByText("Couldn't load the audio. Please try again."),
    ).toBeInTheDocument();
    await waitFor(() => expect(onStateChange).toHaveBeenCalledWith("error"));
  });

  it("shows an error status if the browser blocks programmatic playback", async () => {
    vi.mocked(courseApi.getExerciseAudio).mockResolvedValue(fakeBlob);
    vi.spyOn(HTMLMediaElement.prototype, "play").mockRejectedValueOnce(
      new DOMException("blocked", "NotAllowedError"),
    );
    const user = userEvent.setup();
    render(<ListeningAudioPlayer exerciseId="ex-1" accessToken="token" />);

    const listenButton = await screen.findByRole("button", { name: "Listen to audio" });
    await user.click(listenButton);

    expect(await screen.findByText("Couldn't play audio - please try again.")).toBeInTheDocument();
  });
});
