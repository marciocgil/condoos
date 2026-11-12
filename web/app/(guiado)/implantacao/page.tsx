import { Building2, ChevronLeft } from "lucide-react";
import Link from "next/link";

import { GuidedChoice } from "@/components/condoos/GuidedChoice";
import { apiGet } from "@/lib/api";
import { type DayToDay, sindicoCondos } from "@/lib/daytoday";
import type { Me } from "@/lib/types";

/** Which implantation to continue (D128). */
export default async function ImplantacoesPage() {
  const me = await apiGet<Me>("/me");
  const days = await Promise.all(
    sindicoCondos(me).map((c) => apiGet<DayToDay>(`/condominiums/${c.id}/day`)),
  );
  return (
    <>
      <Link href="/inicio" className="inline-flex items-center gap-1 text-sm text-fg-2">
        <ChevronLeft size={16} aria-hidden /> Início
      </Link>
      <h1 className="text-[22px] font-semibold">Qual implantação?</h1>
      {days
        .filter((d) => !d.implemented)
        .map((d) => (
          <GuidedChoice
            key={d.condominium.id}
            href={`/implantacao/${d.condominium.id}`}
            icon={Building2}
            title={d.condominium.name}
            detail={`${d.implantation.percent}% · ${d.implantation.done} de ${d.implantation.total} itens`}
          />
        ))}
    </>
  );
}
