import { FindingDetailView } from "@/components/condoos/FindingDetailView";
import { apiGet } from "@/lib/api";
import type { FindingDetail } from "@/lib/types";

/** The manager validates or discards a serious finding before the síndico sees it. */
export default async function ValidateFindingPage({
  params,
}: {
  params: Promise<{ condoId: string; findingId: string }>;
}) {
  const { condoId, findingId } = await params;
  const finding = await apiGet<FindingDetail>(`/condominiums/${condoId}/findings/${findingId}`);
  return (
    <div className="max-w-3xl">
      <FindingDetailView
        finding={finding}
        condominiumId={condoId}
        backHref="/admin/fila"
        backLabel="Fila de exceções"
      />
    </div>
  );
}
