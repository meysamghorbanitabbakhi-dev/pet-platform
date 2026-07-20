const statusLabels: Record<string, string> = {
  closed: "بسته‌شده",
  in_review: "در حال بررسی",
  resolved: "پاسخ داده‌شده",
  submitted: "ثبت‌شده",
};

const statusTones: Record<
  string,
  "positive" | "info" | "warning" | "error" | "muted"
> = {
  closed: "muted",
  in_review: "info",
  resolved: "positive",
  submitted: "info",
};

const typeLabels: Record<string, string> = {
  concierge_sourcing: "درخواست تامین محصول",
  support: "پشتیبانی",
};

const promiseLabels: Record<string, string> = {
  availability: "تضمین موجودی",
  refund: "تضمین بازپرداخت",
  replacement: "تضمین تعویض",
  response_time: "تضمین زمان پاسخ",
  sourcing_success: "تضمین موفقیت تامین",
};

export function requestStatusLabel(value: string): string {
  return statusLabels[value] ?? value;
}

export function requestStatusTone(
  value: string,
): "positive" | "info" | "warning" | "error" | "muted" {
  return statusTones[value] ?? "muted";
}

export function requestTypeLabel(value: string): string {
  return typeLabels[value] ?? value;
}

export function promiseLabel(key: string): string {
  return promiseLabels[key] ?? key;
}

const offerStatusLabels: Record<string, string> = {
  accepted: "پذیرفته شد و سفارش ایجاد شد",
  declined: "رد شد",
  expired: "مهلت پاسخ به پایان رسید",
  offer_presented: "پیشنهاد آماده بررسی است",
  refresh_requested: "درخواست بررسی دوباره ثبت شد",
  reviewing: "در حال بررسی و راستی‌آزمایی",
  unavailable: "قابل تامین نیست",
};

const offerStatusTones: Record<
  string,
  "positive" | "info" | "warning" | "error" | "muted"
> = {
  accepted: "positive",
  declined: "muted",
  expired: "muted",
  offer_presented: "warning",
  refresh_requested: "info",
  reviewing: "info",
  unavailable: "muted",
};

export function offerStatusLabel(value: string): string {
  return offerStatusLabels[value] ?? value;
}

export function offerStatusTone(
  value: string,
): "positive" | "info" | "warning" | "error" | "muted" {
  return offerStatusTones[value] ?? "muted";
}
