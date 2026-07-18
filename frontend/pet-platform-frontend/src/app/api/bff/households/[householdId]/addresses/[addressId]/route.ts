import type { AddressUpdateBody } from "@/lib/api-types";
import {
  jsonError,
  jsonNoContent,
  jsonOk,
  readJson,
  requireCsrf,
} from "@/lib/api/bff-route";
import { deleteAddressBackend, updateAddressBackend } from "@/lib/api/backend";

export async function PATCH(
  request: Request,
  context: { params: Promise<{ householdId: string; addressId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { householdId, addressId } = await context.params;
    return jsonOk(
      await updateAddressBackend(
        householdId,
        addressId,
        await readJson<AddressUpdateBody>(request),
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}

export async function DELETE(
  request: Request,
  context: { params: Promise<{ householdId: string; addressId: string }> },
) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const { householdId, addressId } = await context.params;
    await deleteAddressBackend(householdId, addressId);
    return jsonNoContent();
  } catch (error) {
    return jsonError(error);
  }
}
