import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { consumeReturnTo } from "@/lib/auth-return";
import { useSessionExpiryRedirect } from "./use-session-expiry";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

function setLocation(pathname: string, search = "") {
  window.history.pushState({}, "", pathname + search);
}

describe("useSessionExpiryRedirect", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    setLocation("/inventory/unit-1", "?tab=details");
  });

  it("returns false and does not redirect when there is no 401 among the errors", () => {
    const { result } = renderHook(() =>
      useSessionExpiryRedirect(undefined, new Error("network down")),
    );
    expect(result.current).toBe(false);
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to the session-expired screen and captures the current path as a safe return path", () => {
    const { result } = renderHook(() =>
      useSessionExpiryRedirect(new ApiError("expired", 401)),
    );
    expect(result.current).toBe(true);
    expect(replace).toHaveBeenCalledWith("/auth/session-expired");
    expect(consumeReturnTo()).toBe("/inventory/unit-1?tab=details");
  });

  it("only redirects once, not on every re-render (no loop)", () => {
    const { rerender } = renderHook(
      ({ error }: { error: unknown }) => useSessionExpiryRedirect(error),
      { initialProps: { error: new ApiError("expired", 401) } },
    );
    act(() => rerender({ error: new ApiError("expired", 401) }));
    act(() => rerender({ error: new ApiError("expired", 401) }));
    expect(replace).toHaveBeenCalledTimes(1);
  });

  it("does not redirect (or capture a return path) when already on an /auth/* route", () => {
    setLocation("/auth/session-expired");
    renderHook(() => useSessionExpiryRedirect(new ApiError("expired", 401)));
    expect(replace).not.toHaveBeenCalled();
    expect(consumeReturnTo()).toBeNull();
  });

  it("treats any 401 among multiple errors as expiry", () => {
    const { result } = renderHook(() =>
      useSessionExpiryRedirect(undefined, new ApiError("expired", 401)),
    );
    expect(result.current).toBe(true);
  });
});
