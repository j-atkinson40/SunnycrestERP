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
