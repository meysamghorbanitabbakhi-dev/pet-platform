import type { CustomerRequestBody } from "@/lib/api-types";
import { jsonError, jsonOk, readJson, requireCsrf } from "@/lib/api/bff-route";
import {
  createCustomerRequestBackend,
  listCustomerRequestsBackend,
} from "@/lib/api/backend";

type CreateCustomerRequestPayload = {
  body: CustomerRequestBody;
  idempotencyKey: string;
};

export async function GET() {
  try {
    return jsonOk(await listCustomerRequestsBackend());
  } catch (error) {
    return jsonError(error);
  }
}

export async function POST(request: Request) {
  const csrfError = await requireCsrf(request);
  if (csrfError) return csrfError;

  try {
    const payload = await readJson<CreateCustomerRequestPayload>(request);
    return jsonOk(
      await createCustomerRequestBackend(payload.body, payload.idempotencyKey),
    );
  } catch (error) {
    return jsonError(error);
  }
}
