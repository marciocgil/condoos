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

/** The month's farol sent to the síndico (D124). */
export type Publication = {
  id: string;
  competencia: string;
  status: "aguardando_sindico" | "aprovada" | "devolvida" | "superada";
  sha256: string;
  submitted_at: string;
  submitted_by: string | null;
  decided_at: string | null;
  decided_by: string | null;
  reason: string | null;
  changed_since: boolean | null;
  snapshot: {
    competencia: string;
    contagem: Record<string, number>;
    controles: {
      id: string;
      nome: string;
      pilar: string;
      status: string;
      motivo: string;
      pendencias: string[];
    }[];
  };
};

export const PUBLICATION_LABEL: Record<Publication["status"], string> = {
  aguardando_sindico: "Aguardando o síndico",
  aprovada: "Aprovado pelo síndico",
  devolvida: "Devolvido pelo síndico",
  superada: "Substituído (o farol mudou)",
};
