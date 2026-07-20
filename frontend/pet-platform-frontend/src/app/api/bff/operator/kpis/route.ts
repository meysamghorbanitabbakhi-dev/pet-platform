import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listOperatorKpisBackend } from "@/lib/api/backend";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const windowStart = url.searchParams.get("window_start") ?? "";
    const windowEnd = url.searchParams.get("window_end") ?? "";
    return jsonOk(await listOperatorKpisBackend(windowStart, windowEnd));
  } catch (error) {
    return jsonError(error);
  }
}
