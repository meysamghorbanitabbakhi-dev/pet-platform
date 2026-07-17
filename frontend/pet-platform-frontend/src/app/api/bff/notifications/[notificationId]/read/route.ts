import { jsonError, jsonNoContent, requireCsrf } from "@/lib/api/bff-route";
import { markNotificationReadBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ notificationId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { notificationId } = await context.params;
    await markNotificationReadBackend(notificationId);
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
