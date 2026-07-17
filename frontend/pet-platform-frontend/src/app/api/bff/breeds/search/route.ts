import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { searchBreedsBackend } from "@/lib/api/backend";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const q = url.searchParams.get("q") ?? "";
    const species = url.searchParams.get("species");
    return jsonOk(
      await searchBreedsBackend(
        q,
        species === "dog" || species === "cat" ? species : undefined,
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
