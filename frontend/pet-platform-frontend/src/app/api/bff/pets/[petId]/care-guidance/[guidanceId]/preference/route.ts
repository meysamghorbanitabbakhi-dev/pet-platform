import type { GuidancePreferenceBody } from "@/lib/api-types";
import {
  jsonError,
  jsonNoContent,
  readJson,
  requireCsrf,
} from "@/lib/api/bff-route";
import { setGuidancePreferenceBackend } from "@/lib/api/backend";

export async function PUT(
  request: Request,
  context: { params: Promise<{ petId: string; guidanceId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { petId, guidanceId } = await context.params;
    await setGuidancePreferenceBackend(
      petId,
      guidanceId,
      await readJson<GuidancePreferenceBody>(request),
    );
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
