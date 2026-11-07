import { OpportunityDetailView } from "@/components/condoos/OpportunityDetailView";
import { apiGet } from "@/lib/api";
import type { Me, OpportunityDetail } from "@/lib/types";

export default async function OportunidadePage({
  params,
}: {
  params: Promise<{ id: string; oppId: string }>;
}) {
  const { id, oppId } = await params;
  const [detail, me] = await Promise.all([
    apiGet<OpportunityDetail>(`/condominiums/${id}/opportunities/${oppId}`),
    apiGet<Me>("/me"),
  ]);
  const canOpen = me.condominiums.find((c) => c.id === id)?.permissions.includes("manage_cases");
  return (
    <OpportunityDetailView
      detail={detail}
      backHref={`/condominio/${id}/oportunidades`}
      backLabel="Oportunidades"
      findingPath={`/condominio/${id}/achados/{id}`}
      newCaseHref={
        canOpen && detail.presented
          ? `/condominio/${id}/assuntos/novo?oportunidade=${oppId}`
          : undefined
      }
    />
  );
}
