import type { Me } from "@/lib/types";

/** Condominiums where the person can see the internal farol (D122). */
export function auditCondos(me: Me): { id: string; name: string }[] {
  return me.condominiums
    .filter((c) => c.permissions.includes("view_audit"))
    .map((c) => ({ id: c.id, name: c.name }));
}

/** "2026-10" for the month before today (the default competence). */
export function lastMonth(): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function shiftMonth(ym: string, delta: number): string {
  const [y = 2000, m = 1] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function pct(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(Number(value) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

export const REVIEW_LABEL: Record<string, string> = {
  DRAFT: "Rascunho",
  NEEDS_HUMAN_REVIEW: "Aguarda revisão humana",
  REVIEWED: "Revisado",
  APPROVED_FOR_PUBLICATION: "Aprovado para publicação",
};
