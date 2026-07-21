import type { JourneyStartBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { startJourneyBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ petId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { petId } = await context.params;
    return jsonOk(
      await startJourneyBackend(
        petId,
        await readJson<JourneyStartBody>(request),
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
