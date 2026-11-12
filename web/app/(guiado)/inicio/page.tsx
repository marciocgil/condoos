import { Flag, Sun } from "lucide-react";
import { redirect } from "next/navigation";

import { GuidedChoice } from "@/components/condoos/GuidedChoice";
import { apiGet } from "@/lib/api";
import { type DayToDay, sindicoCondos } from "@/lib/daytoday";
import type { Launch, Me } from "@/lib/types";

function greeting(): string {
  const h = Number(
    new Intl.DateTimeFormat("pt-BR", { hour: "numeric", timeZone: "America/Sao_Paulo" }).format(
      new Date(),
    ),
  );
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

/** The síndico's start (D127): "O que vamos fazer hoje?" with only the paths that apply.
 * Implanting and closing a condominium come in the next slices. */
export default async function InicioPage() {
  const me = await apiGet<Me>("/me");
  const condos = sindicoCondos(me);
  if (condos.length === 0) redirect("/");
  const days = await Promise.all(condos.map((c) => apiGet<DayToDay>(`/condominiums/${c.id}/day`)));
  const running = days.filter((d) => d.implemented);
  const implementing = days.filter((d) => !d.implemented);
  const progress = implementing[0]
    ? (await apiGet<Launch>(`/condominiums/${implementing[0].condominium.id}/launch`)).progress
    : null;
  const first = me.name.split(" ")[0];
  const attention = running.reduce((n, d) => n + d.attention.count, 0);
  return (
    <>
      <h1 className="mt-2 text-[26px] leading-tight font-semibold text-balance">
        {greeting()}, {first}. O que vamos fazer hoje?
      </h1>
      {running.length > 0 && (
        <GuidedChoice
          testId="choice-dia-a-dia"
          href={running.length === 1 ? `/dia-a-dia/${running[0]!.condominium.id}` : "/dia-a-dia"}
          icon={Sun}
          title="Cuidar do dia a dia"
          detail={
            `Enviar as contas do mês e ver o farol` +
            (running.length > 1 ? ` · ${running.length} condomínios` : "") +
            (attention ? ` · ${attention} ponto(s) de atenção` : "")
          }
        />
      )}
      {implementing.length > 0 && (
        <GuidedChoice
          testId="choice-implantacao"
          href={`/condominio/${implementing[0]!.condominium.id}/resumo`}
          icon={Flag}
          title="Continuar uma implantação"
          detail={
            `${implementing[0]!.condominium.name}` +
            (progress ? `: ${progress.done} de ${progress.total} passos` : "") +
            (implementing.length > 1 ? ` · e mais ${implementing.length - 1}` : "")
          }
        />
      )}
    </>
  );
}
