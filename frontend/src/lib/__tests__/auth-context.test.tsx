import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as authApi from "@/lib/auth-api";
import { AuthProvider, useAuth } from "@/lib/auth-context";

vi.mock("@/lib/auth-api");

const sampleUser = {
  id: "1",
  email: "a@example.com",
  created_at: "2026-01-01T00:00:00Z",
  is_admin: false,
  preferences: { native_language: "en", target_language: "es", daily_goal_xp: 50 },
};

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="status">{auth.status}</span>
      <span data-testid="email">{auth.user?.email ?? ""}</span>
      <button onClick={() => auth.login({ email: "a@example.com", password: "pw" })}>
        login
      </button>
      <button onClick={() => auth.logout()}>logout</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.mocked(authApi.refresh).mockRejectedValue(new authApi.ApiError(401, "no session"));
  });

  it("starts unauthenticated when the silent refresh fails", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    expect(screen.getByTestId("status").textContent).toBe("loading");
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
  });

  it("becomes authenticated after a successful login, and unauthenticated after logout", async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: "tok",
      token_type: "bearer",
      user: sampleUser,
    });
    vi.mocked(authApi.logout).mockResolvedValue(undefined);

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));

    await user.click(screen.getByText("login"));
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    expect(screen.getByTestId("email").textContent).toBe("a@example.com");

    await user.click(screen.getByText("logout"));
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("unauthenticated"));
  });
});
