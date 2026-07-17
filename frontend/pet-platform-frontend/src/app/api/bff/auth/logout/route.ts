import { jsonError, jsonNoContent, requireCsrf } from "@/lib/api/bff-route";
import { logoutBackend } from "@/lib/api/backend";

export async function POST(request: Request) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    await logoutBackend();
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
