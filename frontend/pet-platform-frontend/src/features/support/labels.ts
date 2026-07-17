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
