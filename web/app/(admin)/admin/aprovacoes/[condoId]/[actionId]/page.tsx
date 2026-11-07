import { ActionDetailView } from "@/components/condoos/ActionDetailView";
import { apiGet } from "@/lib/api";
import type { ActionDetail, ActionTypes } from "@/lib/types";

export default async function AprovacaoAdminPage({
  params,
}: {
  params: Promise<{ condoId: string; actionId: string }>;
}) {
  const { condoId, actionId } = await params;
  const [detail, types] = await Promise.all([
    apiGet<ActionDetail>(`/condominiums/${condoId}/actions/${actionId}`),
    apiGet<ActionTypes>("/action-types"),
  ]);
  return (
    <div className="max-w-3xl">
      <ActionDetailView
        detail={detail}
        types={types.types}
        backHref={`/admin/aprovacoes?condominio=${condoId}`}
        backLabel="Aprovações"
        casePath={`/admin/assuntos/${condoId}/{id}`}
      />
    </div>
  );
}
