import { Building2, ChevronLeft } from "lucide-react";
import Link from "next/link";

import { GuidedChoice } from "@/components/condoos/GuidedChoice";
import { apiGet } from "@/lib/api";
import { type DayToDay, sindicoCondos } from "@/lib/daytoday";
import type { Me } from "@/lib/types";

/** Which condominium today (D127): one line each, with what is missing. */
export default async function EscolherCondominioPage() {
  const me = await apiGet<Me>("/me");
  const days = await Promise.all(
    sindicoCondos(me).map((c) => apiGet<DayToDay>(`/condominiums/${c.id}/day`)),
  );
  return (
    <>
      <Link href="/inicio" className="inline-flex items-center gap-1 text-sm text-fg-2">
        <ChevronLeft size={16} aria-hidden /> Início
      </Link>
      <h1 className="text-[22px] font-semibold">Qual condomínio?</h1>
      {days
        .filter((d) => d.implemented)
        .map((d) => {
          const missing = d.checklist.filter((i) => i.status === "falta").length;
          return (
            <GuidedChoice
              key={d.condominium.id}
              href={`/dia-a-dia/${d.condominium.id}`}
              icon={Building2}
              title={d.condominium.name}
              detail={
                missing
                  ? `${missing} item(ns) de ${d.month_label} faltando`
                  : `${d.month_label}: tudo recebido`
              }
            />
          );
        })}
    </>
  );
}
