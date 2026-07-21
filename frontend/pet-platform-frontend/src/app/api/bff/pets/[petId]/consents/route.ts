import type { ConsentBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import {
  grantPetConsentBackend,
  listPetConsentsBackend,
} from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ petId: string }> },
) {
  try {
    const { petId } = await context.params;
    return jsonOk(await listPetConsentsBackend(petId));
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
    return jsonOk(
      await grantPetConsentBackend(petId, await readJson<ConsentBody>(request)),
    );
  } catch (error) {
    return jsonError(error);
  }
}
