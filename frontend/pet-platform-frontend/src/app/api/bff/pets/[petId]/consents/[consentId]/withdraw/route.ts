import { jsonError, jsonNoContent, requireCsrf } from "@/lib/api/bff-route";
import { withdrawPetConsentBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ petId: string; consentId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { petId, consentId } = await context.params;
    await withdrawPetConsentBackend(petId, consentId);
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
