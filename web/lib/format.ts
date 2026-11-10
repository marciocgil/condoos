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
/** A contract's value as people say it: per month, or in total for a one-off contract. */
export function contractValue(c: {
  monthly_value: string | null;
  total_value?: string | null;
  installments?: number | null;
}): string {
  if (c.monthly_value !== null) return `${formatBRL(c.monthly_value)} por mês`;
  if (c.total_value) {
    const parts = c.installments && c.installments > 1 ? ` em ${c.installments} parcelas` : "";
    return `${formatBRL(c.total_value)} no total${parts}`;
  }
  return "—";
}

export function formatBRLShort(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(n);
}

/** ISO datetime -> "05/11/2026 14:32" in Brasília time. A fixed zone, not the runtime's:
 * pages render on the server (UTC) and in the browser, and both must show the same hour
 * (D80; an end-of-day deadline was shown as 02:59). Per-condominium zones are future work. */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(iso));
}
