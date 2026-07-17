import type { PrivacyRequestBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { requestPrivacyActionBackend } from "@/lib/api/backend";

export async function POST(request: Request) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    return jsonOk(
      await requestPrivacyActionBackend(
        await readJson<PrivacyRequestBody>(request),
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
