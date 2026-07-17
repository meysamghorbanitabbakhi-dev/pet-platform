import type { OpenInventoryBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { openInventoryBackend } from "@/lib/api/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ unitId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { unitId } = await context.params;
    return jsonOk(
      await openInventoryBackend(
        unitId,
        await readJson<OpenInventoryBody>(request),
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
