import { jsonError, jsonOk, requireCsrf } from "@/lib/api/bff-route";
import { listPetAssetsBackend, uploadPetAssetBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ petId: string }> },
) {
  try {
    const { petId } = await context.params;
    return jsonOk(await listPetAssetsBackend(petId));
  } catch (error) {
    return jsonError(error);
  }
}

export async function POST(
  request: Request,
  context: { params: Promise<{ petId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { petId } = await context.params;
    const filename = request.headers.get("x-filename");
    const category = request.headers.get("x-asset-category");
    const consentId = request.headers.get("x-consent-id");
    const mediaType = request.headers.get("content-type");
    if (!filename || !category || !consentId || !mediaType) {
      return jsonError(new Error("missing upload headers"));
    }
    const bytes = await request.arrayBuffer();
    return jsonOk(
      await uploadPetAssetBackend(
        petId,
        { bytes, mediaType },
        { category, consentId, filename },
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
