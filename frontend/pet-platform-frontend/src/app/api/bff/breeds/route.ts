import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { listBreedsBackend } from "@/lib/api/backend";

export async function GET(request: Request) {
  try {
    const species = new URL(request.url).searchParams.get("species");
    return jsonOk(
      await listBreedsBackend(
        species === "dog" || species === "cat" ? species : undefined,
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
