export function supplierCountryLabel(value: string | null | undefined) {
  if (!value) return "ثبت نشده";
  const normalized = value.trim().toUpperCase();
  const countries: Record<string, string> = {
    CN: "چین",
    DE: "آلمان",
    FR: "فرانسه",
    GB: "بریتانیا",
    IR: "ایران",
    IT: "ایتالیا",
    NL: "هلند",
    TR: "ترکیه",
    US: "آمریکا",
  };
  return countries[normalized] ?? value;
}

export function availabilityLabel(value: string) {
  if (value === "available") return "موجود برای پرداخت کامل";
  if (value === "temporarily_unavailable") return "فعلا ناموجود";
  return value;
}

export function orderStatusLabel(value: string) {
  const labels: Record<string, string> = {
    awaiting_payment: "در انتظار پرداخت",
    cancelled: "لغوشده",
    delivered: "تحویل‌شده",
    failed: "ناموفق",
    in_transit: "در مسیر تحویل",
    paid: "پرداخت تایید شده",
    refunded: "بازپرداخت‌شده",
    sourcing: "در حال تامین پس از پرداخت",
  };
  return labels[value] ?? value;
}

export function paymentCallbackLabel(value: string) {
  if (value === "verified") return "پرداخت توسط سرویس تایید شد";
  if (value === "cancelled_or_failed") return "پرداخت توسط سرویس تایید نشد";
  return value;
}
