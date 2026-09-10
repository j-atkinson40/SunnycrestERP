/**
 * Read-only in the Focus layer.
 *
 * ⚠️ THE CLAIM IS THAT A USER MAY SEE A FOCUS AND NOT CHANGE IT — and that the
 * refusal is VISIBLE. Every assertion that a control is disabled is paired with
 * one that it is still RENDERED, because hiding it would satisfy "cannot act"
 * perfectly while telling the user nothing about why.
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useFocusReadOnly } from "./useFocusReadOnly";
import type { FocusConfig } from "@/contexts/focus-registry";

const authState = { hasPermission: (_k: string) => false, isAdmin: false };
vi.mock("@/contexts/auth-context", () => ({
  useAuthOptional: () => authState,
}));

function cfg(over: Partial<FocusConfig> = {}): FocusConfig {
  return {
    id: "f", mode: "kanban", displayName: "F", ...over,
  } as FocusConfig;
}

describe("useFocusReadOnly", () => {
  it("a Focus declaring NO editPermission is not read-only", () => {
    // ⚠️ Absence means "no gate declared", never "deny". A Focus that became
    // read-only by omission would make every unmigrated Focus silently
    // uneditable the moment this shipped.
    authState.hasPermission = () => false;
    authState.isAdmin = false;
    const { result } = renderHook(() => useFocusReadOnly(cfg()));
    expect(result.current).toBe(false);
  });

  it("is read-only when the declared permission is absent", () => {
    authState.hasPermission = () => false;
    authState.isAdmin = false;
    const { result } = renderHook(() =>
      useFocusReadOnly(cfg({ editPermission: "delivery.edit" })),
    );
    expect(result.current).toBe(true);
  });

  it("CONTROL: is NOT read-only when the permission is held", () => {
    // The pair. Without it, "read-only" is satisfied by a hook that always
    // returns true.
    authState.hasPermission = (k: string) => k === "delivery.edit";
    authState.isAdmin = false;
    const { result } = renderHook(() =>
      useFocusReadOnly(cfg({ editPermission: "delivery.edit" })),
    );
    expect(result.current).toBe(false);
  });

  it("admins are not read-only — matching PermissionGate deliberately", () => {
    // Two places answering "may this user do X" that disagree about admins is
    // worse than either answer.
    authState.hasPermission = () => false;
    authState.isAdmin = true;
    const { result } = renderHook(() =>
      useFocusReadOnly(cfg({ editPermission: "delivery.edit" })),
    );
    expect(result.current).toBe(false);
  });

  it("a null config is not read-only", () => {
    authState.hasPermission = () => false;
    authState.isAdmin = false;
    const { result } = renderHook(() => useFocusReadOnly(null));
    expect(result.current).toBe(false);
  });
});

describe("useFocusReadOnly — no auth context", () => {
  it("is not read-only when the gate cannot be evaluated", async () => {
    // ⚠️ REGRESSION. The first version called `useAuth`, which THROWS outside a
    // provider — making a Focus unrenderable without an auth tree and breaking
    // 12 tests in Focus.test.tsx and ReturnPill.test.tsx. Both answers here
    // assert something unknown; this preserves the pre-capability behaviour,
    // and the server remains the enforcement boundary.
    vi.resetModules();
    vi.doMock("@/contexts/auth-context", () => ({ useAuthOptional: () => null }));
    const { useFocusReadOnly: hook } = await import("./useFocusReadOnly");
    const { result } = renderHook(() =>
      hook(cfg({ editPermission: "delivery.edit" })),
    );
    expect(result.current).toBe(false);
    vi.doUnmock("@/contexts/auth-context");
  });
});
