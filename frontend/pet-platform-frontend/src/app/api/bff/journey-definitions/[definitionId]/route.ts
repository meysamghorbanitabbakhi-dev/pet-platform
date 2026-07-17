import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getJourneyDefinitionBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ definitionId: string }> },
) {
  try {
    const { definitionId } = await context.params;
    return jsonOk(await getJourneyDefinitionBackend(definitionId));
  } catch (error) {
    return jsonError(error);
  }
}
