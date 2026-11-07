import { OpportunityDetailView } from "@/components/condoos/OpportunityDetailView";
import { apiGet } from "@/lib/api";
import type { OpportunityDetail } from "@/lib/types";

export default async function OportunidadeAdminPage({
  params,
}: {
  params: Promise<{ condoId: string; oppId: string }>;
}) {
  const { condoId, oppId } = await params;
  const detail = await apiGet<OpportunityDetail>(`/condominiums/${condoId}/opportunities/${oppId}`);
  return (
    <div className="max-w-3xl">
      <OpportunityDetailView
        detail={detail}
        backHref={`/admin/oportunidades?condominio=${condoId}`}
        backLabel="Oportunidades"
        findingPath={`/admin/achados/${condoId}/{id}`}
      />
    </div>
  );
}
