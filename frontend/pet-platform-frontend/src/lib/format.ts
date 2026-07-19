const persianDigits = new Intl.NumberFormat("fa-IR", {
  maximumFractionDigits: 0,
  numberingSystem: "arabext",
});

export function formatPersianNumber(value: number): string {
  return persianDigits.format(value);
}

const persianDecimals = new Intl.NumberFormat("fa-IR", {
  maximumFractionDigits: 2,
  numberingSystem: "arabext",
});

export function formatPersianDecimal(value: number): string {
  return persianDecimals.format(value);
}

export function tomanFromIrr(irr: number, divisor = 10): number {
  return Math.trunc(irr / divisor);
}

export function formatTomanFromIrr(irr: number, divisor = 10): string {
  return `${formatPersianNumber(tomanFromIrr(irr, divisor))} تومان`;
}

export function formatDeliveryCommitment(hours: number): string {
  return `${formatPersianNumber(hours)} ساعت`;
}

const iranDateTimeFormatter = new Intl.DateTimeFormat("fa-IR-u-nu-arabext", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Tehran",
});

const iranDateFormatter = new Intl.DateTimeFormat("fa-IR-u-nu-arabext", {
  dateStyle: "medium",
  timeZone: "Asia/Tehran",
});

export function formatIranDateTime(value: string | null | undefined): string {
  if (!value) return "ثبت نشده";
  return iranDateTimeFormatter.format(new Date(value));
}

export function formatIranDate(value: string | null | undefined): string {
  if (!value) return "ثبت نشده";
  return iranDateFormatter.format(new Date(value));
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "ثبت نشده";
  return `${formatPersianNumber(value)}٪`;
}
