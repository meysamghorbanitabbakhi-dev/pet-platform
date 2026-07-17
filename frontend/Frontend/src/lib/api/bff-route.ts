import "server-only";

import { NextResponse } from "next/server";
import { mapApiError } from "@/lib/api/errors";
import { verifyCsrf } from "@/lib/session/server";
import { BackendApiError } from "./backend";

export async function requireCsrf(request: Request) {
  if (await verifyCsrf(request)) return null;
  return NextResponse.json(
    { message: "درخواست معتبر نیست. صفحه را تازه‌سازی کنید." },
    { status: 403 },
  );
}

export async function readJson<T>(request: Request): Promise<T> {
  return (await request.json()) as T;
}

export function jsonOk<T>(data: T) {
  return NextResponse.json(data);
}

export function jsonNoContent() {
  return new NextResponse(null, { status: 204 });
}

export function jsonError(error: unknown) {
  if (error instanceof BackendApiError) {
    const mapped = mapApiError(error.status, error.detail);
    return NextResponse.json(
      { message: mapped.message, detail: mapped.detail },
      { status: mapped.status ?? 500 },
    );
  }
  return NextResponse.json(
    { message: "خطا در ارتباط با سرویس." },
    { status: 500 },
  );
}
