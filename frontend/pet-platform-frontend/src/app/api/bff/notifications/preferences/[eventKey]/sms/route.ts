import type { NotificationPreferenceBody } from "@/lib/api-types";
import {
  jsonError,
  jsonNoContent,
  jsonOk,
  readJson,
  requireCsrf,
} from "@/lib/api/bff-route";
import {
  getSmsPreferenceBackend,
  updateSmsPreferenceBackend,
} from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ eventKey: string }> },
) {
  try {
    const { eventKey } = await context.params;
    return jsonOk(await getSmsPreferenceBackend(eventKey));
  } catch (error) {
    return jsonError(error);
  }
}

export async function PUT(
  request: Request,
  context: { params: Promise<{ eventKey: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { eventKey } = await context.params;
    await updateSmsPreferenceBackend(
      eventKey,
      await readJson<NotificationPreferenceBody>(request),
    );
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
