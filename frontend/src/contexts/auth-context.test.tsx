/**
 * AuthProvider — error-handling discrimination tests (R-1.6.2).
 *
 * Covers the post-R-1.6.2 invariant: only HTTP 401 from /auth/me
 * destroys the access + refresh tokens. Every other error
 * (404, 5xx, network failure) leaves the token in place.
 *
 * Originating bug: a wrong-backend 404 (production frontend bundle
 * baked with VITE_API_URL=https://api.getbridgeable.com hitting prod
 * with a staging-realm impersonation token) was sweeping valid
 * tokens before R-1.6.2. See /tmp/shell_empty_state_bug.md.
 */
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "./auth-context";

vi.mock("@/services/auth-service", () => ({
  authService: {
    getMe: vi.fn(),
  },
}));

import { authService } from "@/services/auth-service";

/**
 * ⚠️ A SECOND PROBE, because logout is a CALLABLE and the existing probe only reads
 * state. Exposing it as a button keeps the test driving the provider the way the app
 * does rather than reaching into the context value.
 */
function LogoutProbe() {
  const { isLoading, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{isLoading ? "loading" : "ready"}</span>
      <button type="button" data-testid="logout" onClick={logout}>
        out
      </button>
    </div>
  );
}

function Probe() {
  const { isLoading, isAuthenticated } = useAuth();
  return (
    <div>
      <span data-testid="loading">{isLoading ? "loading" : "ready"}</span>
      <span data-testid="auth">{isAuthenticated ? "auth" : "anon"}</span>
    </div>
  );
}

describe("AuthProvider — R-1.6.2 catch-block status discrimination", () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem("access_token", "stub-access-token");
    localStorage.setItem("refresh_token", "stub-refresh-token");
    vi.mocked(authService.getMe).mockReset();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("clears tokens on 401 (token genuinely invalid)", async () => {
    vi.mocked(authService.getMe).mockRejectedValueOnce({
      response: { status: 401 },
    });

    const { getByTestId } = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(getByTestId("loading").textContent).toBe("ready");
    });

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("preserves tokens on 404 (wrong backend / route missing)", async () => {
    vi.mocked(authService.getMe).mockRejectedValueOnce({
      response: { status: 404 },
    });

    const { getByTestId } = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(getByTestId("loading").textContent).toBe("ready");
    });

    expect(localStorage.getItem("access_token")).toBe("stub-access-token");
    expect(localStorage.getItem("refresh_token")).toBe("stub-refresh-token");
  });

  it("preserves tokens on 500 (server error)", async () => {
    vi.mocked(authService.getMe).mockRejectedValueOnce({
      response: { status: 500 },
    });

    const { getByTestId } = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(getByTestId("loading").textContent).toBe("ready");
    });

    expect(localStorage.getItem("access_token")).toBe("stub-access-token");
    expect(localStorage.getItem("refresh_token")).toBe("stub-refresh-token");
  });

  it("preserves tokens on network error (no response)", async () => {
    // Axios network failures throw an Error with no `response` property.
    vi.mocked(authService.getMe).mockRejectedValueOnce(
      new Error("Network Error"),
    );

    const { getByTestId } = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(getByTestId("loading").textContent).toBe("ready");
    });

    expect(localStorage.getItem("access_token")).toBe("stub-access-token");
    expect(localStorage.getItem("refresh_token")).toBe("stub-refresh-token");
  });
});

/**
 * Logout clears Opas client state. Ruled by James 2026-10-13.
 *
 * ⚠️ THE REASON IS A SHARED OFFICE COMPUTER, not tidiness. Logout is the handover
 * between two PEOPLE; the next person to sign in must not inherit anything about the
 * last person's half-typed order. Closing Opas is the same person changing their
 * mind, and clears too, but this is the boundary that crosses between people.
 *
 * ⚠️ THE KEY USED HERE IS ONE NO CURRENT CODE WRITES, and that is deliberate. Measured
 * 2026-10-13: nothing in the shipping bundle persists an Opas key any more. The keys
 * that matter on logout are leftovers from builds already replaced — which is exactly
 * the state James's own tab was in for three walk rounds — so the clear is a sweep of
 * the `opas.` namespace and the test pins the sweep, not the one name.
 */
describe("logout clears Opas client state", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    localStorage.setItem("access_token", "stub-access-token");
    vi.mocked(authService.getMe).mockResolvedValue({
      id: 1,
      username: "jamesd",
      track: "office",
    } as never);
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("removes every opas.* key from BOTH storages", async () => {
    sessionStorage.setItem("opas.capture.session", "sess-1");
    sessionStorage.setItem("opas.some.older.build.key", "x");
    localStorage.setItem("opas.capture.session", "sess-1");
    // ⚠️ THE NEGATIVE CONTROL. A clear that wiped storage wholesale would pass every
    // assertion above and log the shared tablet out of its remembered username,
    // which the office relies on.
    localStorage.setItem("last_username", "jamesd");

    const { getByTestId } = render(
      <AuthProvider>
        <LogoutProbe />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(getByTestId("loading").textContent).toBe("ready");
    });

    getByTestId("logout").click();

    await waitFor(() => {
      expect(sessionStorage.getItem("opas.capture.session")).toBeNull();
    });
    expect(sessionStorage.getItem("opas.some.older.build.key")).toBeNull();
    expect(localStorage.getItem("opas.capture.session")).toBeNull();
    expect(localStorage.getItem("last_username")).toBe("jamesd");
  });
});
