import { ActionDetailView } from "@/components/condoos/ActionDetailView";
import { apiGet } from "@/lib/api";
import type { ActionDetail, ActionTypes } from "@/lib/types";

export default async function AprovacaoPage({
  params,
}: {
  params: Promise<{ id: string; actionId: string }>;
}) {
  const { id, actionId } = await params;
  const [detail, types] = await Promise.all([
    apiGet<ActionDetail>(`/condominiums/${id}/actions/${actionId}`),
    apiGet<ActionTypes>("/action-types"),
  ]);
  return (
    <ActionDetailView
      detail={detail}
      types={types.types}
      backHref={`/condominio/${id}/aprovacoes`}
      backLabel="Aprovações"
      casePath={`/condominio/${id}/assuntos/{id}`}
    />
  );
}
