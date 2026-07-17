import "server-only";

import { randomUUID } from "node:crypto";
import { cookies } from "next/headers";
import type { OtpVerifyResponse, TokenResponse } from "@/lib/api-types";

const accessMaxAgeSeconds = 15 * 60;
const refreshMaxAgeSeconds = 30 * 24 * 60 * 60;
const secureCookie =
  process.env.NODE_ENV === "production" || process.env.COOKIE_SECURE === "1";
const accessCookie = secureCookie ? "__Host-pet_access" : "pet_access";
const refreshCookie = secureCookie ? "__Host-pet_refresh" : "pet_refresh";
export const csrfCookie = secureCookie ? "__Host-pet_csrf" : "pet_csrf";

const tokenCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: secureCookie,
  path: "/",
};

const csrfCookieOptions = {
  httpOnly: false,
  sameSite: "lax" as const,
  secure: secureCookie,
  path: "/",
};

export async function readAccessToken() {
  return (await cookies()).get(accessCookie)?.value ?? null;
}

export async function readRefreshToken() {
  return (await cookies()).get(refreshCookie)?.value ?? null;
}

export async function setSessionFromOtp(response: OtpVerifyResponse) {
  if (
    response.state !== "verified" ||
    !response.access_token ||
    !response.refresh_token
  ) {
    return;
  }
  await setSessionCookies({
    access_token: response.access_token,
    refresh_token: response.refresh_token,
    expires_in_seconds: accessMaxAgeSeconds,
    token_type: "bearer",
  });
}

export async function setSessionCookies(response: TokenResponse) {
  const cookieStore = await cookies();
  cookieStore.set(accessCookie, response.access_token, {
    ...tokenCookieOptions,
    maxAge: response.expires_in_seconds || accessMaxAgeSeconds,
  });
  cookieStore.set(refreshCookie, response.refresh_token, {
    ...tokenCookieOptions,
    maxAge: refreshMaxAgeSeconds,
  });
  cookieStore.set(csrfCookie, randomUUID(), {
    ...csrfCookieOptions,
    maxAge: refreshMaxAgeSeconds,
  });
}

export async function clearSessionCookies() {
  const cookieStore = await cookies();
  for (const name of [accessCookie, refreshCookie, csrfCookie]) {
    cookieStore.set(name, "", {
      path: "/",
      maxAge: 0,
      sameSite: "lax",
      secure: secureCookie,
    });
  }
}

export async function verifyCsrf(request: Request) {
  const cookieStore = await cookies();
  const cookieToken = cookieStore.get(csrfCookie)?.value;
  const headerToken = request.headers.get("x-csrf-token");
  return Boolean(cookieToken && headerToken && cookieToken === headerToken);
}
