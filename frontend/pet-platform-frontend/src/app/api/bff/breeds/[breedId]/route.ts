import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getBreedDetailBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ breedId: string }> },
) {
  try {
    const { breedId } = await context.params;
    return jsonOk(await getBreedDetailBackend(breedId));
  } catch (error) {
    return jsonError(error);
  }
}
