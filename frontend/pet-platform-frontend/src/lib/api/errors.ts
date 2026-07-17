export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function mapApiError(status?: number, detail?: unknown): ApiError {
  if (status === 401)
    return new ApiError("نشست شما پایان یافته است.", status, detail);
  if (status === 403)
    return new ApiError(
      "این اقدام با سیاست فعلی در دسترس نیست.",
      status,
      detail,
    );
  if (status === 404)
    return new ApiError("داده مورد نظر پیدا نشد.", status, detail);
  if (status === 422)
    return new ApiError("اطلاعات واردشده نیاز به اصلاح دارد.", status, detail);
  if (status === 429)
    return new ApiError("تعداد درخواست‌ها بیش از حد مجاز است.", status, detail);
  return new ApiError("خطا در ارتباط با سرویس.", status, detail);
}
