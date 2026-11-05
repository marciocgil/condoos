const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function formatBRL(value: string | number): string {
  return brl.format(typeof value === "string" ? Number(value) : value);
}

/** "2026-10-01" -> "01/10/2026" (no timezone conversion). */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

const MONTHS = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

/** "2026-10-01" -> "outubro de 2026" */
export function formatMonth(iso: string): string {
  const [y, m] = iso.split("-");
  return `${MONTHS[Number(m) - 1] ?? m} de ${y}`;
}

/** "2026-10-01" -> "Outubro de 2026" */
export function formatMonthTitle(iso: string): string {
  const text = formatMonth(iso);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** "2026-10-01" -> "2026-10" (API competence parameter) */
export function competenceParam(iso: string): string {
  return iso.slice(0, 7);
}

/** Whole reais for highlights, as in the mockups: "R$ 6.200". */
export function formatBRLShort(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(n);
}

/** ISO datetime -> "05/11/2026 14:32" in the user's local time. */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(iso));
}
