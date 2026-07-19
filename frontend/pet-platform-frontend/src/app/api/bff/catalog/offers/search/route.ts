import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { searchOffersBackend } from "@/lib/api/backend";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const q = url.searchParams.get("q") ?? "";
    const limit = Number(url.searchParams.get("limit") ?? "25");
    const offset = Number(url.searchParams.get("offset") ?? "0");
    return jsonOk(await searchOffersBackend(q, limit, offset));
  } catch (error) {
    return jsonError(error);
  }
}
