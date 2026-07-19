import type { OtpVerifyBody, OtpVerifyResponse } from "@/lib/api-types";
import { jsonError, jsonOk, readJson } from "@/lib/api/bff-route";
import { verifyOtpBackend } from "@/lib/api/backend";
import { setSessionFromOtp } from "@/lib/session/server";

type PublicOtpVerifyResponse = Omit<
  OtpVerifyResponse,
  "access_token" | "refresh_token" | "token_type"
>;

function stripTokens(response: OtpVerifyResponse): PublicOtpVerifyResponse {
  return {
    attempts_remaining: response.attempts_remaining,
    expires_in_seconds: response.expires_in_seconds,
    identity_id: response.identity_id,
    state: response.state,
  };
}

export async function POST(request: Request) {
  try {
    const response = await verifyOtpBackend(
      await readJson<OtpVerifyBody>(request),
    );
    await setSessionFromOtp(response);
    return jsonOk(stripTokens(response));
  } catch (error) {
    return jsonError(error);
  }
}
