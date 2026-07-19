import type { AddressBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import { createAddressBackend, listAddressesBackend } from "@/lib/api/backend";

export async function GET(
  _request: Request,
  context: { params: Promise<{ householdId: string }> },
) {
  try {
    const { householdId } = await context.params;
    return jsonOk(await listAddressesBackend(householdId));
  } catch (error) {
    return jsonError(error);
  }
}

export async function POST(
  request: Request,
  context: { params: Promise<{ householdId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { householdId } = await context.params;
    return jsonOk(
      await createAddressBackend(
        householdId,
        await readJson<AddressBody>(request),
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
