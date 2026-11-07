import { Sun } from "lucide-react";

import { BriefingView } from "@/components/condoos/BriefingView";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { Briefing } from "@/lib/types";

/** Hoje (VS-04, D82): one briefing per condominium, never mixed. */
export default async function HojePage({
  searchParams,
}: {
  searchParams: Promise<{ condominio?: string }>;
}) {
  const { condominio } = await searchParams;
  const all = await apiGet<Briefing[]>("/portfolio/briefing");
  const shown = condominio ? all.filter((b) => b.condominium_id === condominio) : all;
  return (
    <>
      <PageHeader
        title="Hoje"
        subtitle="O que precisa de você em cada condomínio, com a fonte de cada item. Nada é enviado por e-mail."
      />
      {shown.length === 0 ? (
        <EmptyState icon={<Sun size={24} />} title="Nenhum condomínio">
          Seu acesso ainda não está ligado a nenhum condomínio.
        </EmptyState>
      ) : (
        <div className="grid gap-8 xl:grid-cols-2">
          {shown.map((b) => (
            <BriefingView
              key={b.id}
              compact
              withName
              briefing={b}
              paths={{
                finding: `/admin/achados/${b.condominium_id}/{id}`,
                case: `/admin/assuntos/${b.condominium_id}/{id}`,
                opportunity: `/admin/oportunidades/${b.condominium_id}/{id}`,
                action: `/admin/aprovacoes/${b.condominium_id}/{id}`,
                agenda: `/admin/agenda?condominio=${b.condominium_id}`,
                queue: `/admin/fila?condominio=${b.condominium_id}`,
              }}
            />
          ))}
        </div>
      )}
    </>
  );
}
