import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getDiaryEntryBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ petId: string; entryId: string }> },
) {
  try {
    const { petId, entryId } = await context.params;
    return jsonOk(await getDiaryEntryBackend(petId, entryId));
  } catch (error) {
    return jsonError(error);
  }
}
