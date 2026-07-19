import { cookies } from "next/headers";
import { jsonError, jsonOk } from "@/lib/api/bff-route";
import { getMeContextBackend } from "@/lib/api/backend";

export async function GET() {
  if (await missingDevelopmentSession()) {
    return Response.json(
      { message: "نشست شما پایان یافته است." },
      { status: 401 },
    );
  }

  try {
    return jsonOk(await getMeContextBackend());
  } catch (error) {
    return jsonError(error);
  }
}

async function missingDevelopmentSession() {
  if (
    process.env.NODE_ENV === "production" ||
    process.env.GATE_FIXTURE_MODE !== "1"
  ) {
    return false;
  }
  const cookieStore = await cookies();
  return !(
    cookieStore.has("pet_access") || cookieStore.has("__Host-pet_access")
  );
}
