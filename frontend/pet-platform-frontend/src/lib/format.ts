const persianDigits = new Intl.NumberFormat("fa-IR", {
  maximumFractionDigits: 0,
  numberingSystem: "arabext",
});

export function formatPersianNumber(value: number): string {
  return persianDigits.format(value);
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
