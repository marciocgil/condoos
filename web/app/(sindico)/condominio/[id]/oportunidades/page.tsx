import { PiggyBank } from "lucide-react";

import { OpportunityCards } from "@/components/condoos/OpportunityCards";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { OpportunityRow } from "@/lib/types";

export default async function OportunidadesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const rows = await apiGet<OpportunityRow[]>(`/condominiums/${id}/opportunities`);
  return (
    <>
      <h1 className="text-xl font-semibold">Oportunidades de economia</h1>
      <p className="text-[13px] text-fg-2">
        Revisadas pela equipe CondoOS antes de chegar aqui. Valores são estimativas até serem
        comprovados.
      </p>
      {rows.length === 0 ? (
        <EmptyState icon={<PiggyBank size={24} />} title="Nenhuma oportunidade apresentada">
          Quando a revisão CondoOS aprovar uma oportunidade, ela aparece aqui para sua decisão.
        </EmptyState>
      ) : (
        <OpportunityCards rows={rows} hrefFor={(r) => `/condominio/${id}/oportunidades/${r.id}`} />
      )}
    </>
  );
}
