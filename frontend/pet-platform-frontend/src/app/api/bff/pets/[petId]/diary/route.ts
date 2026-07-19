import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listDiaryBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ petId: string }> },
) {
  try {
    const { petId } = await context.params;
    return jsonOk(await listDiaryBackend(petId));
  } catch (error) {
    return jsonError(error);
  }
}
