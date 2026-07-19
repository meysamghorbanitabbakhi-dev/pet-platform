import { NextRequest } from "next/server";
import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { paymentCallbackBackend } from "@/lib/api/backend";

export async function GET(request: NextRequest) {
  try {
    const authority = request.nextUrl.searchParams.get("Authority");
    if (!authority) {
      return Response.json(
        { message: "شناسه پرداخت از درگاه دریافت نشد." },
        { status: 422 },
      );
    }
    return jsonOk(
      await paymentCallbackBackend(
        authority,
        request.nextUrl.searchParams.get("Status"),
      ),
    );
  } catch (error) {
    return jsonError(error);
  }
}
