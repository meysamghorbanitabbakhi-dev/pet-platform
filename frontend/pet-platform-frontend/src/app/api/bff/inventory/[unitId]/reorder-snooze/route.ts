import type { ReorderSnoozeBody } from "@/lib/api-types";
import {
  jsonError,
  jsonNoContent,
  readJson,
  requireCsrf,
} from "@/lib/api/bff-route";
import { snoozeReorderBackend } from "@/lib/api/backend";

export async function PUT(
  request: Request,
  context: { params: Promise<{ unitId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { unitId } = await context.params;
    await snoozeReorderBackend(
      unitId,
      await readJson<ReorderSnoozeBody>(request),
    );
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
