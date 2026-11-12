import type { Me } from "@/lib/types";

/** The síndico's day to day of one condominium (D127). */
export type DayToDay = {
  condominium: { id: string; name: string };
  month: string;
  month_label: string;
  implemented: boolean;
  implantation: { done: number; total: number; percent: number };
  can_upload: boolean;
  checklist: { key: string; title: string; status: "ok" | "falta"; detail: string }[];
  farol: {
    last_approved: {
      id: string;
      competencia: string;
      validados: number;
      ressalvas: number;
      pendentes: number;
      divergentes: number;
    } | null;
    waiting_for_you: boolean;
    in_review: boolean;
  };
  attention: { count: number; items: { id: string; title: string }[] };
};

/** Condominiums where the person is the síndico (only the síndico approves the farol, D124):
 * they are the ones the guided start applies to (D127). */
export function sindicoCondos(me: Me): Me["condominiums"] {
  return me.condominiums.filter((c) => c.permissions.includes("approve_audit_publication"));
}

export function monthTitle(ym: string): string {
  const [y, m] = ym.split("-");
  return `${m}/${y}`;
}
