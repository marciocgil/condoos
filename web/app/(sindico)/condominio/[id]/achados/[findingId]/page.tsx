import { FindingDetailView } from "@/components/condoos/FindingDetailView";
import { apiGet } from "@/lib/api";
import type { FindingDetail } from "@/lib/types";

export default async function FindingPage({
  params,
}: {
  params: Promise<{ id: string; findingId: string }>;
}) {
  const { id, findingId } = await params;
  const finding = await apiGet<FindingDetail>(`/condominiums/${id}/findings/${findingId}`);
  return (
    <FindingDetailView
      finding={finding}
      condominiumId={id}
      backHref={`/condominio/${id}/achados`}
      backLabel="Achados"
    />
  );
}
