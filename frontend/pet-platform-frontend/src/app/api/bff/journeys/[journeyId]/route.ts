import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getJourneyBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ journeyId: string }> },
) {
  try {
    const { journeyId } = await context.params;
    return jsonOk(await getJourneyBackend(journeyId));
  } catch (error) {
    return jsonError(error);
  }
}
