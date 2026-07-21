import { jsonError, jsonNoContent, requireCsrf } from "@/lib/api/bff-route";
import {
  deletePetAssetBackend,
  downloadPetAssetBackend,
} from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ petId: string; assetId: string }> },
) {
  try {
    const { petId, assetId } = await context.params;
    const backendResponse = await downloadPetAssetBackend(petId, assetId);
    // Proxy the binary body only; never redirect to or expose the backend
    // storage location itself.
    return new Response(backendResponse.body, {
      headers: {
        "Content-Type":
          backendResponse.headers.get("content-type") ??
          "application/octet-stream",
        "Content-Disposition":
          backendResponse.headers.get("content-disposition") ?? "inline",
      },
    });
  } catch (error) {
    return jsonError(error);
  }
}

export async function DELETE(
  request: Request,
  context: { params: Promise<{ petId: string; assetId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { petId, assetId } = await context.params;
    await deletePetAssetBackend(petId, assetId);
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
