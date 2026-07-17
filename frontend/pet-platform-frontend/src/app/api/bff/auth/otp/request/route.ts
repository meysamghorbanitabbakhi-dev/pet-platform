import type { OtpRequestBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson } from "@/lib/api/bff-route";
import { requestOtpBackend } from "@/lib/api/backend";

export async function POST(request: Request) {
  try {
    return jsonOk(
      await requestOtpBackend(await readJson<OtpRequestBody>(request)),
    );
  } catch (error) {
    return jsonError(error);
  }
}
