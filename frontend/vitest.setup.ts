import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement these - needed by any component using <audio>
// (tutor voice replies, listening practice), not specific to one test file.
if (typeof URL.createObjectURL !== "function") {
  URL.createObjectURL = () => "blob:mock";
}
if (typeof URL.revokeObjectURL !== "function") {
  URL.revokeObjectURL = () => {};
}
HTMLMediaElement.prototype.play = () => Promise.resolve();
HTMLMediaElement.prototype.pause = () => {};
