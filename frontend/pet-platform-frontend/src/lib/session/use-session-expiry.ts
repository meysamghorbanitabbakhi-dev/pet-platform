"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { ApiError } from "@/lib/api/errors";
import { storeReturnTo } from "@/lib/auth-return";

function isSessionExpiredError(error: unknown) {
  return error instanceof ApiError && error.status === 401;
}

// Single place that decides what "session expired" means and what happens
// next, so every protected page does not re-implement (or forget to
// implement) its own 401 check. Pass every query/mutation error the page
// depends on; a 401 on any of them means the whole page is unusable.
//
// On first detecting expiry, captures the current location as a safe return
// path (consumed once, after the user re-authenticates) and redirects to the
// dedicated session-expired screen -- never re-redirects on every render
// (no loop), and never fires while already on an /auth/* route (nothing to
// return from).
export function useSessionExpiryRedirect(...errors: unknown[]): boolean {
  const router = useRouter();
  const sessionExpired = errors.some(isSessionExpiredError);
  const redirected = useRef(false);

  useEffect(() => {
    if (!sessionExpired || redirected.current) return;
    if (window.location.pathname.startsWith("/auth/")) return;
    redirected.current = true;
    storeReturnTo(window.location.pathname + window.location.search);
    router.replace("/auth/session-expired");
  }, [sessionExpired, router]);

  return sessionExpired;
}
